from __future__ import annotations

import csv
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
SNAPSHOT_PATH = ROOT / "dashboard" / "data" / "dashboard_snapshot.json"
TRACKED_REVIEW_PATH = ROOT / "data" / "reference" / "tracked_review_cards.csv"
OWNED_LEDGER_PATH = ROOT / "data" / "reference" / "owned_resale_cards.csv"
OWNED_MARKET_PATH = ROOT / "dashboard" / "data" / "owned_market.json"
CARD_IMAGE_PATH = ROOT / "dashboard" / "data" / "card_images.json"
PROVIDER_USAGE_PATH = ROOT / "dashboard" / "data" / "provider_usage.csv"
PROVIDER_LIMITS_PATH = ROOT / "data" / "reference" / "provider_limits.csv"

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
GATE_NAME_MAP = {"EU-PCS": "PCS", "EU-LQS": "LQS", "PCS": "PCS", "LQS": "LQS", "ECS": "ECS", "BOS": "BOS"}
SCORE_LABEL_RED = {"VERY_LOW", "LOW", "ILLIQUID", "WEAK", "WEAK_OR_UNSUPPORTED", "UNSUPPORTED"}
SCORE_LABEL_AMBER = {"MEDIUM", "MIXED", "MODERATE"}
SCORE_LABEL_GREEN = {"HIGH", "VERY_HIGH", "LIQUID", "STRONG", "STRONG_OR_SUPPORTED", "SUPPORTED"}


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
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)).fetchone()
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


def provider_usage_summary(rows: list[dict], limits: list[dict]) -> list[dict]:
    now = datetime.now().astimezone()
    limit_map = {str(r.get("provider")): r for r in limits}
    providers = sorted({str(r.get("provider")) for r in rows if r.get("provider")} | set(limit_map))
    result = []
    for provider in providers:
        provider_rows = [r for r in rows if str(r.get("provider")) == provider]
        def within_days(days: int) -> list[dict]:
            cutoff = now.timestamp() - days * 86400
            selected = []
            for row in provider_rows:
                stamp = clean_text(row.get("observed_at_utc"))
                if not stamp:
                    continue
                try:
                    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if parsed.timestamp() >= cutoff:
                    selected.append(row)
            return selected
        month_rows = [r for r in provider_rows if str(r.get("snapshot_date") or "")[:7] == now.strftime("%Y-%m")]
        today_rows = [r for r in provider_rows if str(r.get("snapshot_date") or "") == now.strftime("%Y-%m-%d")]
        def total(selected: list[dict], field: str) -> float:
            return sum(as_float(r.get(field)) or 0 for r in selected)
        limit = as_float(limit_map.get(provider, {}).get("monthly_credit_limit"))
        month_credits = total(month_rows, "documented_credits")
        remaining = None if limit is None else max(0.0, limit - month_credits)
        result.append({
            "Provider": provider.replace("_", " ").title(),
            "Today requests": int(total(today_rows, "requests")),
            "7d requests": int(total(within_days(7), "requests")),
            "30d requests": int(total(within_days(30), "requests")),
            "Month credits": month_credits if provider_rows else None,
            "Monthly limit": limit,
            "Remaining": remaining if provider_rows else None,
            "Latest status": clean_text(provider_rows[-1].get("status")) if provider_rows else "NOT INSTRUMENTED",
        })
    return result


def load_card_images(path: Path) -> dict[str, dict]:
    payload = read_snapshot(path)
    cards = payload.get("cards") if isinstance(payload, dict) else None
    return {str(k): dict(v) for k, v in (cards or {}).items() if isinstance(v, dict)}


def card_image_url(row: dict, quality: str = "low") -> str | None:
    pid = str(row.get("id_product") or "").strip()
    record = CARD_IMAGES.get(pid) or {}
    base = clean_text(record.get("image_base"))
    return f"{base}/{quality}.webp" if base else None


def render_card_title(row: dict, heading: str = "####", image_width: int = 92, quality: str = "low") -> None:
    image_url = card_image_url(row, quality=quality)
    if image_url:
        image_col, text_col = st.columns([1, 3.2], vertical_alignment="top")
        with image_col:
            st.image(image_url, width=image_width)
        with text_col:
            st.markdown(f"{heading} {short_name(row.get('name'))}")
            st.caption(card_context(row))
    else:
        st.markdown(f"{heading} {short_name(row.get('name'))}")
        st.caption(card_context(row))


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value):
    number = as_float(value)
    return None if number is None else int(number)


def clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if not text or text.lower() in {"none", "nan", "null"} else text


def compact_timestamp(value) -> str:
    text = clean_text(value) or "unknown"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if "T" not in text:
        return parsed.strftime("%d %b %Y").lstrip("0")
    suffix = " UTC" if text.endswith("+00:00") or text.endswith("Z") else ""
    return parsed.strftime("%d %b %Y · %H:%M").lstrip("0") + suffix


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
    return (clean_text(value) or "Unknown card").split(" [", 1)[0]


def card_context(row: dict) -> str:
    bits = []
    if clean_text(row.get("expansion_name")):
        bits.append(f"Set: {row['expansion_name']}")
    if clean_text(row.get("number")):
        bits.append(f"No. {row['number']}")
    if clean_text(row.get("cardtrader_version")):
        bits.append(f"Variant: {row['cardtrader_version']}")
    if clean_text(row.get("rarity")):
        bits.append(f"Rarity: {row['rarity']}")
    pid = clean_text(row.get("id_product"))
    if pid:
        bits.append(f"Cardmarket ID {pid}")
    return " · ".join(bits) if bits else "Exact set/number not available in snapshot"


