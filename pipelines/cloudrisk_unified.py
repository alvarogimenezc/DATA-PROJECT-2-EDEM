"""
CloudRISK — Unified Streaming Pipeline (Apache Beam / Dataflow)

Fan-in de 3 topics Pub/Sub (player-movements, weather, air-quality) a un único
pipeline con **stateful DoFn** por player_id. Aplica toda la lógica de negocio
del juego en streaming:

  1. Calcula distancia recorrida por usuario (haversine vs. última posición).
  2. Calcula velocidad media en km/h. Si > MAX_SPEED_KMH → rechazo anti-trampa
     (evento a DLQ, no se actualiza estado ni Firestore).
  3. Cap de pasos diario: si el usuario ha reportado ya ≥ DAILY_STEPS_CAP
     pasos hoy, trunca el exceso (no se acumula ni a ejércitos ni a steps).
     Es una defensa anti-trampa adicional al speed check.
  4. Factor multiplicador = último multiplicador ambiental (aire × clima)
     propagado como side input desde los topics weather + air-quality.
  5. Ejércitos equivalentes: (pasos permitidos // POWER_PER_STEPS) × factor.
  6. Límite diario de armies: CombiningValueState acumula armies del día y
     trunca al cap DAILY_ARMY_CAP. Un timer ProcessingTime resetea a diario
     ambos contadores (armies y steps).

Sinks:
  - Firestore (UPSERT con Increment) — colecciones user_balance/ y users/.
  - BigQuery (INSERT WRITE_APPEND) — tabla `cloudrisk.player_scoring_events`.
  - BigQuery DLQ — tabla `cloudrisk.dead_letter` para mensajes rechazados.
  - BigQuery ambiental — tabla `cloudrisk.environmental_factors` (histórico).

Ejecución local (DirectRunner):

    python pipelines/cloudrisk_unified.py \\
        --runner=DirectRunner \\
        --project=cloudrisk-local \\
        --player_sub=projects/cloudrisk-local/subscriptions/player-movements-sub \\
        --weather_sub=projects/cloudrisk-local/subscriptions/weather-sub \\
        --airq_sub=projects/cloudrisk-local/subscriptions/air-quality-sub \\
        --scoring_table=cloudrisk-local:cloudrisk.player_scoring_events \\
        --env_table=cloudrisk-local:cloudrisk.environmental_factors \\
        --dlq_table=cloudrisk-local:cloudrisk.dead_letter \\
        --streaming

Producción (DataflowRunner):

    python pipelines/cloudrisk_unified.py \\
        --runner=DataflowRunner \\
        --project=<PROJECT_ID> \\
        --region=europe-west1 \\
        --temp_location=gs://<PROJECT_ID>-dataflow/tmp \\
        --staging_location=gs://<PROJECT_ID>-dataflow/staging \\
        --player_sub=... --weather_sub=... --airq_sub=... \\
        --scoring_table=... --env_table=... --dlq_table=... \\
        --streaming

EDEM. Master Big Data & Cloud 2025/2026
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.transforms import trigger, window
from apache_beam.transforms.userstate import (
    CombiningValueStateSpec,
    ReadModifyWriteStateSpec,
    TimerSpec,
    on_timer,
)
from apache_beam.transforms.timeutil import TimeDomain


# ─── Parámetros de juego (overridables por env var o flag CLI) ────────────────
DEFAULT_POWER_PER_STEPS = int(os.environ.get("POWER_PER_STEPS", "500"))
DEFAULT_DAILY_ARMY_CAP = int(os.environ.get("DAILY_ARMY_CAP", "50"))
DEFAULT_MAX_SPEED_KMH = float(os.environ.get("MAX_SPEED_KMH", "15"))
DEFAULT_DAILY_STEPS_CAP = int(os.environ.get("DAILY_STEPS_CAP", "30000"))
# Multiplicador ambiental que asumimos cuando aún no ha llegado ningún
# evento de aire/clima al side input — neutral, no penaliza ni premia.
DEFAULT_ENV_MULTIPLIER = 1.0
# Horas entre resets de los contadores diarios (armies_today, steps_today).
# No es parametrizable por evento: es una constante operativa.
DAILY_RESET_HOURS = 24.0


# ─── Schemas BigQuery ─────────────────────────────────────────────────────────
SCORING_SCHEMA = {
    "fields": [
        {"name": "player_id",          "type": "STRING",    "mode": "REQUIRED"},
        {"name": "ts",                 "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "latitude",           "type": "FLOAT",     "mode": "NULLABLE"},
        {"name": "longitude",          "type": "FLOAT",     "mode": "NULLABLE"},
        {"name": "steps_delta",        "type": "INTEGER",   "mode": "REQUIRED"},
        {"name": "distance_m",         "type": "FLOAT",     "mode": "REQUIRED"},
        {"name": "speed_kmh",          "type": "FLOAT",     "mode": "REQUIRED"},
        {"name": "env_multiplier",     "type": "FLOAT",     "mode": "REQUIRED"},
        {"name": "rappel_applied",     "type": "BOOLEAN",   "mode": "REQUIRED"},
        {"name": "armies_earned",      "type": "INTEGER",   "mode": "REQUIRED"},
        {"name": "armies_today_after", "type": "INTEGER",   "mode": "REQUIRED"},
        {"name": "capped",             "type": "BOOLEAN",   "mode": "REQUIRED"},
        {"name": "processed_at",       "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
}

ENV_SCHEMA = {
    "fields": [
        {"name": "ts",           "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "type",         "type": "STRING",    "mode": "REQUIRED"},
        {"name": "multiplier",   "type": "FLOAT",     "mode": "REQUIRED"},
        {"name": "raw_payload",  "type": "STRING",    "mode": "REQUIRED"},
        {"name": "processed_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
}

DLQ_SCHEMA = {
    "fields": [
        {"name": "source",       "type": "STRING",    "mode": "REQUIRED"},
        {"name": "reason",       "type": "STRING",    "mode": "REQUIRED"},
        {"name": "player_id",    "type": "STRING",    "mode": "NULLABLE"},
        {"name": "raw_payload",  "type": "STRING",    "mode": "REQUIRED"},
        {"name": "processed_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
}


# ─── Helpers puros (testables sin Beam) ───────────────────────────────────────
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en metros entre dos coordenadas WGS84."""
    r = 6_371_000.0  # radio Tierra en metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_ts(ts_str: str) -> datetime:
    """Parsea un ISO-8601 con o sin sufijo Z. Si falla, devuelve `now()` en UTC.

    Lo usamos en dos sitios (parse del evento y reset del timer) — centralizar
    aquí evita el `try/except ValueError` repetido y deja claro el fallback.
    """
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return datetime.now(timezone.utc)


