from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"


def load_cfg() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def resolve_path(cfg: dict, configured: str) -> Path:
    path = Path(configured)
    return path if path.is_absolute() else ROOT / path


def open_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    ).fetchone()
    return row is not None


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def latest_predictions(conn: sqlite3.Connection) -> list[dict]:
    if not table_exists(conn, "model_predictions"):
        return []
    latest = conn.execute("SELECT MAX(snapshot_date) AS d FROM model_predictions").fetchone()["d"]
    if not latest:
        return []
    rows = conn.execute(
        """
        SELECT
          p.snapshot_date, p.id_product, pr.name, pr.expansion_name, pr.number,
          p.model_version, p.eu_fair_value_eur, p.eu_price_confidence_score,
          p.eu_liquidity_score, p.us_fair_value_eur, p.us_price_confidence_score,
          p.us_liquidity_score, p.exit_confidence_score, p.bridge_opportunity_score,
          p.best_validated_buy_eur, p.best_sell_channel, p.best_sell_net_eur,
          p.route_signal, p.deal_score
        FROM model_predictions p
        LEFT JOIN products pr ON pr.id_product = p.id_product
        WHERE p.snapshot_date=?
        ORDER BY COALESCE(p.deal_score, -999999) DESC, p.id_product
        """,
        (latest,),
    ).fetchall()
    return [dict(r) for r in rows]


def matured_stats(conn: sqlite3.Connection) -> dict:
    if not table_exists(conn, "model_outcomes"):
        return {"t7": 0, "t7_cards": 0, "t30": 0, "t30_cards": 0}
    row = conn.execute(
        """
        SELECT
          SUM(CASE WHEN horizon_days=7 AND realised_value_eur IS NOT NULL THEN 1 ELSE 0 END) AS t7,
          COUNT(DISTINCT CASE WHEN horizon_days=7 AND realised_value_eur IS NOT NULL THEN id_product END) AS t7_cards,
          SUM(CASE WHEN horizon_days=30 AND realised_value_eur IS NOT NULL THEN 1 ELSE 0 END) AS t30,
          COUNT(DISTINCT CASE WHEN horizon_days=30 AND realised_value_eur IS NOT NULL THEN id_product END) AS t30_cards
        FROM model_outcomes
        """
    ).fetchone()
    return {k: int(row[k] or 0) for k in ("t7", "t7_cards", "t30", "t30_cards")}