def acquisition_source_text(row: dict) -> str:
    explicit = (clean_text(row.get("screening_acquisition_source")) or "").upper()
    labels = {
        "CARDTRADER_EN_NM": "CardTrader — English/NM ask",
        "CARDMARKET_EN_NM": "Cardmarket — English/NM floor",
        "CARDMARKET_EN_NM+CARDTRADER_EN_NM": "Cardmarket + CardTrader — same English/NM floor",
        "CARDTRADER_EN_NM+CARDMARKET_EN_NM": "Cardmarket + CardTrader — same English/NM floor",
        "CARDMARKET_GENERIC_LOW": "Cardmarket — generic low (screening only)",
        "VALIDATED_EN_NM_SOURCE_UNRESOLVED": "Validated EN/NM source not retained",
    }
    if explicit in labels:
        return labels[explicit]
    buy = as_float(row.get("best_validated_sourcing_price"))
    cm = as_float(row.get("cm_en_nm_floor"))
    ct = as_float(row.get("ct_en_nm_floor"))
    if buy is not None:
        if ct is not None and abs(ct - buy) < 0.005 and not (cm is not None and abs(cm - buy) < 0.005):
            return "CardTrader — English/NM ask"
        if cm is not None and abs(cm - buy) < 0.005 and not (ct is not None and abs(ct - buy) < 0.005):
            return "Cardmarket — English/NM floor"
        if cm is not None and ct is not None and abs(cm - buy) < 0.005 and abs(ct - buy) < 0.005:
            return "Cardmarket + CardTrader — same English/NM floor"
    return "Source not retained in this snapshot"


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
    signal = str(signal or "").upper()
    if signal in RESELL_SIGNALS or signal == "STRONG_ARBITRAGE":
        return 0
    if signal in WATCH_SIGNALS:
        return 1
    if signal in NEEDS_EVIDENCE_SIGNALS:
        return 2
    return 4 if signal == "NO_EDGE" else 3


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
        if match and GATE_NAME_MAP.get(match.group(1)):
            failures[GATE_NAME_MAP[match.group(1)]] = (float(match.group(2)), float(match.group(3)))
    return failures


def score_badge(metric: str, row: dict) -> str:
    field, label_field = SCORE_FIELDS[metric]
    value = score_from(row, field, "liquidity_score") if metric == "LQS" else row.get(field)
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
    labels = {"LQS": "liquidity", "PCS": "price confidence", "ECS": "exit confidence", "BOS": "bridge support"}
    phrases = [f"{labels[m]} is below its route gate ({a:.0f} vs {t:.0f})" for m, (a, t) in failures.items()]
    if intro and phrases:
        return f"{intro} " + "; ".join(phrases) + "."
    if intro:
        return intro
    if phrases:
        return "; ".join(phrases).capitalize() + "."
    return clean_text(row.get("quality_gate_reason"))


def latest_predictions(conn: sqlite3.Connection) -> list[dict]:
    if not table_exists(conn, "model_predictions"):
        return []
    latest = conn.execute("SELECT MAX(snapshot_date) AS d FROM model_predictions").fetchone()["d"]
    if not latest:
        return []
    rows = conn.execute(
        """
        SELECT p.snapshot_date, p.id_product, pr.name, pr.expansion_name, pr.number,
               p.model_version, p.eu_fair_value_eur, p.eu_price_confidence_score,
               p.eu_liquidity_score, p.us_fair_value_eur, p.us_price_confidence_score,
               p.us_liquidity_score, p.exit_confidence_score, p.bridge_opportunity_score,
               p.best_validated_buy_eur, p.best_sell_channel, p.best_sell_net_eur,
               p.route_signal, p.deal_score
        FROM model_predictions p
        LEFT JOIN products pr ON pr.id_product=p.id_product
        WHERE p.snapshot_date=?
        ORDER BY COALESCE(p.deal_score, -999999) DESC, p.id_product
        """,
        (latest,),
    ).fetchall()
    return [dict(row) for row in rows]


def matured_stats(conn: sqlite3.Connection) -> dict:
    empty = {"t7": 0, "t7_cards": 0, "t30": 0, "t30_cards": 0}
    if not table_exists(conn, "model_outcomes"):
        return empty
    row = conn.execute(
        """
        SELECT
          SUM(CASE WHEN horizon_days=7 AND realised_value_eur IS NOT NULL THEN 1 ELSE 0 END),
          COUNT(DISTINCT CASE WHEN horizon_days=7 AND realised_value_eur IS NOT NULL THEN id_product END),
          SUM(CASE WHEN horizon_days=30 AND realised_value_eur IS NOT NULL THEN 1 ELSE 0 END),
          COUNT(DISTINCT CASE WHEN horizon_days=30 AND realised_value_eur IS NOT NULL THEN id_product END)
        FROM model_outcomes
        """
    ).fetchone()
    return {key: int(row[index] or 0) for index, key in enumerate(empty)}


def latest_sync_state(conn: sqlite3.Connection) -> list[dict]:
    if not table_exists(conn, "source_sync_state"):
        return []
    return [dict(r) for r in conn.execute("SELECT source, value, updated_at FROM source_sync_state ORDER BY updated_at DESC").fetchall()]


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


def by_product(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("id_product")): r for r in rows if r.get("id_product") not in (None, "")}


def merge_market_profile(routes: list[dict], signals: list[dict], quality: list[dict]) -> list[dict]:
    signal_map, quality_map = by_product(signals), by_product(quality)
    out = []
    for source in routes:
        row = dict(source)
        pid = str(row.get("id_product"))
        signal, q = signal_map.get(pid, {}), quality_map.get(pid, {})
        row["market_trend_label"] = signal.get("signal_label")
        row["market_trend_confidence"] = signal.get("confidence")
        row["market_trend_coverage_count"] = signal.get("coverage_count")
        for field in ("cm_short_momentum_pct", "cm_30d_change_pct", "cm_price_basis", "sales_7d", "sales_prev_23d", "sales_velocity_ratio", "active_supply_now", "active_supply_30d_ago", "supply_change_pct"):
            row[field] = signal.get(field)
        for field in ("eu_dispersion_pct", "us_dispersion_pct", "tcgplayer_sales_30d", "tcgplayer_sales_90d", "tcgplayer_avg_daily_sold", "tcgplayer_monthly_sales_equiv", "tcgplayer_current_quantity", "tcgplayer_current_sellers", "tcgplayer_supply_coverage_days", "tcgplayer_supply_state"):
            row[field] = q.get(field)
        out.append(row)
    return out


def route_summary_rows(rows: list[dict]) -> list[dict]:
    result = []
    for row in sorted(rows, key=route_sort_key):
        result.append({
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
        })
    return result