def dlq_record(source: str, reason: str, player_id, raw_payload: str) -> dict:
    """Construye una fila para la tabla `dead_letter` en BQ.

    Llamado desde 5 sitios (los 3 DoFns de parse + scoring), por eso vive
    suelto a nivel módulo en vez de duplicar la misma estructura inline.
    """
    return {
        "source": source,
        "reason": reason,
        "player_id": player_id,
        "raw_payload": raw_payload,
        "processed_at": now_utc_iso(),
    }


# ─── Parse DoFns ──────────────────────────────────────────────────────────────
class ParseMovement(beam.DoFn):
    """Decodifica un mensaje player-movements. TaggedOutput 'dlq' si falla."""
    DLQ = "dlq"

    def process(self, raw: bytes):
        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            yield beam.pvalue.TaggedOutput(self.DLQ, dlq_record(
                source="player-movements",
                reason=f"json_decode: {exc}",
                player_id=None,
                raw_payload=raw[:500].decode("utf-8", errors="replace"),
            ))
            return

        pid = msg.get("player_id")
        if not pid:
            yield beam.pvalue.TaggedOutput(self.DLQ, dlq_record(
                source="player-movements",
                reason="missing_player_id",
                player_id=None,
                raw_payload=json.dumps(msg),
            ))
            return

        yield (pid, {
            "player_id": pid,
            "ts": msg.get("timestamp") or msg.get("ts") or now_utc_iso(),
            "latitude": float(msg["latitude"]) if msg.get("latitude") is not None else None,
            "longitude": float(msg["longitude"]) if msg.get("longitude") is not None else None,
            "steps_delta": int(msg.get("steps_delta", msg.get("steps", 0))),
            "raw": msg,
        })


