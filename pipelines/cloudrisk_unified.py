#ETL en Streaming (Extraer, Transformar y Cargar en tiempo real)
# 1. Recibe los pasos de los jugadores, la contaminación y el clima en tiempo real.
# 2. Calcula la velocidad del jugador para detectar trampas (si va en coche).
# 3. Aplica límites de seguridad (máximo de pasos y ejércitos por día).
# 4. Transforma los pasos en ejércitos usando la fórmula ambiental.
# 5. Guarda los resultados en Firestore (para el juego en vivo) y BigQuery (historial).
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

#Bloques 1 y 2 -> definen las reglas del universo y preparan los "moldes" donde se guardará la información.

#REGLAS DEL JUEGO. Se definen los límites y multiplicadores que se aplican al juego.  
DEFAULT_POWER_PER_STEPS = int(os.environ.get("POWER_PER_STEPS", "500")) # 500 pasos = 1 ejército base
DEFAULT_DAILY_ARMY_CAP = int(os.environ.get("DAILY_ARMY_CAP", "50")) # Máximo 50 ejércitos al día
DEFAULT_MAX_SPEED_KMH = float(os.environ.get("MAX_SPEED_KMH", "15")) # Más de 15km/h = Trampa (va en bici/coche)
DEFAULT_DAILY_STEPS_CAP = int(os.environ.get("DAILY_STEPS_CAP", "30000")) # Máximo 30.000 pasos al día

DEFAULT_ENV_MULTIPLIER = 1.0 # Si fallan las APIs de clima, multiplicador neutro por defecto

DAILY_RESET_HOURS = 24.0 # Cada 24 horas se resetean los límites a cero


#MOLDES PARA LA BASE DE DATOS (ESQUEMAS BQ)
#Le decimos a BigQuery qué forma tienen las tablas para que no rechace los datos.