def discovery_summary_rows(rows: list[dict]) -> list[dict]:
    return [{
        "Card": short_name(row.get("name")),
        "Set": clean_text(row.get("expansion_name")) or "—",
        "No.": clean_text(row.get("number")) or "—",
        "Scanner status": clean_text(row.get("status")) or "—",
        "Candidate buy": as_float(row.get("best_validated_sourcing_price")),
        "Buy source": acquisition_source_text(row),
        "30d average": as_float(row.get("avg30")),
        "Gap %": as_float(row.get("gap_pct")),
        "Deal score": as_float(row.get("deal_score")),
        "CT sellers": as_float(row.get("ct_visible_sellers")),
    } for row in rows]


def market_trend_text(row: dict) -> str:
    label = (clean_text(row.get("market_trend_label")) or "NO TREND DATA").replace("_", " ")
    move = as_float(row.get("cm_30d_change_pct"))
    if move is not None:
        return f"{label} · {move:+.1f}% / 30d"
    short = as_float(row.get("cm_short_momentum_pct"))
    return f"{label} · short {short:+.1f}%" if short is not None else label


def trend_confidence_text(row: dict) -> str:
    confidence = (clean_text(row.get("market_trend_confidence")) or "UNKNOWN").replace("_", " ")
    coverage = as_int(row.get("market_trend_coverage_count"))
    return f"{confidence} · {coverage}/4 inputs" if coverage is not None else confidence


def velocity_text(row: dict) -> str:
    parts = []
    tcg30, tcg90 = as_int(row.get("tcgplayer_sales_30d")), as_int(row.get("tcgplayer_sales_90d"))
    if tcg30 is not None:
        parts.append(f"TCGplayer {tcg30}/30d")
    if tcg90 is not None:
        parts.append(f"{tcg90}/90d")
    s7, s23 = as_int(row.get("sales_7d")), as_int(row.get("sales_prev_23d"))
    if s7 is not None or s23 is not None:
        parts.append(f"tracked eBay signals {(s7 or 0) + (s23 or 0)}/30d")
    return " · ".join(parts) if parts else "No transaction-velocity evidence"


def supply_text(row: dict) -> str:
    parts = []
    cm_sellers, cm_units = as_int(row.get("cm_live_sellers")), as_int(row.get("cm_live_units"))
    if cm_sellers is not None:
        parts.append(f"Cardmarket {cm_sellers} EN/NM sellers" + (f" · {cm_units} units" if cm_units is not None else ""))
    ebay = as_int(row.get("active_supply_now"))
    if ebay is not None:
        parts.append(f"tracked eBay {ebay} live listings")
    tq, ts = as_int(row.get("tcgplayer_current_quantity")), as_int(row.get("tcgplayer_current_sellers"))
    if tq is not None or ts is not None:
        parts.append(f"TCGplayer {tq if tq is not None else '—'} units / {ts if ts is not None else '—'} sellers")
    return " · ".join(parts) if parts else "No exact live-supply evidence"


def dispersion_text(row: dict) -> str:
    parts = []
    eu, us = as_float(row.get("eu_dispersion_pct")), as_float(row.get("us_dispersion_pct"))
    if eu is not None:
        parts.append(f"EU {eu:.1f}%")
    if us is not None:
        parts.append(f"US {us:.1f}%")
    return " · ".join(parts) if parts else "No dispersion estimate"


def render_market_profile(row: dict, expanded: bool = False) -> None:
    with st.expander("Market profile", expanded=expanded):
        st.markdown(f"**Trend:** {market_trend_text(row)}")
        st.markdown(f"**Trend confidence:** {trend_confidence_text(row)}")
        st.markdown(f"**Transaction velocity:** {velocity_text(row)}")
        st.markdown(f"**Exact supply:** {supply_text(row)}")
        st.markdown(f"**Volatility / dispersion:** {dispersion_text(row)}")
        supply_state = clean_text(row.get("tcgplayer_supply_state"))
        coverage_days = as_float(row.get("tcgplayer_supply_coverage_days"))
        if supply_state or coverage_days is not None:
            detail = (supply_state or "UNKNOWN").replace("_", " ")
            if coverage_days is not None:
                detail += f" · ~{coverage_days:.1f} days of TCGplayer supply at observed velocity"
            st.caption(detail)
        st.caption("Trend confidence is evidence-coverage confidence, not a promise of future price direction. Dispersion is cross-source price dispersion, not yet a full historical-volatility model.")


def render_score_line(row: dict) -> None:
    st.markdown(" · ".join(f"**{score_badge(metric, row)}**" for metric in ("PCS", "LQS", "ECS", "BOS")))



def owned_floor(row: dict, source_name: str):
    source = row.get(source_name) or {}
    if not isinstance(source, dict) or str(source.get("status") or "").upper() != "OK":
        return None
    return as_float(source.get("floor_eur"))


def owned_robust_floor(row: dict, source_name: str):
    source = row.get(source_name) or {}
    if not isinstance(source, dict) or str(source.get("status") or "").upper() != "OK":
        return None
    return as_float(source.get("robust_floor_eur"))


def owned_ask_sample(row: dict, source_name: str) -> str | None:
    source = row.get(source_name) or {}
    values = source.get("ask_sample_eur") if isinstance(source, dict) else None
    if not isinstance(values, list) or not values:
        return None
    return " / ".join(format_eur(v) for v in values)


def owned_market_depth(row: dict, source_name: str, label: str) -> str:
    source = row.get(source_name) or {}
    if not isinstance(source, dict):
        return "not queried"
    status = str(source.get("status") or "NOT_QUERIED").upper()
    if status != "OK":
        return {
            "VERIFY_FINISH": "finish unverified",
            "NO_COMPARABLE_EN_NM_ASK": "no exact ask",
            "DEGRADED": "refresh degraded",
        }.get(status, "source unavailable" if status.startswith("MISSING_") else "not queried")
    if source_name == "cardtrader":
        bits = []
        if source.get("visible_sellers") not in (None, ""):
            bits.append(f"{source.get('visible_sellers')} sellers")
        if source.get("visible_units") not in (None, ""):
            bits.append(f"{source.get('visible_units')} cards")
        return " · ".join(bits) if bits else "exact EN/NM"
    offers = source.get("visible_offer_rows")
    return f"{offers} comparable offers" if offers not in (None, "") else "exact EN/NM"


