from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
SNAPSHOT_PATH = ROOT / "dashboard" / "data" / "dashboard_snapshot.json"

RESELL_SIGNALS = {"RESELL_TEST"}
WATCH_SIGNALS = {"WATCH_ONLY"}
NEEDS_EVIDENCE_SIGNALS = {
    "INSUFFICIENT_EXIT_REFERENCE",
    "REVALIDATE_SOURCE",
    "VERIFY_VARIANT",
    "VERIFY_CONDITION_LANGUAGE",
    "POSSIBLE_ARBITRAGE",
}

SCORE_FIELDS = {
    "PCS": ("eu_price_confidence_score", "eu_price_confidence_label"),
    "LQS": ("eu_liquidity_score", "liquidity_label"),
    "ECS": ("exit_confidence_score", "exit_confidence_label"),
    "BOS": ("bridge_opportunity_score", "bridge_opportunity_label"),
}

GATE_NAME_MAP = {
    "EU-PCS": "PCS",
    "EU-LQS": "LQS",
    "PCS": "PCS",
    "LQS": "LQS",
    "ECS": "ECS",
    "BOS": "BOS",
}

SCORE_LABEL_RED = {
    "VERY_LOW",
    "LOW",
    "ILLIQUID",
    "WEAK",
    "WEAK_OR_UNSUPPORTED",
    "UNSUPPORTED",
}
SCORE_LABEL_AMBER = {"MEDIUM", "MIXED", "MODERATE"}
SCORE_LABEL_GREEN = {
    "HIGH",
    "VERY_HIGH",
    "LIQUID",
    "STRONG",
    "STRONG_OR_SUPPORTED",
    "SUPPORTED",
}


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


def read_snapshot(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "null"}:
        return None
    return text


def format_eur(value) -> str:
    amount = as_float(value)
    return "—" if amount is None else f"€{amount:,.2f}"


def format_pct(value) -> str:
    amount = as_float(value)
    return "—" if amount is None else f"{amount:,.1f}%"


def format_score(value) -> str:
    amount = as_float(value)
    return "—" if amount is None else f"{amount:.0f}"


def short_name(value) -> str:
    text = clean_text(value) or "Unknown card"
    return text.split(" [", 1)[0]


def card_context(row: dict) -> str:
    bits = []
    expansion = clean_text(row.get("expansion_name"))
    number = clean_text(row.get("number"))
    if expansion:
        bits.append(expansion)
    if number:
        bits.append(f"#{number}")
    if bits:
        return " · ".join(bits)
    pid = clean_text(row.get("id_product"))
    return f"Cardmarket ID {pid}" if pid else "Exact set/number not available in snapshot"


def signal_label(signal: str | None) -> str:
    signal = str(signal or "").upper()
    labels = {
        "RESELL_TEST": "🟢 RESELL TEST",
        "WATCH_ONLY": "🟡 WATCH",
        "REVALIDATE_SOURCE": "🟠 REVALIDATE",
        "INSUFFICIENT_EXIT_REFERENCE": "🔵 NEEDS EXIT DATA",
        "VERIFY_VARIANT": "🔵 VERIFY VARIANT",
        "VERIFY_CONDITION_LANGUAGE": "🔵 VERIFY CONDITION/LANGUAGE",
        "NO_EDGE": "⚪ NO EDGE",
        "STRONG_ARBITRAGE": "🟢 STRONG ARBITRAGE",
        "POSSIBLE_ARBITRAGE": "🟡 POSSIBLE ARBITRAGE",
    }
    return labels.get(signal, signal.replace("_", " ") if signal else "UNKNOWN")


def signal_rank(signal: str | None) -> int:
    # Display order only. It does not change or manufacture any scanner signal.
    signal = str(signal or "").upper()
    if signal in RESELL_SIGNALS or signal == "STRONG_ARBITRAGE":
        return 0
    if signal in WATCH_SIGNALS:
        return 1
    if signal in NEEDS_EVIDENCE_SIGNALS:
        return 2
    if signal == "NO_EDGE":
        return 4
    return 3