#Cómo tienen que guardarse los puntos válidos de los jugadores (pasos, velocidad, ejércitos ganados)
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
#Cómo tiene que guardarse el histórico del clima y el aire (temperatura, nivel de contaminación)
ENV_SCHEMA = {
    "fields": [
        {"name": "ts",           "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "type",         "type": "STRING",    "mode": "REQUIRED"},
        {"name": "multiplier",   "type": "FLOAT",     "mode": "REQUIRED"},
        {"name": "raw_payload",  "type": "STRING",    "mode": "REQUIRED"},
        {"name": "processed_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
}
# El contenedor de errores y trampas. Si alguien hace trampas o un archivo JSON viene roto, 
# el dato se envía a este esquema con un campo "reason" que explica por qué fue rechazado.
DLQ_SCHEMA = {
    "fields": [
        {"name": "source",       "type": "STRING",    "mode": "REQUIRED"},
        {"name": "reason",       "type": "STRING",    "mode": "REQUIRED"},
        {"name": "player_id",    "type": "STRING",    "mode": "NULLABLE"},
        {"name": "raw_payload",  "type": "STRING",    "mode": "REQUIRED"},
        {"name": "processed_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
}


# CALCULADORA. Helpers.Funciones para medir distancias en el mapa y arreglar fechas.
# Funciones independientes que hacen cálculos rápidos o arreglan textos.
# Al no depender de Google Dataflow, son muy fáciles de testear.

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
# Fórmula  para calcular metros reales entre dos coordenadas GPS.
    r = 6_371_000.0  # radio Tierra en metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

#Devuelve la hora actual exacta en formato estándar internacional (UTC).
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_ts(ts_str: str) -> datetime:
# Asegura que todas las horas del juego estén en formato estándar.
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return datetime.now(timezone.utc)


def dlq_record(source: str, reason: str, player_id, raw_payload: str) -> dict:
# Crea la etiqueta para mandar un evento corrupto a la tabla de errores (DLQ).
    return {
        "source": source,
        "reason": reason,
        "player_id": player_id,
        "raw_payload": raw_payload,
        "processed_at": now_utc_iso(),
    }


# ─── Clases Parse DoFns ───TRADUCTOR DE MENSAJES
#Cogen el texto crudo de Pub/Sub y lo convierten en diccionarios Python.


class ParseMovement(beam.DoFn):
#Traduce los pasos. Si no tiene 'player_id', lo tira a la basura (DLQ).
    DLQ = "dlq"
    #Intenta leer el JSON.
    def process(self, raw: bytes):
        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception as exc:
        ##Si el texto es ilegible, crea un recibo de error y tíralo a la DLQ
            yield beam.pvalue.TaggedOutput(self.DLQ, dlq_record(
                source="player-movements",
                reason=f"json_decode: {exc}",
                player_id=None,
                raw_payload=raw[:500].decode("utf-8", errors="replace"),
            ))
            return
        #Comprueba que tiene el player_id. Si no, crea un recibo de error y tíralo a la DLQ
        pid = msg.get("player_id")
        if not pid:
            yield beam.pvalue.TaggedOutput(self.DLQ, dlq_record(
                source="player-movements",
                reason="missing_player_id",
                player_id=None,
                raw_payload=json.dumps(msg),
            ))
            return
        #Si todo va bien, devuelve un diccionario con los campos necesarios para el scoring y el raw original por si acaso.
        yield (pid, {
            "player_id": pid,
            "ts": msg.get("timestamp") or msg.get("ts") or now_utc_iso(),
            "latitude": float(msg["latitude"]) if msg.get("latitude") is not None else None,
            "longitude": float(msg["longitude"]) if msg.get("longitude") is not None else None,
            "steps_delta": int(msg.get("steps_delta", msg.get("steps", 0))),
            "raw": msg,
        })


class ParseEnvironment(beam.DoFn):
# Traduce los datos del clima y del aire. Extrae los multiplicadores matemáticos
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
        # El mensaje debe tener un campo "type" que indique si es clima o calidad del aire 
        # para buscar su multiplicador correspondiente. Si no, a la DLQ con un recibo de error.
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

        # Para BQ environmental_factors. Prepara la fila perfecta para guardarla en el historial de BigQuery.
        yield {
            "ts":           msg.get("ts") or now_utc_iso(),
            "type":         mtype,
            "multiplier":   float(mult),
            "raw_payload":  json.dumps(msg),
            "processed_at": now_utc_iso(),
        }


class ExtractMultiplier(beam.DoFn):
# Solo extrae el tipo y el número del multiplicador
    # para usarlo más adelante en las matemáticas de los ejércitos.
    def process(self, row):
        yield (row["type"], float(row["multiplier"]))


# FUSIÓN DE FACTORES AMBIENTALES. Calcula el multiplicador final multiplicando Aire x Clima.
class LatestMultiplierCombineFn(beam.CombineFn):
# Coge el último dato de clima y aire que ha llegado y los multiplica.

    #1.Empieza asumiendo que el clima y el aire son normales (multiplicador 1.0) hasta que lleguen datos reales.
    def create_accumulator(self):
        return {"air_quality": 1.0, "weather": 1.0}
    #2.ACTUALIZAR MEMORIA: Cuando llega un dato nuevo, sobrescribe solo ese tipo.
    def add_input(self, acc, inp):
        kind, mult = inp
        if kind in acc:
            acc[kind] = mult
        return acc
    # 3. SINCRONIZAR SERVIDORES: Si Dataflow está usando varios ordenadores a la vez,
        # junta las memorias de todos en un solo diccionario maestro.
    def merge_accumulators(self, accs):
        out = {"air_quality": 1.0, "weather": 1.0}
        for a in accs:
            for k, v in a.items():
                if k in out:
                    out[k] = v
        return out
    #4.EL RESULTADO: Multiplica el último aire conocido por el último clima conocido.
    def extract_output(self, acc):
        return float(acc.get("air_quality", 1.0)) * float(acc.get("weather", 1.0))


# ─── Es el único sitio que tiene "memoria" por cada jugador de forma individual.
# Esto (Stateful Processing) permite saber a qué velocidad va un usuario 
# comparando su ubicación actual con la anterior que teníamos guardada.

# 1. Creamos los "Casilleros de Memoria" individuales para cada jugador
LAST_POS_STATE = ReadModifyWriteStateSpec("last_pos", beam.coders.PickleCoder())
ARMIES_TODAY_STATE = CombiningValueStateSpec("armies_today", beam.coders.VarIntCoder(), sum)
STEPS_TODAY_STATE = CombiningValueStateSpec("steps_today", beam.coders.VarIntCoder(), sum)
DAILY_RESET_TIMER = TimerSpec("daily_reset", TimeDomain.REAL_TIME)


class StatefulScoringDoFn(beam.DoFn):
# Recibe los pasos de un jugador, revisa trampas, calcula puntos y guarda progreso.
    DLQ = "dlq"
    # Cargamos las reglas del juego al arrancar el Juez
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
    # Compara dónde estaba el jugador antes y ahora para sacar la velocidad.
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
    # Convierte pasos en ejércitos asegurándose de no pasar del límite de 50 diarios.
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

        # PASO 1) Mirar la memoria y calcular la velocidad.
        prev = last_pos.read()
        distance_m, speed_kmh = self._calculate_speed_kmh(prev, lat, lon, ev_ts)

        # PASO 2) JUEZ ANTI-TRAMPA: Si va muy rápido, descartamos el evento entero.
        if speed_kmh > self.max_speed_kmh:
            yield beam.pvalue.TaggedOutput(self.DLQ, dlq_record(
                source="player-movements",
                reason=f"anti_cheat_speed:{speed_kmh:.2f}kmh>{self.max_speed_kmh}",
                player_id=player_id,
                raw_payload=json.dumps(evt.get("raw", {})),
            ))
            return

        # 3) Límite de 30.000 pasos. Si los supera, corta el grifo.
        pasos_hoy = int(steps_today.read() or 0)
        pasos_restantes_cap = max(0, self.daily_steps_cap - pasos_hoy)
        pasos_permitidos = min(steps, pasos_restantes_cap)
        steps_capped = pasos_permitidos < steps

        # 4) Calcula los ejércitos ganados con la ayuda del clima.
        env_factor = float(env_mult) if env_mult is not None else DEFAULT_ENV_MULTIPLIER
        today_so_far = int(armies_today.read() or 0)
        armies_earned, armies_capped = self._compute_armies(
            pasos_permitidos, env_factor, today_so_far,
        )
      
        capped = armies_capped or steps_capped

        # 5) Actualiza la memoria interna del jugador para el próximo evento.
        last_pos.write({"lat": lat, "lon": lon, "ts": ev_ts})
        if pasos_permitidos > 0:
            steps_today.add(pasos_permitidos)
        if armies_earned > 0:
            armies_today.add(armies_earned)

        # 6) Configura la alarma para reiniciar los límites a 0 dentro de 24h.
        next_reset = (ev_ts + timedelta(hours=DAILY_RESET_HOURS)).timestamp()
        daily_timer.set(next_reset)

        # 7) Genera el recibo final para enviar a la base de datos.
        yield {
            "player_id": player_id,
            "ts": evt["ts"],
            "latitude": lat,
            "longitude": lon,
            "steps_delta": pasos_permitidos,
            "distance_m": round(distance_m, 2),
            "speed_kmh": round(speed_kmh, 3),
            "env_multiplier": round(env_factor, 3),
            "rappel_applied": False,
            "armies_earned": armies_earned,
            "armies_today_after": today_so_far + armies_earned,
            "capped": capped,
            "processed_at": now_utc_iso(),
        }

    @on_timer(DAILY_RESET_TIMER)
    # Suena la alarma de 24h: borramos el progreso diario del jugador para que vuelva a 0.
    def _on_daily_reset(
        self,
        armies_today=beam.DoFn.StateParam(ARMIES_TODAY_STATE),
        steps_today=beam.DoFn.StateParam(STEPS_TODAY_STATE),
    ):

        armies_today.clear()
        steps_today.clear()



# BLOQUE 7: ACTUALIZACIÓN DEL JUEGO EN VIVO (FIRESTORE SINK)
# Coge los puntos válidos calculados por el Juez y los sube a Firestore.
# Esto hace que la pantalla del móvil del jugador se actualice por arte de magia.
class WriteFirestoreDoFn(beam.DoFn):
    ## Suma los ejércitos nuevos a los que ya tenía el jugador en el móvil.UPSERT con Increment a user_balance/ y users/. 
    # Ignora filas con 0 armies_earned para no tocar Firestore sin motivo.
    def setup(self):
        #Nos conectamos a la base de datos de Firestore al arrancar
        from google.cloud import firestore  # noqa: F401
        self.fs_module = firestore
        self.db = firestore.Client()

    def process(self, row):
        # Si por culpa del clima o los límites diarios ha ganado 0 ejércitos,
        # no hacemos nada para ahorrar dinero en lecturas/escrituras de la nube.
        if int(row.get("armies_earned", 0)) <= 0:
            yield row
            return

        firestore = self.fs_module
        pid = row["player_id"]
        steps = int(row.get("steps_delta", 0))
        armies = int(row["armies_earned"])

        # 1. Actualizamos el saldo de ejércitos para poder atacar en el mapa
        # Usamos 'Increment' para sumar de forma segura sin borrar otras transacciones
        self.db.collection("user_balance").document(pid).set({
            "armies":      firestore.Increment(armies),
            "total_steps": firestore.Increment(steps),
            "last_scored_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

        # 2. Actualizamos el perfil público del jugador (Nivel, Puntos de Poder, Oro)
        self.db.collection("users").document(pid).set({
            "steps_total":  firestore.Increment(steps),
            "power_points": firestore.Increment(int(steps * float(row.get("env_multiplier", 1.0)))),
            "gold":         firestore.Increment(steps // 100),
            "last_scored_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

        yield row


# BLOQUE 8: LA CONSTRUCCIÓN DE LAS TUBERÍAS (PIPELINE)
# Aquí no hay matemáticas. Solo cogemos todas las piezas (DoFns) que 
# hemos programado arriba y las conectamos con flechas ( | >> ).
def build_pipeline(opts):
    # Configuramos el motor de Google Dataflow
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
        #----------------------------------------------------------------
        # Tubería 1: Leer Clima y Aire, fusionarlos y mandarlos a BigQuery
        #----------------------------------------------------------------
        # 1. Escuchamos las dos antenas a la vez
        air_raw = p | "ReadAir" >> beam.io.ReadFromPubSub(subscription=opts.airq_sub)
        weather_raw = p | "ReadWeather" >> beam.io.ReadFromPubSub(subscription=opts.weather_sub)
        env_raw = (air_raw, weather_raw) | "MergeEnv" >> beam.Flatten()
        # 2. Traducimos los mensajes cada 60 segundos
        env_parsed = (
            env_raw
            | "WindowEnv60s" >> beam.WindowInto(window.FixedWindows(60))
            | "ParseEnv" >> beam.ParDo(ParseEnvironment()).with_outputs(
                ParseEnvironment.DLQ, main="rows"
            )
        )
        env_rows = env_parsed.rows
        env_dlq = env_parsed[ParseEnvironment.DLQ]
        # 3. Mandamos una copia del clima al Historial de BigQuery
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

        # 4. Extraemos el multiplicador y lo dejamos en memoria para que el Juez lo use
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
        #----------------------------------------------------------------
        # Tubería 2: Leer Jugadores, pasar por el Juez y guardar puntos
        #----------------------------------------------------------------
        # 1. Leemos y traducimos los pasos de Pub/Sub
        player_parsed = (
            p
            | "ReadPlayer" >> beam.io.ReadFromPubSub(subscription=opts.player_sub)
            | "ParsePlayer" >> beam.ParDo(ParseMovement()).with_outputs(
                ParseMovement.DLQ, main="rows"
            )
        )
        player_rows = player_parsed.rows
        player_dlq = player_parsed[ParseMovement.DLQ]
         # 2. Pasamos los pasos por el Cerebro Central (El Juez)
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

        # 3. Firestore UPSERT. Guardar puntos en Firestore (Juego en Vivo)
        firestore_written = scoring_rows | "WriteFirestore" >> beam.ParDo(WriteFirestoreDoFn())

        # 4. Guardar puntos en BigQuery (Historial Analítico)
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

        #----------------------------------------------------------------
        # Tubería 3: Recoger la basura (DLQ) (todos los orígenes → una sola tabla) ─────────────────
        #----------------------------------------------------------------

        #Juntamos los errores de clima, de traducción de pasos y de tramposos en un solo tubo
        all_dlq = (env_dlq, player_dlq, scoring_dlq) | "MergeDLQ" >> beam.Flatten()
        if getattr(opts, 'local', False):
            all_dlq | "LogDLQLocal" >> beam.Map(
                lambda r: logging.warning("[DLQ] %s: %s — %s", r.get("source"), r.get("reason"), r.get("player_id"))
            )
        else:
        ##Lo mandamos todo a la tabla del Basurero en BigQuery
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

# ====================================================================
# BOTÓN DE ARRANQUE (MAIN)
# Recoge la configuración que escribes en la terminal y enciende el motor.
# ====================================================================
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
    # ¡Enciende las tuberías!


if __name__ == "__main__":
    main()