class ParseEnvironment(beam.DoFn):
    """Decodifica air_quality / weather a una fila unificada y el multiplicador."""
    DLQ = "dlq"

    def process(self, raw: bytes):
        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            yield beam.pvalue.TaggedOutput(self.DLQ, dlq_record(
                source="environmental",
                reason=f"json_decode: {exc}",
                player_id=None,
                raw_payload=raw[:500].decode("utf-8", errors="replace"),
            ))
            return

        mtype = msg.get("type")
        if mtype == "air_quality":
            mult = msg.get("indice_multiplicador_aire")
        elif mtype == "weather":
            mult = msg.get("indice_multiplicador_tiempo")
        else:
            yield beam.pvalue.TaggedOutput(self.DLQ, dlq_record(
                source="environmental",
                reason=f"unsupported_type:{mtype!r}",
                player_id=None,
                raw_payload=json.dumps(msg),
            ))
            return

        if mult is None:
            yield beam.pvalue.TaggedOutput(self.DLQ, dlq_record(
                source="environmental",
                reason="missing_multiplier",
                player_id=None,
                raw_payload=json.dumps(msg),
            ))
            return

        # Para BQ environmental_factors
        yield {
            "ts":           msg.get("ts") or now_utc_iso(),
            "type":         mtype,
            "multiplier":   float(mult),
            "raw_payload":  json.dumps(msg),
            "processed_at": now_utc_iso(),
        }


class ExtractMultiplier(beam.DoFn):
    """De una fila environmental ya parseada extrae (kind, multiplier) para combinar."""
    def process(self, row):
        yield (row["type"], float(row["multiplier"]))


# ─── Side input: último multiplicador ambiental agregado ──────────────────────
class LatestMultiplierCombineFn(beam.CombineFn):
    """Conserva el último multiplicador recibido por tipo (air_quality / weather)
    y lo combina en un único factor (aire × clima). Se expone como AsSingleton.
    """
    def create_accumulator(self):
        return {"air_quality": 1.0, "weather": 1.0}

    def add_input(self, acc, inp):
        kind, mult = inp
        if kind in acc:
            acc[kind] = mult
        return acc

    def merge_accumulators(self, accs):
        out = {"air_quality": 1.0, "weather": 1.0}
        for a in accs:
            for k, v in a.items():
                if k in out:
                    out[k] = v
        return out

    def extract_output(self, acc):
        return float(acc.get("air_quality", 1.0)) * float(acc.get("weather", 1.0))


# ─── El corazón: StatefulScoringDoFn ──────────────────────────────────────────
LAST_POS_STATE = ReadModifyWriteStateSpec("last_pos", beam.coders.PickleCoder())
ARMIES_TODAY_STATE = CombiningValueStateSpec("armies_today", beam.coders.VarIntCoder(), sum)
STEPS_TODAY_STATE = CombiningValueStateSpec("steps_today", beam.coders.VarIntCoder(), sum)
DAILY_RESET_TIMER = TimerSpec("daily_reset", TimeDomain.REAL_TIME)