def route_sort_key(row: dict):
    return (
        signal_rank(row.get("route_signal")),
        -(as_float(row.get("deal_score")) or -999999),
        -(as_float(row.get("net_roi_pct")) or -999999),
    )


def human_channel(value) -> str:
    channel = clean_text(value)
    if not channel:
        return "No validated exit"
    known = {
        "CARDTRADER_ZERO": "CardTrader Zero",
        "CARDTRADER_DIRECT": "CardTrader Direct",
        "EBAY": "eBay",
        "EBAY_IE": "eBay Ireland",
        "EBAY_EU": "eBay EU",
        "CARDMARKET": "Cardmarket",
        "ADVERTS": "Adverts",
        "GUMTREE": "Gumtree",
    }
    return known.get(channel.upper(), channel.replace("_", " ").title())


def score_from(row: dict, primary: str, fallback: str | None = None):
    value = row.get(primary)
    if value not in (None, ""):
        return value
    return row.get(fallback) if fallback else None


def parse_gate_failures(reason: str | None) -> dict[str, tuple[float, float]]:
    failures: dict[str, tuple[float, float]] = {}
    text = clean_text(reason)
    if not text:
        return failures
    for raw in text.split(";"):
        match = re.search(r"([A-Z-]+)\s*([0-9.]+)\s*<\s*([0-9.]+)", raw.strip().upper())
        if not match:
            continue
        metric = GATE_NAME_MAP.get(match.group(1))
        if metric:
            failures[metric] = (float(match.group(2)), float(match.group(3)))
    return failures


def score_badge(metric: str, row: dict) -> str:
    field, label_field = SCORE_FIELDS[metric]
    if metric == "LQS":
        value = score_from(row, field, "liquidity_score")
    else:
        value = row.get(field)
    number = as_float(value)
    if number is None:
        return f"⚪ {metric} —"

    label = (clean_text(row.get(label_field)) or "").upper()
    failures = parse_gate_failures(row.get("quality_gate_reason"))

    if label in SCORE_LABEL_RED:
        icon = "🔴"
    elif label in SCORE_LABEL_AMBER:
        icon = "🟠"
    elif label in SCORE_LABEL_GREEN:
        icon = "🟢"
    elif metric in failures:
        actual, threshold = failures[metric]
        icon = "🟠" if threshold - actual <= 10 else "🔴"
    else:
        icon = "⚪"

    return f"{icon} {metric} {number:.0f}"


def eu_position_text(row: dict) -> str | None:
    buy = as_float(row.get("best_validated_buy_eur"))
    fair = as_float(row.get("eu_fair_value_eur"))
    if buy is None or fair is None or fair <= 0:
        return None
    pct = ((buy / fair) - 1.0) * 100.0
    if abs(pct) < 2:
        return "Buy is roughly in line with EU fair value."
    if pct > 0:
        return f"Buy is {pct:.1f}% above EU fair value — this is not an EU-discount play."
    return f"Buy is {abs(pct):.1f}% below EU fair value."


def plain_gate_explanation(row: dict) -> str | None:
    signal = str(row.get("route_signal") or "").upper()
    failures = parse_gate_failures(row.get("quality_gate_reason"))

    intro = {
        "INSUFFICIENT_EXIT_REFERENCE": "No sufficiently strong exit reference yet.",
        "REVALIDATE_SOURCE": "The acquisition source needs revalidation.",
        "VERIFY_VARIANT": "The exact printing or variant still needs verification.",
        "VERIFY_CONDITION_LANGUAGE": "Condition or language still needs verification.",
        "WATCH_ONLY": "The scanner keeps this on WATCH.",
        "POSSIBLE_ARBITRAGE": "The opportunity is not strong enough to be treated as confirmed arbitrage.",
    }.get(signal)

    phrases = []
    for metric in ("LQS", "PCS", "ECS", "BOS"):
        if metric not in failures:
            continue
        actual, threshold = failures[metric]
        label = {
            "LQS": "liquidity",
            "PCS": "price confidence",
            "ECS": "exit confidence",
            "BOS": "bridge support",
        }[metric]
        phrases.append(f"{label} is below its route gate ({actual:.0f} vs {threshold:.0f})")

    if intro and phrases:
        return f"{intro} " + "; ".join(phrases) + "."
    if intro:
        return intro
    if phrases:
        return "; ".join(phrases).capitalize() + "."

    raw = clean_text(row.get("quality_gate_reason"))
    return raw


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


