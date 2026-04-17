"""
CloudRISK — Streamlit Dashboard (Cloud Run)
Real-time KPIs and charts from BigQuery metrics.
"""

import os
import streamlit as st
import pandas as pd
from google.cloud import bigquery
from pathlib import Path
import json
import requests

PROJECT_ID = os.environ.get("PROJECT_ID", "cloudrisk-local")
DATASET = os.environ.get("BIGQUERY_DATASET", "cloudrisk_metrics")
ENV_DATASET = os.environ.get("ENV_DATASET", "cloudrisk")
ENV_TABLE = os.environ.get("ENV_TABLE", "environmental_factors")
METRICS_SOURCE = os.environ.get("METRICS_SOURCE", "bigquery").lower()
LOCAL_METRICS_DIR = Path(os.environ.get("LOCAL_METRICS_DIR", "/metrics"))
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")

_bq_client: bigquery.Client | None = None


def get_bq_client() -> bigquery.Client:
    global _bq_client
    if _bq_client is not None:
        return _bq_client
    _bq_client = bigquery.Client(project=PROJECT_ID)
    return _bq_client


def query(sql: str) -> pd.DataFrame:
    return get_bq_client().query(sql).to_dataframe()


def _read_local_jsonl(prefix: str) -> pd.DataFrame:
    files = sorted(LOCAL_METRICS_DIR.glob(f"{prefix}*.jsonl"))
    if not files:
        return pd.DataFrame()
    rows: list[dict] = []
    for fp in files:
        try:
            with fp.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            continue
    return pd.DataFrame(rows)


st.set_page_config(page_title="CloudRISK Dashboard", page_icon="⚔️", layout="wide")
st.title("⚔️ CloudRISK — Dashboard")
st.caption(f"Project: `{PROJECT_ID}` · Dataset: `{DATASET}`")
if METRICS_SOURCE == "local":
    st.info(f"Local metrics mode: reading JSONL from `{LOCAL_METRICS_DIR}`")

# ── KPIs ──
col1, col2, col3, col4 = st.columns(4)

try:
    if METRICS_SOURCE == "local":
        step_df = _read_local_jsonl("step_events")
        total_users = int(step_df["user_id"].nunique()) if "user_id" in step_df else 0
    else:
        total_users = query(
            f"SELECT COUNT(DISTINCT user_id) AS n FROM `{PROJECT_ID}.{DATASET}.step_events`"
        )["n"].iloc[0]
except Exception:
    total_users = 0

try:
    if METRICS_SOURCE == "local":
        if "step_df" not in locals():
            step_df = _read_local_jsonl("step_events")
        total_steps = int(step_df["steps"].fillna(0).sum()) if "steps" in step_df else 0
    else:
        total_steps = query(
            f"SELECT SUM(steps) AS n FROM `{PROJECT_ID}.{DATASET}.step_events`"
        )["n"].iloc[0] or 0
except Exception:
    total_steps = 0

try:
    if METRICS_SOURCE == "local":
        battle_df = _read_local_jsonl("battle_events")
        if {"battle_id", "event_type"}.issubset(set(battle_df.columns)):
            active_battles = int((battle_df["event_type"] == "battle_started").sum())
        else:
            active_battles = 0
    else:
        active_battles = query(
            f"SELECT COUNT(DISTINCT battle_id) AS n FROM `{PROJECT_ID}.{DATASET}.battle_events` WHERE event_type = 'battle_started'"
        )["n"].iloc[0]
except Exception:
    active_battles = 0

try:
    if METRICS_SOURCE == "local":
        loc_df = _read_local_jsonl("location_events")
        if "zone_id" in loc_df:
            zones_visited = int(loc_df["zone_id"].dropna().nunique())
        else:
            zones_visited = 0
    else:
        zones_visited = query(
            f"SELECT COUNT(DISTINCT zone_id) AS n FROM `{PROJECT_ID}.{DATASET}.location_events` WHERE zone_id IS NOT NULL"
        )["n"].iloc[0]
except Exception:
    zones_visited = 0

col1.metric("Total Players", f"{total_users:,}")
col2.metric("Total Steps", f"{int(total_steps):,}")
col3.metric("Battles Started", f"{active_battles:,}")
col4.metric("Zones Visited", f"{zones_visited:,}")

st.divider()