def latest_sync_state(conn: sqlite3.Connection) -> list[dict]:
    if not table_exists(conn, "source_sync_state"):
        return []
    rows = conn.execute(
        "SELECT source, value, updated_at FROM source_sync_state ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def choose_columns(rows: list[dict], preferred: list[str]) -> list[dict]:
    if not rows:
        return []
    available = set(rows[0])
    cols = [c for c in preferred if c in available]
    if not cols:
        cols = list(rows[0])[:12]
    return [{c: row.get(c) for c in cols} for row in rows]


def top_routes(rows: list[dict]) -> list[dict]:
    actionable = [
        row for row in rows
        if str(row.get("route_signal") or "").upper() not in {"", "NO_EDGE"}
    ]
    actionable.sort(
        key=lambda r: (
            as_float(r.get("deal_score")) or -999999,
            as_float(r.get("net_roi_pct")) or -999999,
        ),
        reverse=True,
    )
    return actionable[:50]


st.set_page_config(page_title="Pokémon Deal Scanner", page_icon="🃏", layout="wide")
st.title("Pokémon Deal Scanner")
st.caption("Read-only v0.12 dashboard — display layer only; scanner rules remain authoritative.")

cfg = load_cfg()
db_path = resolve_path(cfg, cfg["paths"]["database"])
output_dir = resolve_path(cfg, cfg["paths"]["output_dir"])

try:
    conn = open_readonly(db_path)
except FileNotFoundError:
    st.error(f"Database not found: {db_path}")
    st.info("Run the scanner first, then refresh this page.")
    st.stop()

predictions = latest_predictions(conn)
routes = read_csv(output_dir / "market_routes.csv")
maturity = matured_stats(conn)

tab_today, tab_card, tab_health = st.tabs(["Today", "Card detail", "Model health"])

with tab_today:
    latest_date = predictions[0]["snapshot_date"] if predictions else "—"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latest forecast", latest_date)
    c2.metric("Cards forecast", len(predictions))
    c3.metric("Actionable routes", len(top_routes(routes)))
    c4.metric("Matured T+7", maturity["t7"])

    st.subheader("Best current opportunities")
    best = top_routes(routes)
    if best:
        preferred = [
            "id_product", "name", "expansion_name", "number", "route_signal",
            "best_validated_buy_eur", "eu_fair_value_eur", "best_sell_channel",
            "best_sell_net_eur", "net_spread_eur", "net_roi_pct",
            "deal_score", "eu_price_confidence_score", "liquidity_score",
            "exit_confidence_score", "bridge_opportunity_score",
            "ct_lag_label", "manual_verification_required",
        ]
        st.dataframe(choose_columns(best, preferred), use_container_width=True, hide_index=True)
    else:
        st.info("No actionable rows found in output/market_routes.csv.")

    st.subheader("Latest immutable forecasts")
    if predictions:
        preferred = [
            "id_product", "name", "expansion_name", "number", "route_signal",
            "best_validated_buy_eur", "eu_fair_value_eur", "us_fair_value_eur",
            "best_sell_channel", "best_sell_net_eur", "deal_score",
            "eu_price_confidence_score", "eu_liquidity_score",
            "exit_confidence_score", "bridge_opportunity_score",
        ]
        st.dataframe(choose_columns(predictions, preferred), use_container_width=True, hide_index=True)
    else:
        st.info("No immutable model_predictions have been frozen yet.")

with tab_card:
    if not predictions:
        st.info("No card forecasts available yet.")
    else:
        label_to_pid = {}
        for row in predictions:
            label = (
                f'{row.get("name") or "Unknown"} — {row.get("expansion_name") or "?"} '
                f'#{row.get("number") or "?"} [{row["id_product"]}]'
            )
            label_to_pid[label] = row["id_product"]
        selected = st.selectbox("Card", list(label_to_pid))
        pid = label_to_pid[selected]
        card = next(r for r in predictions if r["id_product"] == pid)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "EU fair value",
            f'€{card["eu_fair_value_eur"]:.2f}' if card["eu_fair_value_eur"] is not None else "—",
        )
        c2.metric(
            "Validated buy",
            f'€{card["best_validated_buy_eur"]:.2f}' if card["best_validated_buy_eur"] is not None else "—",
        )
        c3.metric("Deal score", f'{card["deal_score"]:.1f}' if card["deal_score"] is not None else "—")
        c4.metric("Route", card["route_signal"] or "—")

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("EU PCS", card["eu_price_confidence_score"] if card["eu_price_confidence_score"] is not None else "—")
        s2.metric("EU LQS", card["eu_liquidity_score"] if card["eu_liquidity_score"] is not None else "—")
        s3.metric("ECS", card["exit_confidence_score"] if card["exit_confidence_score"] is not None else "—")
        s4.metric("BOS", card["bridge_opportunity_score"] if card["bridge_opportunity_score"] is not None else "—")

        matching_routes = [r for r in routes if str(r.get("id_product")) == str(pid)]
        if matching_routes:
            st.subheader("Current route evidence")
            st.dataframe(matching_routes, use_container_width=True, hide_index=True)

        if table_exists(conn, "model_outcomes"):
            outcomes = conn.execute(
                """
                SELECT horizon_days, target_scope, window_start, window_end,
                       forecast_value_eur, realised_value_eur, observation_count,
                       evidence_quality, outcome_source, error_pct, abs_error_pct,
                       entry_return_pct, success_flag
                FROM model_outcomes
                WHERE id_product=?
                ORDER BY snapshot_date DESC, horizon_days, target_scope
                LIMIT 100
                """,
                (pid,),
            ).fetchall()
            st.subheader("Matured outcomes")
            if outcomes:
                st.dataframe([dict(r) for r in outcomes], use_container_width=True, hide_index=True)
            else:
                st.caption("No matured outcomes for this card yet.")

with tab_health:
    st.subheader("Experience-store maturity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("T+7 observations", f'{maturity["t7"]} / 500')
    c2.metric("T+7 unique cards", f'{maturity["t7_cards"]} / 100')
    c3.metric("T+30 observations", f'{maturity["t30"]} / 200')
    c4.metric("T+30 unique cards", f'{maturity["t30_cards"]} / 50')

    st.progress(
        min(1.0, maturity["t7"] / 500 if 500 else 0.0),
        text="Comparable-experience Gate B: T+7 observation progress",
    )
    st.caption(
        "Comparable-experience retrieval remains deferred until the leakage-safe maturity gates in "
        "docs/EXPERIENCE_STORE.md are satisfied."
    )

    st.subheader("Source sync state")
    sync = latest_sync_state(conn)
    if sync:
        st.dataframe(sync, use_container_width=True, hide_index=True)
    else:
        st.info("No source_sync_state records found.")

    st.subheader("Files")
    st.write({
        "database": str(db_path),
        "market_routes": str(output_dir / "market_routes.csv"),
        "dashboard_mode": "read-only",
        "scanner_version": str(cfg.get("version") or "unknown"),
    })

conn.close()