def latest_outcomes(conn: sqlite3.Connection, pid: int) -> list[dict]:
    if not table_exists(conn, "model_outcomes"):
        return []
    rows = conn.execute(
        """
        SELECT snapshot_date, horizon_days, target_scope, window_start, window_end,
               forecast_value_eur, realised_value_eur, observation_count,
               evidence_quality, outcome_source, error_pct, abs_error_pct,
               entry_return_pct, success_flag
        FROM model_outcomes
        WHERE id_product=? AND realised_value_eur IS NOT NULL
        ORDER BY snapshot_date DESC, horizon_days, target_scope
        LIMIT 100
        """,
        (pid,),
    ).fetchall()
    return [dict(r) for r in rows]


def route_summary_rows(rows: list[dict]) -> list[dict]:
    result = []
    for row in sorted(rows, key=route_sort_key):
        result.append(
            {
                "Card": short_name(row.get("name")),
                "Signal": signal_label(row.get("route_signal")),
                "Buy": as_float(row.get("best_validated_buy_eur")),
                "EU fair": as_float(row.get("eu_fair_value_eur")),
                "Exit route": human_channel(row.get("best_sell_channel")),
                "Modelled net exit": as_float(row.get("best_sell_net_eur")),
                "Modelled net profit": as_float(row.get("net_spread_eur")),
                "ROI %": as_float(row.get("net_roi_pct")),
                "PCS": as_float(row.get("eu_price_confidence_score")),
                "LQS": as_float(score_from(row, "eu_liquidity_score", "liquidity_score")),
                "ECS": as_float(row.get("exit_confidence_score")),
                "BOS": as_float(row.get("bridge_opportunity_score")),
            }
        )
    return result


def discovery_summary_rows(rows: list[dict]) -> list[dict]:
    result = []
    for row in rows:
        result.append(
            {
                "Card": short_name(row.get("name")),
                "Scanner status": clean_text(row.get("status")) or "—",
                "Candidate buy": as_float(row.get("best_validated_sourcing_price")),
                "30d average": as_float(row.get("avg30")),
                "Gap %": as_float(row.get("gap_pct")),
                "Deal score": as_float(row.get("deal_score")),
                "CT sellers": as_float(row.get("ct_visible_sellers")),
            }
        )
    return result


def render_score_line(row: dict) -> None:
    badges = [score_badge(metric, row) for metric in ("PCS", "LQS", "ECS", "BOS")]
    st.markdown(" · ".join(f"**{badge}**" for badge in badges))


def render_route_card(row: dict) -> None:
    with st.container(border=True):
        st.markdown(f"#### {short_name(row.get('name'))}")
        st.caption(card_context(row))
        st.markdown(f"**{signal_label(row.get('route_signal'))}**")

        exit_channel = human_channel(row.get("best_sell_channel"))
        st.markdown(f"**Exit route:** {exit_channel}")

        p1, p2 = st.columns(2)
        p1.metric("Validated buy", format_eur(row.get("best_validated_buy_eur")))
        p2.metric("EU fair value", format_eur(row.get("eu_fair_value_eur")))

        p3, p4 = st.columns(2)
        p3.metric("Modelled net exit", format_eur(row.get("best_sell_net_eur")))
        p4.metric("Modelled net profit", format_eur(row.get("net_spread_eur")))

        st.markdown(f"**Modelled ROI:** {format_pct(row.get('net_roi_pct'))}")

        position = eu_position_text(row)
        if position:
            st.caption(position)

        render_score_line(row)

        explanation = plain_gate_explanation(row)
        if explanation:
            st.markdown(f"**Why not actionable:** {explanation}")

        raw_reason = clean_text(row.get("quality_gate_reason"))
        if raw_reason:
            with st.expander("Show numeric gate detail"):
                st.code(raw_reason)