class StatefulScoringDoFn(beam.DoFn):
    """Scoring estado-por-jugador. Consume (player_id, movement_dict) y emite
    (scoring_event_for_bq, firestore_delta) por el cauce principal, y dead-
    letter por el tag DLQ.
    """
    DLQ = "dlq"

    def __init__(
        self,
        max_speed_kmh: float = DEFAULT_MAX_SPEED_KMH,
        power_per_steps: int = DEFAULT_POWER_PER_STEPS,
        daily_cap: int = DEFAULT_DAILY_ARMY_CAP,
        daily_steps_cap: int = DEFAULT_DAILY_STEPS_CAP,
    ):
        self.max_speed_kmh = float(max_speed_kmh)
        self.power_per_steps = int(power_per_steps)
        self.daily_cap = int(daily_cap)
        self.daily_steps_cap = int(daily_steps_cap)

    # ─── Helpers internos (puros, sin tocar estado Beam) ──────────────────────
    @staticmethod
    def _calculate_speed_kmh(prev, lat, lon, ev_ts):
        """Devuelve `(distance_m, speed_kmh)` vs. la última posición.

        Si no había posición previa o falta alguna coordenada, devuelve `(0, 0)`
        (no hay cómo calcular velocidad). `dt_s` se acota a 1µs para evitar
        división por cero si dos eventos llegan con el mismo timestamp.
        """
        sin_posicion_previa = (
            not prev
            or lat is None or lon is None
            or prev.get("lat") is None or prev.get("lon") is None
        )
        if sin_posicion_previa:
            return 0.0, 0.0
        distance_m = haversine_m(prev["lat"], prev["lon"], lat, lon)
        dt_s = max(1e-6, (ev_ts - prev["ts"]).total_seconds())
        speed_kmh = (distance_m / 1000.0) / (dt_s / 3600.0)
        return distance_m, speed_kmh

    def _compute_armies(self, allowed_steps, env_factor, today_so_far):
        """Aplica el cap diario de armies y devuelve `(armies_earned, capped)`.

        `armies_earned` nunca supera `daily_cap - today_so_far`; el resto se
        descarta. `capped=True` significa que se truncó por este cap (no por
        el de pasos — esos son flags separados).
        """
        raw_armies = int((allowed_steps // self.power_per_steps) * env_factor)
        remaining = max(0, self.daily_cap - today_so_far)
        return min(raw_armies, remaining), raw_armies > remaining

    def process(
        self,
        keyed_event,
        env_mult=DEFAULT_ENV_MULTIPLIER,
        last_pos=beam.DoFn.StateParam(LAST_POS_STATE),
        armies_today=beam.DoFn.StateParam(ARMIES_TODAY_STATE),
        steps_today=beam.DoFn.StateParam(STEPS_TODAY_STATE),
        daily_timer=beam.DoFn.TimerParam(DAILY_RESET_TIMER),
    ):
        player_id, evt = keyed_event
        ev_ts = parse_iso_ts(evt["ts"])

        lat, lon = evt.get("latitude"), evt.get("longitude")
        steps = int(evt.get("steps_delta", 0))

        # 1) Calcula velocidad vs. la última posición conocida.
        prev = last_pos.read()
        distance_m, speed_kmh = self._calculate_speed_kmh(prev, lat, lon, ev_ts)

        # 2) Anti-trampa: rechazar si la velocidad supera el límite.
        # Importante: `return` aquí salta TODOS los writes a estado, así el
        # evento tramposo no contamina los contadores diarios ni la posición.
        if speed_kmh > self.max_speed_kmh:
            yield beam.pvalue.TaggedOutput(self.DLQ, dlq_record(
                source="player-movements",
                reason=f"anti_cheat_speed:{speed_kmh:.2f}kmh>{self.max_speed_kmh}",
                player_id=player_id,
                raw_payload=json.dumps(evt.get("raw", {})),
            ))
            return

        # 3) Cap de pasos diario — el exceso se descarta. No entra ni en
        # armies ni en total_steps. Es la segunda barrera anti-trampa
        # (complementa al speed check).
        pasos_hoy = int(steps_today.read() or 0)
        pasos_restantes_cap = max(0, self.daily_steps_cap - pasos_hoy)
        pasos_permitidos = min(steps, pasos_restantes_cap)
        steps_capped = pasos_permitidos < steps

        # 4) Calcula armies con el multiplicador ambiental + cap diario.
        env_factor = float(env_mult) if env_mult is not None else DEFAULT_ENV_MULTIPLIER
        today_so_far = int(armies_today.read() or 0)
        armies_earned, armies_capped = self._compute_armies(
            pasos_permitidos, env_factor, today_so_far,
        )
        # `capped` en BQ señaliza que *algo* se truncó — cap de armies o de pasos.
        capped = armies_capped or steps_capped

        # 5) Actualiza estado sólo si el evento es válido (pasa anti-trampa).
        last_pos.write({"lat": lat, "lon": lon, "ts": ev_ts})
        if pasos_permitidos > 0:
            steps_today.add(pasos_permitidos)
        if armies_earned > 0:
            armies_today.add(armies_earned)

        # 6) Programa reset diario. El timer es idempotente por nombre, así que
        # cada llamada a `set()` SOBREESCRIBE el anterior — el cooldown de 24 h
        # se reinicia en cada evento, no se acumula. Si no llegan eventos, el
        # último timer programado dispara igualmente y limpia los contadores.
        next_reset = (ev_ts + timedelta(hours=DAILY_RESET_HOURS)).timestamp()
        daily_timer.set(next_reset)

        # 7) Evento enriquecido — una copia para BQ, otra para Firestore.
        # `steps_delta` ahora es el valor **permitido** (post-cap), para que
        # Firestore y BQ cuadren con "qué computó realmente el jugador".
        yield {
            "player_id": player_id,
            "ts": evt["ts"],
            "latitude": lat,
            "longitude": lon,
            "steps_delta": pasos_permitidos,
            "distance_m": round(distance_m, 2),
            "speed_kmh": round(speed_kmh, 3),
            "env_multiplier": round(env_factor, 3),
            # `rappel_applied` se retiró del scoring (v3.2). Conservamos la
            # columna en BQ para no romper el schema existente, siempre False.
            "rappel_applied": False,
            "armies_earned": armies_earned,
            "armies_today_after": today_so_far + armies_earned,
            "capped": capped,
            "processed_at": now_utc_iso(),
        }

    @on_timer(DAILY_RESET_TIMER)
    def _on_daily_reset(
        self,
        armies_today=beam.DoFn.StateParam(ARMIES_TODAY_STATE),
        steps_today=beam.DoFn.StateParam(STEPS_TODAY_STATE),
    ):
        # Reset de los contadores diarios. No emitimos ningún evento al hacerlo
        # (el siguiente evento real ya refleja el reset).
        armies_today.clear()
        steps_today.clear()


# ─── Firestore sink ───────────────────────────────────────────────────────────
class WriteFirestoreDoFn(beam.DoFn):
    """UPSERT con Increment a user_balance/ y users/. Ignora filas con 0
    armies_earned para no tocar Firestore sin motivo."""
    def setup(self):
        from google.cloud import firestore  # noqa: F401
        self.fs_module = firestore
        self.db = firestore.Client()

    def process(self, row):
        if int(row.get("armies_earned", 0)) <= 0:
            yield row
            return

        firestore = self.fs_module
        pid = row["player_id"]
        steps = int(row.get("steps_delta", 0))
        armies = int(row["armies_earned"])

        # Contrato del equipo
        self.db.collection("user_balance").document(pid).set({
            "armies":      firestore.Increment(armies),
            "total_steps": firestore.Increment(steps),
            "last_scored_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

        # Contrato del backend CloudRISK — lo lee el frontend
        self.db.collection("users").document(pid).set({
            "steps_total":  firestore.Increment(steps),
            "power_points": firestore.Increment(int(steps * float(row.get("env_multiplier", 1.0)))),
            "gold":         firestore.Increment(steps // 100),
            "last_scored_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

        yield row


# ─── Pipeline ─────────────────────────────────────────────────────────────────
def build_pipeline(opts):
    pipeline_options = PipelineOptions(
        runner=opts.runner,
        project=opts.project,
        region=opts.region,
        temp_location=opts.temp_location,
        staging_location=opts.staging_location,
        streaming=True,
        save_main_session=True,
    )
    pipeline_options.view_as(StandardOptions).streaming = True

    with beam.Pipeline(options=pipeline_options) as p:
        # ── Rama ambiental (fan-in de 2 subs + parse + sink + side input) ─
        air_raw = p | "ReadAir" >> beam.io.ReadFromPubSub(subscription=opts.airq_sub)
        weather_raw = p | "ReadWeather" >> beam.io.ReadFromPubSub(subscription=opts.weather_sub)
        env_raw = (air_raw, weather_raw) | "MergeEnv" >> beam.Flatten()

        env_parsed = (
            env_raw
            | "WindowEnv60s" >> beam.WindowInto(window.FixedWindows(60))
            | "ParseEnv" >> beam.ParDo(ParseEnvironment()).with_outputs(
                ParseEnvironment.DLQ, main="rows"
            )
        )
        env_rows = env_parsed.rows
        env_dlq = env_parsed[ParseEnvironment.DLQ]

        if getattr(opts, 'local', False):
            env_rows | "LogEnvLocal" >> beam.Map(
                lambda r: logging.info("[ENV] type=%s mult=%.3f", r.get("type"), r.get("multiplier", 0))
            )
        else:
            env_rows | "WriteEnvBQ" >> beam.io.WriteToBigQuery(
                opts.env_table,
                schema=ENV_SCHEMA,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                method=beam.io.WriteToBigQuery.Method.STREAMING_INSERTS,
            )

        # Side input: un único float con el producto aire×clima más reciente,
        # actualizado en ventanas globales con triggers repetidos cada 30s.
        env_side = (
            env_rows
            | "ExtractMult" >> beam.ParDo(ExtractMultiplier())
            | "GlobalWindowEnv" >> beam.WindowInto(
                window.GlobalWindows(),
                trigger=trigger.Repeatedly(trigger.AfterProcessingTime(30)),
                accumulation_mode=trigger.AccumulationMode.ACCUMULATING,
            )
            | "CombineLatestMult" >> beam.CombineGlobally(LatestMultiplierCombineFn()).without_defaults()
        )

        # ── Rama jugadores ─────────────────────────────────────────────────
        player_parsed = (
            p
            | "ReadPlayer" >> beam.io.ReadFromPubSub(subscription=opts.player_sub)
            | "ParsePlayer" >> beam.ParDo(ParseMovement()).with_outputs(
                ParseMovement.DLQ, main="rows"
            )
        )
        player_rows = player_parsed.rows
        player_dlq = player_parsed[ParseMovement.DLQ]

        scored = (
            player_rows
            | "ScoringStateful" >> beam.ParDo(
                StatefulScoringDoFn(
                    max_speed_kmh=opts.max_speed_kmh,
                    power_per_steps=opts.power_per_steps,
                    daily_cap=opts.daily_army_cap,
                    daily_steps_cap=opts.daily_steps_cap,
                ),
                env_mult=beam.pvalue.AsSingleton(env_side),
            ).with_outputs(StatefulScoringDoFn.DLQ, main="rows")
        )
        scoring_rows = scored.rows
        scoring_dlq = scored[StatefulScoringDoFn.DLQ]

        # Sink 1: Firestore UPSERT
        firestore_written = scoring_rows | "WriteFirestore" >> beam.ParDo(WriteFirestoreDoFn())

        # Sink 2: BigQuery scoring histórico
        if getattr(opts, 'local', False):
            firestore_written | "LogScoringLocal" >> beam.Map(
                lambda r: logging.info("[SCORING] player=%s steps=%s armies=%s",
                                       r.get("player_id"), r.get("steps_delta"), r.get("armies_earned"))
            )
        else:
            firestore_written | "WriteScoringBQ" >> beam.io.WriteToBigQuery(
                opts.scoring_table,
                schema=SCORING_SCHEMA,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                method=beam.io.WriteToBigQuery.Method.STREAMING_INSERTS,
            )

        # ── Rama DLQ (todos los orígenes → una sola tabla) ─────────────────
        all_dlq = (env_dlq, player_dlq, scoring_dlq) | "MergeDLQ" >> beam.Flatten()
        if getattr(opts, 'local', False):
            all_dlq | "LogDLQLocal" >> beam.Map(
                lambda r: logging.warning("[DLQ] %s: %s — %s", r.get("source"), r.get("reason"), r.get("player_id"))
            )
        else:
            all_dlq | "WriteDLQ" >> beam.io.WriteToBigQuery(
                opts.dlq_table,
                schema=DLQ_SCHEMA,
                create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                method=beam.io.WriteToBigQuery.Method.STREAMING_INSERTS,
            )
            all_dlq | "LogDLQ" >> beam.Map(
                lambda r: logging.warning("[DLQ] %s: %s", r.get("source"), r.get("reason"))
            )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--runner", default="DirectRunner")
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="europe-west1")
    parser.add_argument("--temp_location")
    parser.add_argument("--staging_location")

    parser.add_argument("--player_sub", required=True,
                        help="Ruta suscripción Pub/Sub de player-movements")
    parser.add_argument("--weather_sub", required=True)
    parser.add_argument("--airq_sub", required=True)

    parser.add_argument("--scoring_table", default="unused",
                        help="BQ table project:dataset.player_scoring_events")
    parser.add_argument("--env_table", default="unused",
                        help="BQ table project:dataset.environmental_factors")
    parser.add_argument("--dlq_table", default="unused",
                        help="BQ table project:dataset.dead_letter")

    parser.add_argument("--max_speed_kmh", type=float, default=DEFAULT_MAX_SPEED_KMH)
    parser.add_argument("--power_per_steps", type=int, default=DEFAULT_POWER_PER_STEPS)
    parser.add_argument("--daily_army_cap", type=int, default=DEFAULT_DAILY_ARMY_CAP)
    parser.add_argument("--daily_steps_cap", type=int, default=DEFAULT_DAILY_STEPS_CAP)
    parser.add_argument("--local", action="store_true",
                        help="Skip BigQuery sinks (no BQ emulator). Logs output instead.")

    args, _ = parser.parse_known_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build_pipeline(args)


if __name__ == "__main__":
    main()
