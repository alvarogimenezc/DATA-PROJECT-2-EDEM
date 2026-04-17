"""
CloudRISK — Environmental Factors Streaming Pipeline
Reads from two Pub/Sub topics (`air-quality`, `weather`) and writes a
unified row per message to BigQuery `cloudrisk.environmental_factors`.

BigQuery schema:
    ts            TIMESTAMP   REQUIRED   when the ingestor measured
    type          STRING      REQUIRED   "air_quality" | "weather"
    multiplier    FLOAT       REQUIRED   contract range [0.6, 1.5]
    raw_payload   STRING                 original JSON envelope
    processed_at  TIMESTAMP   REQUIRED   when this pipeline wrote the row

Runners:
    DirectRunner    → local dev (runs in this process, single-thread)
    DataflowRunner  → production (auto-scaled managed cluster)

DirectRunner (dev):
    python pipelines/ambiental_a_bq.py \\
        --runner=DirectRunner \\
        --project=cloudrisk-492619 \\
        --air_subscription=projects/cloudrisk-492619/subscriptions/air-quality-sub \\
        --weather_subscription=projects/cloudrisk-492619/subscriptions/weather-sub \\
        --output_table=cloudrisk-492619:cloudrisk.environmental_factors \\
        --streaming

DataflowRunner (prod):
    python pipelines/ambiental_a_bq.py \\
        --runner=DataflowRunner \\
        --project=cloudrisk-492619 \\
        --region=europe-west1 \\
        --temp_location=gs://cloudrisk-492619-dataflow/tmp \\
        --staging_location=gs://cloudrisk-492619-dataflow/staging \\
        --air_subscription=... --weather_subscription=... \\
        --output_table=cloudrisk-492619:cloudrisk.environmental_factors \\
        --streaming

EDEM. Master Big Data & Cloud 2025/2026
Professor: Javi Briones & Adriana Campos
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions

BQ_SCHEMA = {
    "fields": [
        {"name": "ts",            "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "type",          "type": "STRING",    "mode": "REQUIRED"},
        {"name": "multiplier",    "type": "FLOAT",     "mode": "REQUIRED"},
        {"name": "raw_payload",   "type": "STRING",    "mode": "REQUIRED"},
        {"name": "processed_at",  "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
}


class ParseAndShape(beam.DoFn):
    """Decode a Pub/Sub message, extract the multiplier, and shape the BQ row.

    Handles both message types in a single transform — the input is a bytes
    payload, the output is a dict matching BQ_SCHEMA. Bad messages are
    routed to the `dead_letter` side output instead of failing the bundle.
    """
    DEAD_LETTER = "dead_letter"

    def process(self, element):
        try:
            payload = json.loads(element.decode("utf-8"))
        except Exception as exc:
            yield beam.pvalue.TaggedOutput(self.DEAD_LETTER, {
                "raw": element[:500].decode("utf-8", errors="replace"),
                "error": f"json decode: {exc}",
            })
            return

        msg_type = payload.get("type")
        if msg_type == "air_quality":
            mult = payload.get("indice_multiplicador_aire")
        elif msg_type == "weather":
            mult = payload.get("indice_multiplicador_tiempo")
        else:
            yield beam.pvalue.TaggedOutput(self.DEAD_LETTER, {
                "raw": json.dumps(payload),
                "error": f"unsupported type: {msg_type!r}",
            })
            return

        if mult is None:
            yield beam.pvalue.TaggedOutput(self.DEAD_LETTER, {
                "raw": json.dumps(payload),
                "error": "missing multiplier field",
            })
            return

        yield {
            "ts": payload.get("ts") or datetime.now(timezone.utc).isoformat(),
            "type": msg_type,
            "multiplier": float(mult),
            "raw_payload": json.dumps(payload),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }


def build_pipeline(opts: argparse.Namespace) -> None:
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
        air = (
            p
            | "ReadAir"   >> beam.io.ReadFromPubSub(subscription=opts.air_subscription)
            | "TagAir"    >> beam.Map(lambda b: b)
        )
        weather = (
            p
            | "ReadWeather" >> beam.io.ReadFromPubSub(subscription=opts.weather_subscription)
            | "TagWeather"  >> beam.Map(lambda b: b)
        )

        merged = (air, weather) | "MergeStreams" >> beam.Flatten()

        # Windowing: group messages into 60-second fixed windows BEFORE the
        # WriteToBigQuery sink. For streaming inserts this is technically
        # optional, but without it any transform that expects bounded work
        # per window (GroupByKey, Combine) will fail, and Dataflow can't
        # checkpoint cleanly. 60s is our heartbeat rate — one window per
        # minute is a reasonable default.
        windowed = merged | "FixedWindow60s" >> beam.WindowInto(
            beam.window.FixedWindows(60)
        )

        parsed = windowed | "ParseAndShape" >> beam.ParDo(ParseAndShape()).with_outputs(
            ParseAndShape.DEAD_LETTER, main="rows"
        )

        rows = parsed.rows
        dlq = parsed[ParseAndShape.DEAD_LETTER]

        rows | "WriteBQ" >> beam.io.WriteToBigQuery(
            opts.output_table,
            schema=BQ_SCHEMA,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
            method=beam.io.WriteToBigQuery.Method.STREAMING_INSERTS,
        )

        # Stream dead-letter messages to stdout (tiny in practice)
        dlq | "LogDLQ" >> beam.Map(lambda r: logging.warning("[DLQ] %s", r))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runner", default="DirectRunner",
                        help="DirectRunner (local) or DataflowRunner (GCP).")
    parser.add_argument("--project", required=True, help="GCP project id.")
    parser.add_argument("--region", default="europe-west1")
    parser.add_argument("--temp_location", help="gs://... required for DataflowRunner.")
    parser.add_argument("--staging_location", help="gs://... required for DataflowRunner.")
    parser.add_argument("--air_subscription", required=True,
                        help="Pub/Sub subscription for air_quality messages.")
    parser.add_argument("--weather_subscription", required=True,
                        help="Pub/Sub subscription for weather messages.")
    parser.add_argument("--output_table", required=True,
                        help="BigQuery output table: project:dataset.table or dataset.table")
    args, _ = parser.parse_known_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build_pipeline(args)


if __name__ == "__main__":
    main()