st.set_page_config(page_title="Pokémon Deal Scanner", page_icon="🃏", layout="wide")

cfg = load_cfg()
db_path = resolve_path(cfg, cfg["paths"]["database"])
output_dir = resolve_path(cfg, cfg["paths"]["output_dir"])
snapshot = read_snapshot(SNAPSHOT_PATH)
conn: sqlite3.Connection | None = None

if db_path.exists():
    # Local/developer mode: inspect the current scanner database and outputs directly.
    conn = open_readonly(db_path)
    predictions = latest_predictions(conn)
    routes = read_csv(output_dir / "market_routes.csv")
    discovery = read_csv(output_dir / "top_flips.csv")[:75]
    maturity = matured_stats(conn)
    sync = latest_sync_state(conn)
    outcomes_by_card: dict[str, list[dict]] = {}
    data_mode = "Local read-only SQLite"
    data_updated = predictions[0]["snapshot_date"] if predictions else "unknown"
    scanner_version = str(cfg.get("version") or "unknown")
elif snapshot:
    # Hosted mode: no API credentials and no mutable scanner database.
    predictions = list(snapshot.get("latest_predictions") or [])
    routes = list(snapshot.get("market_routes") or [])
    discovery = list(snapshot.get("discovery_candidates") or [])
    maturity = dict(snapshot.get("maturity") or {})
    sync = list(snapshot.get("source_sync_state") or [])
    outcomes_by_card = dict(snapshot.get("latest_outcomes_by_card") or {})
    data_mode = "Hosted public snapshot"
    data_updated = str(snapshot.get("generated_at_utc") or "unknown")
    scanner_version = str(snapshot.get("scanner_version") or cfg.get("version") or "unknown")
else:
    st.error("No scanner database or hosted dashboard snapshot is available yet.")
    st.info(
        "Run the daily scanner once; GitHub Actions will then publish the dashboard snapshot automatically."
    )
    st.stop()

for key in ("t7", "t7_cards", "t30", "t30_cards"):
    maturity[key] = int(maturity.get(key) or 0)

st.title("Pokémon Deal Scanner")
st.caption(
    f"v{scanner_version} · read-only decision dashboard · "
    "all prices, scores and route signals come from the scanner"
)
st.caption(f"Data mode: **{data_mode}** · Updated: **{data_updated}**")

tab_today, tab_card, tab_health = st.tabs(["Today", "Card detail", "Model health"])