def owned_source_caption(row: dict, source_name: str, label: str) -> str:
    source = row.get(source_name) or {}
    if not isinstance(source, dict):
        return f"{label}: not queried"
    status = str(source.get("status") or "NOT_QUERIED").upper()
    if status == "OK":
        bits = [f"{label}: exact comparable EN/NM ask"]
        sample = owned_ask_sample(row, source_name)
        if sample:
            bits.append(f"cheapest sample {sample}")
        return " · ".join(bits)
    if status == "VERIFY_FINISH":
        return f"{label}: finish/parallel not verified — floor withheld"
    if status == "NO_COMPARABLE_EN_NM_ASK":
        return f"{label}: no comparable EN/NM ask found"
    if status.startswith("MISSING_"):
        return f"{label}: source unavailable in this refresh"
    if status == "DEGRADED":
        return f"{label}: refresh degraded"
    return f"{label}: not queried"


def signed_eur(value) -> str:
    amount = as_float(value)
    if amount is None:
        return "—"
    if amount > 0:
        return f"+€{amount:,.2f}"
    if amount < 0:
        return f"-€{abs(amount):,.2f}"
    return "€0.00"


def signed_pct(value) -> str:
    amount = as_float(value)
    return "—" if amount is None else f"{amount:+.1f}%"


def compact_stat(label: str, value: str, sub: str | None = None) -> None:
    st.caption(label)
    st.markdown(f"#### {value}")
    if sub:
        st.caption(sub)


def friendly_reference_source(value) -> str:
    raw = clean_text(value)
    if not raw:
        return "source not retained"
    known = {
        "CARDTRADER_EN_NM": "CardTrader EN/NM ask",
        "CARDMARKET_EN_NM": "Cardmarket EN/NM ask",
        "CARDTRADER_DIRECT": "CardTrader Direct",
        "CARDTRADER_ZERO": "CardTrader Zero",
    }
    return known.get(raw.upper(), raw.replace("_", " ").title())


def owned_history_quality(row: dict) -> dict:
    values = {
        "Trend": as_float(row.get("trend")),
        "1d": as_float(row.get("avg1")),
        "7d": as_float(row.get("avg7")),
        "30d": as_float(row.get("avg30")),
    }
    positive = {k: v for k, v in values.items() if v is not None and v > 0}
    if len(positive) < 3:
        return {"label": "⚪ INSUFFICIENT", "ratio": None}
    low, high = min(positive.values()), max(positive.values())
    ratio = high / low if low > 0 else None
    if ratio is None:
        return {"label": "⚪ INSUFFICIENT", "ratio": None}
    if ratio >= 2.0:
        label = "🔴 LOW"
    elif ratio >= 1.35:
        label = "🟠 MEDIUM"
    else:
        label = "🟢 HIGH"
    return {"label": label, "ratio": ratio}


def render_owned_price_table(row: dict, landed: float | None) -> None:
    lines = [
        "| Source | Lowest ask | Robust ask | Depth | vs landed |",
        "|---|---:|---:|---|---:|",
    ]
    for source_name, label in (("cardmarket", "Cardmarket"), ("cardtrader", "CardTrader")):
        floor = owned_floor(row, source_name)
        robust = owned_robust_floor(row, source_name)
        delta = None if floor is None or landed is None else floor - landed
        lines.append(
            f"| **{label}** | {format_eur(floor)} | {format_eur(robust)} | "
            f"{owned_market_depth(row, source_name, label)} | {signed_eur(delta)} |"
        )
    st.markdown("\n".join(lines))
    samples = []
    for source_name, label in (("cardmarket", "CM"), ("cardtrader", "CT")):
        sample = owned_ask_sample(row, source_name)
        if sample:
            samples.append(f"{label} cheapest sample: {sample}")
    if samples:
        st.caption(" · ".join(samples))


def owned_result_summary(row: dict, landed: float | None) -> tuple[str, float | None, float | None]:
    model_exit = as_float(row.get("best_sell_net_eur"))
    if model_exit is None or landed is None:
        return "No routed net-exit estimate yet; live asks are market context, not a sell recommendation.", None, None
    profit = model_exit - landed
    roi = (profit / landed * 100.0) if landed else None
    direction = "gain" if profit >= 0 else "loss"
    return (
        f"Current modelled net exit is {format_eur(model_exit)} via {human_channel(row.get('best_sell_channel'))}. "
        f"Against your landed cost, that implies a {direction} of {format_eur(abs(profit))} ({abs(roi or 0):.1f}%).",
        profit,
        roi,
    )