# ── Steps per player chart ──
st.subheader("Steps per Player")
try:
    if METRICS_SOURCE == "local":
        if "step_df" not in locals():
            step_df = _read_local_jsonl("step_events")
        if step_df.empty:
            raise RuntimeError("No local step events yet")
        steps_df = (
            step_df.groupby("user_id", as_index=False)["steps"]
            .sum()
            .rename(columns={"steps": "total_steps"})
            .sort_values("total_steps", ascending=False)
            .head(20)
        )
        st.bar_chart(steps_df.set_index("user_id"))
    else:
        steps_df = query(f"""
            SELECT user_id, SUM(steps) AS total_steps
            FROM `{PROJECT_ID}.{DATASET}.step_events`
            GROUP BY user_id
            ORDER BY total_steps DESC
            LIMIT 20
        """)
        st.bar_chart(steps_df.set_index("user_id"))
except Exception as e:
    st.info(f"No step data available yet: {e}")

# ── Recent location events ──
st.subheader("Recent Location Events")
try:
    if METRICS_SOURCE == "local":
        loc_df = _read_local_jsonl("location_events")
        if loc_df.empty:
            raise RuntimeError("No local location events yet")
        keep = [c for c in ["user_id", "lat", "lng", "zone_name", "timestamp"] if c in loc_df.columns]
        locations_df = loc_df[keep].tail(50).iloc[::-1]
        st.dataframe(locations_df, use_container_width=True)
    else:
        locations_df = query(f"""
            SELECT user_id, lat, lng, zone_name, timestamp
            FROM `{PROJECT_ID}.{DATASET}.location_events`
            ORDER BY timestamp DESC
            LIMIT 50
        """)
        st.dataframe(locations_df, use_container_width=True)
except Exception as e:
    st.info(f"No location data available yet: {e}")

# ── Battle log ──
st.subheader("Battle Events")
try:
    if METRICS_SOURCE == "local":
        battle_df = _read_local_jsonl("battle_events")
        if battle_df.empty:
            raise RuntimeError("No local battle events yet")
        keep = [c for c in ["event_type", "battle_id", "zone_id", "attacker_power", "defender_power", "timestamp"] if c in battle_df.columns]
        battles_df = battle_df[keep].tail(20).iloc[::-1]
        st.dataframe(battles_df, use_container_width=True)
    else:
        battles_df = query(f"""
            SELECT event_type, battle_id, zone_id, attacker_power, defender_power, timestamp
            FROM `{PROJECT_ID}.{DATASET}.battle_events`
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        st.dataframe(battles_df, use_container_width=True)
except Exception as e:
    st.info(f"No battle data available yet: {e}")

# ── Environmental multipliers (live + history) ──
st.divider()
st.subheader("🌬️ Environmental factors — air × weather")
st.caption(f"Live snapshot from `{BACKEND_URL}/api/v1/multipliers`. History from `{ENV_DATASET}.{ENV_TABLE}`.")

# Live snapshot (cheap HTTP call to the backend)
mcols = st.columns(3)
try:
    snap = requests.get(f"{BACKEND_URL}/api/v1/multipliers/", timeout=2).json()
    mcols[0].metric("Aire (live)",     f"×{snap['air']:.2f}")
    mcols[1].metric("Clima (live)",    f"×{snap['weather']:.2f}")
    mcols[2].metric("Combinado (live)", f"×{snap['combined']:.2f}",
                    delta="boost" if snap['combined'] > 1.0 else ("penalty" if snap['combined'] < 1.0 else "neutral"))
except Exception as e:
    mcols[0].info(f"Backend not reachable for live snapshot: {e}")

# Historical chart from BigQuery (only when METRICS_SOURCE=bigquery and table exists)
if METRICS_SOURCE != "local":
    try:
        hist = query(f"""
            SELECT TIMESTAMP_TRUNC(ts, MINUTE) AS minute,
                   type,
                   AVG(multiplier) AS multiplier
            FROM `{PROJECT_ID}.{ENV_DATASET}.{ENV_TABLE}`
            WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 6 HOUR)
            GROUP BY minute, type
            ORDER BY minute
        """)
        if hist.empty:
            st.info("No environmental rows in BigQuery yet — make sure the Beam pipeline is running.")
        else:
            pivoted = hist.pivot(index="minute", columns="type", values="multiplier").ffill()
            st.line_chart(pivoted)
            st.caption(f"Last 6 h — {len(hist)} samples across {pivoted.shape[1]} types.")
    except Exception as e:
        st.info(f"BigQuery {ENV_DATASET}.{ENV_TABLE} unavailable: {e}")
else:
    st.info("Set METRICS_SOURCE=bigquery and configure ENV_DATASET/ENV_TABLE to see the multiplier history chart.")