with tab_today:
    route_signals = [str(r.get("route_signal") or "").upper() for r in routes]
    resell_count = sum(s in RESELL_SIGNALS or s == "STRONG_ARBITRAGE" for s in route_signals)
    watch_count = sum(s in WATCH_SIGNALS for s in route_signals)
    needs_count = sum(s in NEEDS_EVIDENCE_SIGNALS for s in route_signals)

    latest_date = predictions[0].get("snapshot_date", "—") if predictions else "—"
    st.markdown(f"### {latest_date} market review")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Resell tests",
        resell_count,
        help="Existing scanner RESELL_TEST / STRONG_ARBITRAGE signals.",
    )
    c2.metric("Watch", watch_count, help="Existing scanner WATCH_ONLY signals.")
    c3.metric(
        "Needs evidence",
        needs_count,
        help="Routes blocked pending stronger evidence or revalidation.",
    )
    c4.metric(
        "Discovery queue",
        len(discovery),
        help="Pre-route sourcing candidates from top_flips.csv.",
    )

    st.caption(
        "The dashboard does not promote or downgrade cards. These buckets only present the "
        "existing v0.12 signals in a more readable way."
    )

    st.divider()
    st.subheader("Priority review")

    non_edge_signals = sorted({s for s in route_signals if s and s != "NO_EDGE"})
    f1, f2, f3 = st.columns([2, 2, 3])
    selected_signals = f1.multiselect(
        "Signals",
        options=non_edge_signals,
        default=non_edge_signals,
        format_func=signal_label,
    )
    price_bands = sorted(
        {clean_text(r.get("price_band")) for r in routes if clean_text(r.get("price_band"))}
    )
    selected_bands = f2.multiselect("Price bands", options=price_bands, default=price_bands)
    search_text = (
        f3.text_input("Find card", placeholder="e.g. Dragonite, Pikachu, Charizard")
        .strip()
        .lower()
    )

    priority = []
    for row in routes:
        signal = str(row.get("route_signal") or "").upper()
        if signal == "NO_EDGE":
            continue
        if selected_signals and signal not in selected_signals:
            continue
        band = clean_text(row.get("price_band"))
        if selected_bands and band not in selected_bands:
            continue
        if search_text and search_text not in str(row.get("name") or "").lower():
            continue
        priority.append(row)
    priority.sort(key=route_sort_key)

    if priority:
        for start in range(0, min(len(priority), 6), 3):
            cols = st.columns(3)
            for offset, row in enumerate(priority[start : start + 3]):
                with cols[offset]:
                    render_route_card(row)
        if len(priority) > 6:
            st.caption(f"Showing the first 6 of {len(priority)} filtered routes.")
    else:
        st.info("No current routed cards match these filters.")

    st.divider()
    st.subheader("Discovery queue")
    st.caption(
        "Broader sourcing candidates from `top_flips.csv`. These are **pre-route discovery** "
        "signals, not final resale recommendations. Identity, landed-cost and market-quality "
        "gates still apply before a route can become actionable."
    )
    if discovery:
        discovery_view = discovery
        if search_text:
            discovery_view = [
                row
                for row in discovery
                if search_text in str(row.get("name") or "").lower()
            ]
        st.dataframe(
            discovery_summary_rows(discovery_view[:50]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Candidate buy": st.column_config.NumberColumn(format="€%.2f"),
                "30d average": st.column_config.NumberColumn(format="€%.2f"),
                "Gap %": st.column_config.NumberColumn(format="%.1f%%"),
                "Deal score": st.column_config.NumberColumn(format="%.1f"),
                "CT sellers": st.column_config.NumberColumn(format="%.0f"),
            },
        )
        if len(discovery_view) > 50:
            st.caption(f"Showing the first 50 of {len(discovery_view)} discovery candidates.")
    else:
        st.info("No discovery candidates are included in this dashboard snapshot yet.")

    with st.expander("All routed cards"):
        show_no_edge = st.checkbox("Include NO_EDGE", value=False)
        table_routes = [
            row
            for row in routes
            if show_no_edge or str(row.get("route_signal") or "").upper() != "NO_EDGE"
        ]
        if search_text:
            table_routes = [
                row
                for row in table_routes
                if search_text in str(row.get("name") or "").lower()
            ]

        if table_routes:
            st.dataframe(
                route_summary_rows(table_routes),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Buy": st.column_config.NumberColumn(format="€%.2f"),
                    "EU fair": st.column_config.NumberColumn(format="€%.2f"),
                    "Modelled net exit": st.column_config.NumberColumn(format="€%.2f"),
                    "Modelled net profit": st.column_config.NumberColumn(format="€%.2f"),
                    "ROI %": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )
        else:
            st.info("No routed cards to display.")

    with st.expander("Immutable forecasts · audit view"):
        st.caption(
            "Daily frozen forecasts used by the validation/experience-store layer. "
            "This is audit data rather than the primary deal view."
        )
        if predictions:
            preferred = [
                "id_product",
                "name",
                "expansion_name",
                "number",
                "route_signal",
                "best_validated_buy_eur",
                "eu_fair_value_eur",
                "us_fair_value_eur",
                "best_sell_channel",
                "best_sell_net_eur",
                "deal_score",
                "eu_price_confidence_score",
                "eu_liquidity_score",
                "exit_confidence_score",
                "bridge_opportunity_score",
            ]
            available = set(predictions[0])
            cols = [c for c in preferred if c in available]
            audit_rows = [{c: row.get(c) for c in cols} for row in predictions]
            st.dataframe(audit_rows, use_container_width=True, hide_index=True)
        else:
            st.info("No immutable model_predictions have been frozen yet.")