def render_owned_position(row: dict, routed: bool) -> None:
    landed = as_float(row.get("landed_cost_eur"))
    item_paid = as_float(row.get("item_paid_eur"))
    shipping = as_float(row.get("allocated_shipping_eur"))
    summary, owner_profit, owner_roi = owned_result_summary(row, landed)
    st.markdown(f"**What it means:** {summary}")

    st.markdown("**Your position**")
    purchase_source = clean_text(row.get("purchase_source")) or "Unknown source"
    purchase_date = clean_text(row.get("purchase_date")) or "date not retained"
    st.caption(
        f"Bought {purchase_date} on **{purchase_source}** · {clean_text(row.get('language')) or '—'} / "
        f"{clean_text(row.get('condition')) or '—'} · finish rule {clean_text(row.get('finish_requirement')) or '—'}"
    )
    p1, p2, p3 = st.columns(3)
    with p1:
        compact_stat("Card price", format_eur(item_paid))
    with p2:
        compact_stat("Allocated shipping", format_eur(shipping))
    with p3:
        compact_stat("Landed cost", format_eur(landed))

    st.markdown("**Live pricing**")
    render_owned_price_table(row, landed)
    st.caption("Active asks are competition references, not realised exits. Robust ask = median of the cheapest three exact comparable asks when available.")

    history = owned_history_quality(row)
    marks = (
        f"Trend {format_eur(row.get('trend'))} · 1d {format_eur(row.get('avg1'))} · "
        f"7d {format_eur(row.get('avg7'))} · 30d {format_eur(row.get('avg30'))}"
    )
    st.markdown(f"**Cardmarket history:** {marks} · reference confidence **{history['label']}**")
    if history.get("ratio") is not None:
        st.caption(f"Summary spread {history['ratio']:.2f}×. Product-level history may mix condition/language and is not treated as a clean EN/NM realised-price series.")

    if routed:
        st.markdown("**Scanner view**")
        s1, s2 = st.columns(2)
        with s1:
            compact_stat("EU model value", format_eur(row.get("eu_fair_value_eur")))
        with s2:
            compact_stat(
                "Scanner acquisition reference",
                format_eur(row.get("best_validated_buy_eur")),
                friendly_reference_source(row.get("best_validated_buy_source")),
            )
        s3, s4 = st.columns(2)
        with s3:
            compact_stat("Modelled net exit", format_eur(row.get("best_sell_net_eur")), human_channel(row.get("best_sell_channel")))
        with s4:
            compact_stat("Your result", signed_eur(owner_profit), signed_pct(owner_roi))

        with st.expander("Why this scanner status?"):
            explanation = plain_gate_explanation(row)
            if explanation:
                st.markdown(explanation)
            render_score_line(row)
            st.caption("PCS = price confidence · LQS = liquidity · ECS = exit confidence · BOS = bridge support")
            raw_reason = clean_text(row.get("quality_gate_reason"))
            if raw_reason:
                st.code(raw_reason)

        with st.expander("Market evidence"):
            st.markdown(f"**Market state:** {market_trend_text(row)} · confidence {trend_confidence_text(row)}")
            render_market_profile(row, expanded=True)
            st.caption(owned_source_caption(row, "cardmarket", "Cardmarket"))
            st.caption(owned_source_caption(row, "cardtrader", "CardTrader"))
    else:
        with st.expander("Market evidence"):
            st.write({
                "Cardmarket trend": format_eur(row.get("trend")),
                "30d average": format_eur(row.get("avg30")),
                "7d average": format_eur(row.get("avg7")),
                "1d average": format_eur(row.get("avg1")),
                "purchase date": row.get("purchase_date"),
                "purchase source": row.get("purchase_source"),
                "allocated shipping": format_eur(row.get("allocated_shipping_eur")),
                "finish rule": row.get("finish_requirement"),
            })
            st.caption(owned_source_caption(row, "cardmarket", "Cardmarket"))
            st.caption(owned_source_caption(row, "cardtrader", "CardTrader"))


def render_route_card(row: dict) -> None:
    with st.container(border=True):
        render_card_title(row)
        st.markdown(f"**{signal_label(row.get('route_signal'))}**")
        owner_landed = as_float(row.get("landed_cost_eur"))
        if owner_landed is not None:
            render_owned_position(row, routed=True)
            return

        st.markdown(f"**Exit route:** {human_channel(row.get('best_sell_channel'))}")
        p1, p2 = st.columns(2)
        p1.metric("Scanner validated buy", format_eur(row.get("best_validated_buy_eur")))
        p2.metric("EU fair value", format_eur(row.get("eu_fair_value_eur")))
        p3, p4 = st.columns(2)
        p3.metric("Modelled net exit", format_eur(row.get("best_sell_net_eur")))
        p4.metric("Scanner modelled net profit", format_eur(row.get("net_spread_eur")))
        st.markdown(f"**Scanner modelled ROI:** {format_pct(row.get('net_roi_pct'))}")
        position = eu_position_text(row)
        if position:
            st.caption(position)
        render_score_line(row)
        st.caption(f"Market: {market_trend_text(row)} · confidence {trend_confidence_text(row)}")
        render_market_profile(row)
        explanation = plain_gate_explanation(row)
        if explanation:
            st.markdown(f"**Why not actionable:** {explanation}")
        raw_reason = clean_text(row.get("quality_gate_reason"))
        if raw_reason:
            with st.expander("Show numeric gate detail"):
                st.code(raw_reason)


def render_tracked_card(row: dict) -> None:
    with st.container(border=True):
        render_card_title(row)
        st.markdown("**🟣 OWNED REVIEW**")
        render_owned_position(row, routed=False)
        st.caption("No BUY/SELL signal is fabricated when an owned card is not routed.")