with tab_card:
    if not predictions:
        st.info("No card forecasts available yet.")
    else:
        label_to_pid = {}
        for row in predictions:
            label = f"{short_name(row.get('name'))} — {card_context(row)}"
            label_to_pid[label] = int(row["id_product"])
        selected = st.selectbox("Card", list(label_to_pid))
        pid = label_to_pid[selected]
        card = next(r for r in predictions if int(r["id_product"]) == pid)

        st.subheader(short_name(card.get("name")))
        st.caption(card_context(card))

        matching_routes = [r for r in routes if str(r.get("id_product")) == str(pid)]
        route = matching_routes[0] if matching_routes else card

        c1, c2, c3, c4 = st.columns(4)
        eu_fair = as_float(card.get("eu_fair_value_eur"))
        buy = as_float(card.get("best_validated_buy_eur"))
        deal = as_float(card.get("deal_score"))
        c1.metric("EU fair value", f"€{eu_fair:.2f}" if eu_fair is not None else "—")
        c2.metric("Validated buy", f"€{buy:.2f}" if buy is not None else "—")
        c3.metric("Deal score", f"{deal:.1f}" if deal is not None else "—")
        c4.metric("Route", signal_label(card.get("route_signal")))

        st.markdown(f"**Exit route:** {human_channel(card.get('best_sell_channel'))}")
        render_score_line(route)

        position = eu_position_text(route)
        if position:
            st.caption(position)

        explanation = plain_gate_explanation(route)
        if explanation:
            st.markdown(f"**Decision explanation:** {explanation}")

        if matching_routes:
            st.subheader("Current route evidence")
            st.dataframe(
                route_summary_rows(matching_routes),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Buy": st.column_config.NumberColumn(format="€%.2f"),
                    "EU fair": st.column_config.NumberColumn(format="€%.2f"),
                    "Modelled net exit": st.column_config.NumberColumn(format="€%.2f"),
                    "Modelled net profit": st.column_config.NumberColumn(format="€%.2f"),
                    "ROI %": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )
            with st.expander("Raw route fields"):
                st.dataframe(matching_routes, use_container_width=True, hide_index=True)

        outcomes = (
            latest_outcomes(conn, pid)
            if conn is not None
            else list(outcomes_by_card.get(str(pid)) or [])
        )
        st.subheader("Matured outcomes")
        if outcomes:
            st.dataframe(outcomes, use_container_width=True, hide_index=True)
        else:
            st.caption("No matured outcomes for this card in the current dashboard dataset.")

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
    if sync:
        st.dataframe(sync, use_container_width=True, hide_index=True)
    else:
        st.info("No source_sync_state records found.")

    st.subheader("Dashboard architecture")
    st.write(
        {
            "mode": data_mode,
            "scanner_version": scanner_version,
            "pricing_logic_in_ui": False,
            "mutations_allowed": False,
            "hosted_snapshot": "dashboard/data/dashboard_snapshot.json",
        }
    )

if conn is not None:
    conn.close()