st.set_page_config(page_title="Pokémon Deal Scanner", page_icon="🃏", layout="wide")
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] .main .block-container {
        padding-top: 1.05rem;
    }
    .scanner-header {
        display: flex;
        align-items: baseline;
        flex-wrap: wrap;
        gap: 0.25rem 0.9rem;
        margin: 0 0 0.15rem 0;
    }
    .scanner-title {
        font-size: 2rem;
        font-weight: 720;
        line-height: 1.1;
        letter-spacing: -0.025em;
    }
    .scanner-meta {
        font-size: 0.80rem;
        line-height: 1.25;
        color: rgba(127, 127, 127, 0.95);
    }
    .review-date {
        font-size: 1.02rem;
        font-weight: 650;
        line-height: 1.2;
        padding-top: 0.25rem;
        white-space: nowrap;
    }
    .discovery-chip {
        display: inline-block;
        border: 1px solid rgba(127, 127, 127, 0.35);
        background: rgba(127, 127, 127, 0.08);
        border-radius: 999px;
        padding: 0.20rem 0.55rem;
        font-size: 0.82rem;
        line-height: 1.3;
        white-space: nowrap;
        margin-top: 0.08rem;
    }
    .discovery-chip strong { font-weight: 700; }
    div[data-testid="stSegmentedControl"] {
        margin-bottom: 0;
    }
    @media (max-width: 700px) {
        .scanner-title { font-size: 1.65rem; }
        .scanner-meta { width: 100%; }
        .review-date { white-space: normal; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)
cfg = load_cfg()
db_path = resolve_path(cfg, cfg["paths"]["database"])
output_dir = resolve_path(cfg, cfg["paths"]["output_dir"])
snapshot = read_snapshot(SNAPSHOT_PATH)
CARD_IMAGES = load_card_images(CARD_IMAGE_PATH)
provider_usage_rows = read_csv(PROVIDER_USAGE_PATH)
provider_limits = read_csv(PROVIDER_LIMITS_PATH)
conn: sqlite3.Connection | None = None

if db_path.exists():
    conn = open_readonly(db_path)
    predictions = latest_predictions(conn)
    routes = merge_market_profile(
        read_csv(output_dir / "market_routes.csv"),
        read_csv(output_dir / "market_signals.csv"),
        read_csv(output_dir / "market_quality.csv"),
    )
    discovery = read_csv(output_dir / "top_flips.csv")[:75]
    tracked = read_csv(TRACKED_REVIEW_PATH)
    maturity = matured_stats(conn)
    sync = latest_sync_state(conn)
    outcomes_by_card: dict[str, list[dict]] = {}
    data_mode = "Local read-only SQLite"
    data_updated = predictions[0]["snapshot_date"] if predictions else "unknown"
    scanner_version = str(cfg.get("version") or "unknown")
elif snapshot:
    predictions = list(snapshot.get("latest_predictions") or [])
    routes = list(snapshot.get("market_routes") or [])
    discovery = list(snapshot.get("discovery_candidates") or [])
    tracked = list(snapshot.get("tracked_cards") or [])
    maturity = dict(snapshot.get("maturity") or {})
    sync = list(snapshot.get("source_sync_state") or [])
    outcomes_by_card = dict(snapshot.get("latest_outcomes_by_card") or {})
    data_mode = "Hosted public snapshot"
    data_updated = str(snapshot.get("generated_at_utc") or "unknown")
    scanner_version = str(snapshot.get("scanner_version") or cfg.get("version") or "unknown")
else:
    st.error("No scanner database or hosted dashboard snapshot is available yet.")
    st.stop()

owned_market_payload = read_snapshot(OWNED_MARKET_PATH)
owned_rows = list(owned_market_payload.get("cards") or [])
if not owned_rows:
    owned_rows = read_csv(OWNED_LEDGER_PATH)
owned_by_pid = {str(r.get("id_product")): dict(r) for r in owned_rows if r.get("id_product") not in (None, "")}
enriched_tracked = []
for source in tracked:
    row = dict(source)
    owned = owned_by_pid.get(str(row.get("id_product")))
    if owned:
        row.update({k: v for k, v in owned.items() if v not in (None, "")})
    enriched_tracked.append(row)
tracked = enriched_tracked

for key in ("t7", "t7_cards", "t30", "t30_cards"):
    maturity[key] = int(maturity.get(key) or 0)

compact_mode = "Hosted snapshot" if data_mode == "Hosted public snapshot" else data_mode
st.markdown(
    f"""
    <div class="scanner-header">
      <div class="scanner-title">Pokémon Deal Scanner</div>
      <div class="scanner-meta">v{scanner_version} · {compact_mode} · Updated {compact_timestamp(data_updated)} · read-only</div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_today, tab_card, tab_health = st.tabs(["Today", "Card detail", "Model health"])

with tab_today:
    route_signals = [str(r.get("route_signal") or "").upper() for r in routes]
    resell_count = sum(s in RESELL_SIGNALS or s == "STRONG_ARBITRAGE" for s in route_signals)
    watch_count = sum(s in WATCH_SIGNALS for s in route_signals)
    needs_count = sum(s in NEEDS_EVIDENCE_SIGNALS for s in route_signals)
    latest_date = predictions[0].get("snapshot_date", "—") if predictions else "—"
    review_date = compact_timestamp(latest_date).split(" · ", 1)[0]
    non_edge_signals = sorted({s for s in route_signals if s and s != "NO_EDGE"})

    resell_group = set(RESELL_SIGNALS) | {"STRONG_ARBITRAGE"}
    watch_group = set(WATCH_SIGNALS)
    needs_group = set(NEEDS_EVIDENCE_SIGNALS)
    known_groups = resell_group | watch_group | needs_group
    other_group = set(non_edge_signals) - known_groups
    signal_option_map = {
        f"🟢 Resell {resell_count}": resell_group,
        f"🟡 Watch {watch_count}": watch_group,
        f"🔵 Needs data {needs_count}": needs_group,
    }
    if other_group:
        signal_option_map[f"⚪ Other {sum(s in other_group for s in route_signals)}"] = other_group
    signal_options = list(signal_option_map)

    h0, h1, h2, h3 = st.columns([1.45, 2.1, 4.1, 1.35], vertical_alignment="center")
    with h0:
        st.markdown(f'<div class="review-date">{review_date} market review</div>', unsafe_allow_html=True)
    with h1:
        review_choice = st.segmented_control(
            "Review set",
            options=["All", "Owned", "Routed"],
            default="All",
            label_visibility="collapsed",
            width="stretch",
            help="All = routed priority plus owned review cards. Owned excludes bundle-only €1 hero inventory.",
        ) or "All"
    with h2:
        selected_signal_labels = st.segmented_control(
            "Signals",
            options=signal_options,
            default=signal_options,
            selection_mode="multi",
            label_visibility="collapsed",
            width="stretch",
        ) or []
    with h3:
        st.markdown(
            f'<div class="discovery-chip" title="Discovery is pre-route sourcing evidence. Market diagnostics do not create BUY rules.">🔎 Discovery <strong>{len(discovery)}</strong> ⓘ</div>',
            unsafe_allow_html=True,
        )

    review_set = {"All": "Routed + owned", "Owned": "Owned cards", "Routed": "Routed priority"}[review_choice]
    selected_signals = set()
    for option in selected_signal_labels:
        selected_signals.update(signal_option_map.get(option, set()))

    st.subheader("Priority review")
    price_bands = sorted({clean_text(r.get("price_band")) for r in routes if clean_text(r.get("price_band"))})
    if len(price_bands) > 1:
        band_col, search_col = st.columns([3, 5], vertical_alignment="center")
        with band_col:
            selected_bands = st.segmented_control(
                "Price bands",
                options=price_bands,
                default=price_bands,
                selection_mode="multi",
                label_visibility="collapsed",
                width="stretch",
            ) or []
        with search_col:
            search_text = st.text_input(
                "Find card",
                placeholder="Find card — e.g. Dragonite, Pikachu, Charizard",
                label_visibility="collapsed",
            ).strip().lower()
    else:
        selected_bands = price_bands
        search_text = st.text_input(
            "Find card",
            placeholder="Find card — e.g. Dragonite, Pikachu, Charizard",
            label_visibility="collapsed",
        ).strip().lower()

    routed_priority = []
    if review_set in {"Routed + owned", "Routed priority"}:
        for row in routes:
            signal = str(row.get("route_signal") or "").upper()
            if signal == "NO_EDGE" or signal not in selected_signals:
                continue
            band = clean_text(row.get("price_band"))
            if selected_bands and band not in selected_bands:
                continue
            if search_text and search_text not in str(row.get("name") or "").lower():
                continue
            routed_priority.append(dict(row))
        routed_priority.sort(key=route_sort_key)

    tracked_map = {str(r.get("id_product") or "").strip(): dict(r) for r in tracked if r.get("id_product") not in (None, "")}
    route_map = {str(r.get("id_product") or "").strip(): dict(r) for r in routes if r.get("id_product") not in (None, "")}
    tracked_priority = []
    if review_set in {"Routed + owned", "Owned cards"}:
        for pid_key, tracked_row in tracked_map.items():
            if search_text and search_text not in str(tracked_row.get("name") or "").lower():
                continue
            route_row = route_map.get(pid_key)
            if route_row:
                merged = dict(tracked_row)
                merged.update({k: v for k, v in route_row.items() if v not in (None, "")})
                merged["_tracked"] = True
                tracked_priority.append(merged)
            else:
                tracked_row["_tracked"] = True
                tracked_priority.append(tracked_row)
        tracked_priority.sort(key=lambda r: short_name(r.get("name")).lower())

    combined_priority = []
    seen_priority = set()
    for row in tracked_priority + routed_priority:
        pid_key = str(row.get("id_product") or "").strip()
        if pid_key and pid_key in seen_priority:
            continue
        if pid_key:
            seen_priority.add(pid_key)
        combined_priority.append(row)

    if combined_priority:
        display_limit = len(combined_priority) if review_set == "Owned cards" else min(len(combined_priority), 18)
        for start in range(0, display_limit, 3):
            cols = st.columns(3)
            for offset, row in enumerate(combined_priority[start:start + 3]):
                with cols[offset]:
                    if clean_text(row.get("route_signal")):
                        if row.get("_tracked"):
                            st.caption("🟣 Owned review card")
                        render_route_card(row)
                    else:
                        render_tracked_card(row)
    else:
        st.info("No cards match these Priority Review filters.")

    st.divider()
    st.subheader("Discovery queue")
    st.caption("Pre-route sourcing candidates only. Normal identity, landed-cost and market-quality gates still apply.")
    if discovery:
        view = [r for r in discovery if not search_text or search_text in str(r.get("name") or "").lower()]
        st.dataframe(
            discovery_summary_rows(view[:50]),
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
    else:
        st.info("No discovery candidates are included in this dashboard snapshot yet.")

    with st.expander("All routed cards"):
        show_no_edge = st.checkbox("Include NO_EDGE", value=False)
        table_routes = [r for r in routes if show_no_edge or str(r.get("route_signal") or "").upper() != "NO_EDGE"]
        if search_text:
            table_routes = [r for r in table_routes if search_text in str(r.get("name") or "").lower()]
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

with tab_card:
    prediction_map = {str(r.get("id_product")): r for r in predictions if r.get("id_product") not in (None, "")}
    route_rows_by_pid: dict[str, list[dict]] = {}
    for row in routes:
        pid_key = str(row.get("id_product") or "").strip()
        if pid_key:
            route_rows_by_pid.setdefault(pid_key, []).append(row)
    discovery_map = {str(r.get("id_product")): r for r in discovery if r.get("id_product") not in (None, "")}
    tracked_detail_map = {str(r.get("id_product")): r for r in tracked if r.get("id_product") not in (None, "")}
    detail_ids = sorted(
        set(prediction_map) | set(route_rows_by_pid) | set(discovery_map) | set(tracked_detail_map),
        key=lambda pid_key: (
            short_name(
                (route_rows_by_pid.get(pid_key) or [{}])[0].get("name")
                or prediction_map.get(pid_key, {}).get("name")
                or discovery_map.get(pid_key, {}).get("name")
                or tracked_detail_map.get(pid_key, {}).get("name")
            ).lower(),
            int(pid_key),
        ),
    )

    if not detail_ids:
        st.info("No card-level scanner evidence is available yet.")
    else:
        def combined_card(pid_key: str) -> dict:
            merged: dict = {}
            for source in (
                tracked_detail_map.get(pid_key),
                discovery_map.get(pid_key),
                prediction_map.get(pid_key),
                (route_rows_by_pid.get(pid_key) or [None])[0],
            ):
                if not source:
                    continue
                for field, value in source.items():
                    if value not in (None, ""):
                        merged[field] = value
            merged["id_product"] = pid_key
            return merged

        detail_cards = {pid_key: combined_card(pid_key) for pid_key in detail_ids}

        def detail_stage(pid_key: str) -> str:
            if pid_key in route_rows_by_pid and pid_key in tracked_detail_map:
                return "ROUTED · TRACKED"
            if pid_key in route_rows_by_pid:
                return "ROUTED"
            if pid_key in prediction_map:
                return "FORECAST"
            if pid_key in tracked_detail_map:
                return "TRACKED"
            status = str(discovery_map.get(pid_key, {}).get("status") or "").upper()
            if status == "RESEARCH_WATCH":
                return "RESEARCH WATCH"
            return "DISCOVERY"

        def detail_label(pid_key: str) -> str:
            row = detail_cards[pid_key]
            return f"{short_name(row.get('name'))} — {card_context(row)} · {detail_stage(pid_key)}"

        selected_pid = st.selectbox(
            "Card",
            detail_ids,
            format_func=detail_label,
            help="Includes routed cards, tracked review cards, immutable forecasts, discovery candidates and explicit research watches present in the current dashboard dataset.",
        )
        pid_key = str(selected_pid)
        pid = int(pid_key)
        card = detail_cards[pid_key]
        matching_routes = list(route_rows_by_pid.get(pid_key) or [])
        prediction = prediction_map.get(pid_key)
        discovery_row = discovery_map.get(pid_key)

        render_card_title(card, heading="##", image_width=190, quality="high")
        st.caption(f"Stage: **{detail_stage(pid_key)}**")

        if matching_routes or prediction:
            route = dict(card)
            for source in (prediction, matching_routes[0] if matching_routes else None):
                if not source:
                    continue
                for field, value in source.items():
                    if value not in (None, ""):
                        route[field] = value

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("EU fair value", format_eur(route.get("eu_fair_value_eur")))
            c2.metric("Validated buy", format_eur(route.get("best_validated_buy_eur")))
            c3.metric("Deal score", format_score(route.get("deal_score")))
            c4.metric("Route", signal_label(route.get("route_signal")))
            st.markdown(f"**Exit route:** {human_channel(route.get('best_sell_channel'))}")
            render_score_line(route)
            position = eu_position_text(route)
            if position:
                st.caption(position)
            render_market_profile(route, expanded=True)
            explanation = plain_gate_explanation(route)
            if explanation:
                st.markdown(f"**Decision explanation:** {explanation}")

            if matching_routes:
                st.subheader("Current route evidence")
                st.dataframe(route_summary_rows(matching_routes), use_container_width=True, hide_index=True)
                with st.expander("Raw route fields"):
                    st.dataframe(matching_routes, use_container_width=True, hide_index=True)

            if prediction:
                with st.expander("Immutable forecast · audit view"):
                    st.json(prediction)
        else:
            status = clean_text((discovery_row or {}).get("status")) or "DISCOVERY"
            if status.upper() == "RESEARCH_WATCH":
                st.info("Research watch only — evidence is being collected without creating a BUY or fair-value override.")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Cardmarket trend", format_eur(card.get("trend")))
                c2.metric("30d average", format_eur(card.get("avg30")))
                c3.metric("7d average", format_eur(card.get("avg7")))
                c4.metric("Scanner status", status.replace("_", " "))
                note = clean_text(card.get("research_note"))
                if note:
                    st.caption(note)
            else:
                st.info("Pre-route discovery candidate only — identity, landed-cost, liquidity and market-quality gates still apply before any final resale decision.")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Candidate buy", format_eur(card.get("best_validated_sourcing_price")))
                c2.metric("30d average", format_eur(card.get("avg30")))
                c3.metric("Gap", format_pct(card.get("gap_pct")))
                c4.metric("Deal score", format_score(card.get("deal_score")))
                st.markdown(f"**Candidate buy source:** {acquisition_source_text(card)}")
                st.caption("Candidate buy is a source ask/floor, not a landed cost. Shipping, fees and Ireland eligibility still need route validation unless explicitly stated otherwise.")
                sellers = as_int(card.get("ct_visible_sellers"))
                units = as_int(card.get("ct_visible_units"))
                supply_bits = []
                if sellers is not None:
                    supply_bits.append(f"{sellers} CardTrader sellers")
                if units is not None:
                    supply_bits.append(f"{units} visible units")
                if supply_bits:
                    st.caption(" · ".join(supply_bits))
                st.markdown(f"**Scanner status:** {status}")
                with st.expander("Discovery evidence"):
                    st.write({
                        "Cardmarket trend": format_eur(card.get("trend")),
                        "Cardmarket 1d average": format_eur(card.get("avg1")),
                        "Cardmarket 7d average": format_eur(card.get("avg7")),
                        "Cardmarket 30d average": format_eur(card.get("avg30")),
                        "Cardmarket EN/NM floor": format_eur(card.get("cm_en_nm_floor")),
                        "CardTrader EN/NM floor": format_eur(card.get("ct_en_nm_floor")),
                    })

        outcomes = latest_outcomes(conn, pid) if conn is not None else list(outcomes_by_card.get(pid_key) or [])
        st.subheader("Matured outcomes")
        if outcomes:
            st.dataframe(outcomes, use_container_width=True, hide_index=True)
        else:
            st.caption("No matured outcomes for this card in the current dashboard dataset.")

with tab_health:
    st.subheader("Provider usage")
    usage_summary = provider_usage_summary(provider_usage_rows, provider_limits)
    if usage_summary:
        st.dataframe(
            usage_summary,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Month credits": st.column_config.NumberColumn(format="%.0f"),
                "Monthly limit": st.column_config.NumberColumn(format="%.0f"),
                "Remaining": st.column_config.NumberColumn(format="%.0f"),
            },
        )
        st.caption("Credits are shown only where the provider documents the unit cost or the account UI confirms it. Firecrawl is listed as a known account limit but scanner automation does not currently instrument its usage.")
    else:
        st.caption("No provider-usage observations have been recorded yet.")

    st.subheader("Experience-store maturity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("T+7 observations", f'{maturity["t7"]} / 500')
    c2.metric("T+7 unique cards", f'{maturity["t7_cards"]} / 100')
    c3.metric("T+30 observations", f'{maturity["t30"]} / 200')
    c4.metric("T+30 unique cards", f'{maturity["t30_cards"]} / 50')
    st.progress(min(1.0, maturity["t7"] / 500), text="Comparable-experience Gate B: T+7 observation progress")
    st.caption("Comparable-experience retrieval remains deferred until the leakage-safe maturity gates in docs/EXPERIENCE_STORE.md are satisfied.")
    st.subheader("Source sync state")
    if sync:
        st.dataframe(sync, use_container_width=True, hide_index=True)
    else:
        st.info("No source_sync_state records found.")
    st.subheader("Dashboard architecture")
    st.write({
        "mode": data_mode,
        "scanner_version": scanner_version,
        "pricing_logic_in_ui": False,
        "market_profile_changes_buy_logic": False,
        "mutations_allowed": False,
        "hosted_snapshot": "dashboard/data/dashboard_snapshot.json",
    })

if conn is not None:
    conn.close()
