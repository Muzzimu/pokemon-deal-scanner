from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
DEFAULT_OUTPUT = ROOT / "dashboard" / "data" / "dashboard_snapshot.json"
RESEARCH_WATCH_PATH = ROOT / "data" / "reference" / "research_watchlist.csv"
TRACKED_REVIEW_PATH = ROOT / "data" / "reference" / "tracked_review_cards.csv"

PREDICTION_FIELDS = [
    "snapshot_date", "id_product", "name", "expansion_name", "number", "model_version",
    "eu_fair_value_eur", "eu_price_confidence_score", "eu_liquidity_score",
    "us_fair_value_eur", "us_price_confidence_score", "us_liquidity_score",
    "exit_confidence_score", "bridge_opportunity_score", "best_validated_buy_eur",
    "best_sell_channel", "best_sell_net_eur", "route_signal", "deal_score",
]

ROUTE_FIELDS = [
    "snapshot_date", "id_product", "name", "expansion_name", "number", "route_signal",
    "best_validated_buy_source", "best_validated_buy_eur", "eu_fair_value_eur",
    "us_fair_value_eur", "best_sell_channel", "best_sell_net_eur", "net_spread_eur",
    "net_roi_pct", "deal_score", "eu_price_confidence_score", "eu_price_confidence_label",
    "liquidity_score", "liquidity_label", "eu_liquidity_score",
    "exit_confidence_score", "exit_confidence_label", "bridge_opportunity_score",
    "bridge_opportunity_label", "quality_gate_reason", "confidence", "ct_lag_label",
    "manual_verification_required", "price_band",
    # Optional live Cardmarket depth fields when present in market_routes.csv.
    "cm_live_sellers", "cm_live_units", "cm_live_robust_floor_eur",
]

DISCOVERY_FIELDS = [
    "snapshot_date", "id_product", "name", "expansion_name", "number", "rarity",
    "best_validated_sourcing_price", "deal_score", "status", "trend", "avg30", "avg7", "avg1",
    "cm_en_nm_floor", "ct_en_nm_floor", "ct_visible_sellers", "ct_visible_units",
    "gap_pct", "popularity_score", "research_note",
]

# Dashboard-only diagnostics. These are observations/explanations, not new model scores.
PROFILE_SIGNAL_FIELDS = [
    "market_trend_label", "market_trend_confidence", "market_trend_coverage_count",
    "cm_short_momentum_pct", "cm_30d_change_pct", "cm_price_basis",
    "sales_7d", "sales_prev_23d", "sales_velocity_ratio",
    "active_supply_now", "active_supply_30d_ago", "supply_change_pct",
]
PROFILE_QUALITY_FIELDS = [
    "eu_dispersion_pct", "us_dispersion_pct",
    "tcgplayer_sales_30d", "tcgplayer_sales_90d", "tcgplayer_avg_daily_sold",
    "tcgplayer_monthly_sales_equiv", "tcgplayer_current_quantity",
    "tcgplayer_current_sellers", "tcgplayer_supply_coverage_days", "tcgplayer_supply_state",
]

OUTCOME_FIELDS = [
    "snapshot_date", "id_product", "horizon_days", "target_scope", "window_start", "window_end",
    "forecast_value_eur", "realised_value_eur", "observation_count", "evidence_quality",
    "outcome_source", "error_pct", "abs_error_pct", "entry_return_pct", "success_flag",
]


def load_cfg() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def resolve_path(configured: str) -> Path:
    path = Path(configured)
    return path if path.is_absolute() else ROOT / path


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


def select_fields(row: dict, fields: list[str]) -> dict:
    return {field: row.get(field) for field in fields if field in row}


def blank(value) -> bool:
    return value is None or str(value).strip().lower() in {"", "none", "nan", "null"}


def enrich_identity(conn: sqlite3.Connection, rows: list[dict]) -> list[dict]:
    ids = sorted({int(row["id_product"]) for row in rows if row.get("id_product") not in (None, "")})
    if not ids or not table_exists(conn, "products"):
        return rows
    placeholders = ",".join("?" for _ in ids)
    products = conn.execute(
        f"SELECT id_product, name, expansion_name, number FROM products WHERE id_product IN ({placeholders})",
        tuple(ids),
    ).fetchall()
    by_id = {int(row["id_product"]): dict(row) for row in products}
    out = []
    for source in rows:
        row = dict(source)
        try:
            product = by_id.get(int(row.get("id_product")))
        except (TypeError, ValueError):
            product = None
        if product:
            for field in ("name", "expansion_name", "number"):
                if blank(row.get(field)) and not blank(product.get(field)):
                    row[field] = product[field]
        out.append(row)
    return out


def latest_predictions(conn: sqlite3.Connection) -> list[dict]:
    if not table_exists(conn, "model_predictions"):
        return []
    latest = conn.execute("SELECT MAX(snapshot_date) FROM model_predictions").fetchone()[0]
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
        LEFT JOIN products pr ON pr.id_product=p.id_product
        WHERE p.snapshot_date=?
        ORDER BY COALESCE(p.deal_score, -999999) DESC, p.id_product
        """,
        (latest,),
    ).fetchall()
    return [select_fields(dict(row), PREDICTION_FIELDS) for row in rows]


def maturity(conn: sqlite3.Connection) -> dict:
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


def sync_state(conn: sqlite3.Connection) -> list[dict]:
    if not table_exists(conn, "source_sync_state"):
        return []
    rows = conn.execute(
        "SELECT source, value, updated_at FROM source_sync_state ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def latest_outcomes_by_card(conn: sqlite3.Connection, product_ids: list[int]) -> dict[str, list[dict]]:
    if not product_ids or not table_exists(conn, "model_outcomes"):
        return {}
    placeholders = ",".join("?" for _ in product_ids)
    rows = conn.execute(
        f"""
        SELECT {','.join(OUTCOME_FIELDS)}
        FROM model_outcomes
        WHERE id_product IN ({placeholders}) AND realised_value_eur IS NOT NULL
        ORDER BY snapshot_date DESC, horizon_days, target_scope
        """,
        tuple(product_ids),
    ).fetchall()
    seen: set[tuple[int, int, str]] = set()
    out: dict[str, list[dict]] = {}
    for raw in rows:
        row = dict(raw)
        key = (int(row["id_product"]), int(row["horizon_days"]), str(row["target_scope"]))
        if key in seen:
            continue
        seen.add(key)
        out.setdefault(str(row["id_product"]), []).append(select_fields(row, OUTCOME_FIELDS))
    return out


def by_product(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        pid = str(row.get("id_product") or "").strip()
        if pid:
            out[pid] = row
    return out


def merge_market_profile(routes: list[dict], signals: list[dict], quality: list[dict]) -> list[dict]:
    signal_map = by_product(signals)
    quality_map = by_product(quality)
    out = []
    for source in routes:
        row = dict(source)
        pid = str(row.get("id_product") or "").strip()
        signal = signal_map.get(pid, {})
        quality_row = quality_map.get(pid, {})

        # Prefix the market-signal labels so they cannot be confused with route confidence.
        row["market_trend_label"] = signal.get("signal_label")
        row["market_trend_confidence"] = signal.get("confidence")
        row["market_trend_coverage_count"] = signal.get("coverage_count")
        for field in (
            "cm_short_momentum_pct", "cm_30d_change_pct", "cm_price_basis",
            "sales_7d", "sales_prev_23d", "sales_velocity_ratio",
            "active_supply_now", "active_supply_30d_ago", "supply_change_pct",
        ):
            row[field] = signal.get(field)
        for field in PROFILE_QUALITY_FIELDS:
            row[field] = quality_row.get(field)
        out.append(row)
    return out


def research_watch_rows(conn: sqlite3.Connection, path: Path) -> list[dict]:
    """Expose exact-card research pilots without promoting them into routed BUY logic."""
    rows = read_csv(path)
    if not rows:
        return []
    watched = enrich_identity(conn, rows)
    out: list[dict] = []
    for source in watched:
        try:
            pid = int(source.get("id_product") or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue

        product = None
        if table_exists(conn, "products"):
            product = conn.execute(
                "SELECT name, expansion_name, number, rarity FROM products WHERE id_product=?",
                (pid,),
            ).fetchone()
        price = None
        if table_exists(conn, "price_snapshots"):
            price = conn.execute(
                """
                SELECT snapshot_date, low, trend, avg1, avg7, avg30
                FROM price_snapshots
                WHERE id_product=?
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                (pid,),
            ).fetchone()

        product_dict = dict(product) if product else {}
        price_dict = dict(price) if price else {}
        out.append({
            "snapshot_date": price_dict.get("snapshot_date") or "",
            "id_product": pid,
            "name": source.get("name") or product_dict.get("name") or f"Cardmarket ID {pid}",
            "expansion_name": source.get("expansion_name") or product_dict.get("expansion_name"),
            "number": source.get("number") or product_dict.get("number"),
            "rarity": product_dict.get("rarity"),
            "best_validated_sourcing_price": None,
            "deal_score": None,
            "status": source.get("status") or "RESEARCH_WATCH",
            "trend": price_dict.get("trend"),
            "avg30": price_dict.get("avg30"),
            "avg7": price_dict.get("avg7"),
            "avg1": price_dict.get("avg1"),
            "cm_en_nm_floor": None,
            "ct_en_nm_floor": None,
            "ct_visible_sellers": None,
            "ct_visible_units": None,
            "gap_pct": None,
            "popularity_score": None,
            "research_note": source.get("research_note") or "",
        })
    return out


def tracked_review_rows(conn: sqlite3.Connection, path: Path) -> list[dict]:
    """Public-safe exact-card watch rows for dashboard Priority Review."""
    rows = read_csv(path)
    if not rows:
        return []
    out: list[dict] = []
    for source in rows:
        try:
            pid = int(source.get("id_product") or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue
        price = None
        if table_exists(conn, "price_snapshots"):
            price = conn.execute(
                """
                SELECT snapshot_date, trend, avg1, avg7, avg30
                FROM price_snapshots
                WHERE id_product=?
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                (pid,),
            ).fetchone()
        price_dict = dict(price) if price else {}
        out.append({
            "snapshot_date": price_dict.get("snapshot_date") or "",
            "id_product": pid,
            "name": source.get("name") or f"Cardmarket ID {pid}",
            "expansion_name": source.get("expansion_name") or "",
            "number": source.get("number") or "",
            "tracking_role": source.get("tracking_role") or "RESALE_REVIEW",
            "status": "TRACKED_REVIEW",
            "trend": price_dict.get("trend"),
            "avg1": price_dict.get("avg1"),
            "avg7": price_dict.get("avg7"),
            "avg30": price_dict.get("avg30"),
        })
    return out


def build_snapshot() -> dict:
    cfg = load_cfg()
    db_path = resolve_path(cfg["paths"]["database"])
    output_dir = resolve_path(cfg["paths"]["output_dir"])
    if not db_path.exists():
        raise FileNotFoundError(f"Scanner database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    predictions = latest_predictions(conn)
    product_ids = [int(row["id_product"]) for row in predictions if row.get("id_product") is not None]

    raw_routes = enrich_identity(conn, read_csv(output_dir / "market_routes.csv"))
    profile_routes = merge_market_profile(
        raw_routes,
        read_csv(output_dir / "market_signals.csv"),
        read_csv(output_dir / "market_quality.csv"),
    )
    route_fields = ROUTE_FIELDS + PROFILE_SIGNAL_FIELDS + PROFILE_QUALITY_FIELDS
    routes = [select_fields(row, route_fields) for row in profile_routes]

    raw_discovery = read_csv(output_dir / "top_flips.csv")[:75]
    seen_discovery_ids = {
        str(row.get("id_product") or "").strip()
        for row in raw_discovery
        if str(row.get("id_product") or "").strip()
    }
    for research_row in research_watch_rows(conn, RESEARCH_WATCH_PATH):
        pid = str(research_row.get("id_product") or "").strip()
        if pid and pid not in seen_discovery_ids:
            raw_discovery.append(research_row)
            seen_discovery_ids.add(pid)
    discovery = [
        select_fields(row, DISCOVERY_FIELDS)
        for row in enrich_identity(conn, raw_discovery)
    ]

    tracked = tracked_review_rows(conn, TRACKED_REVIEW_PATH)

    snapshot = {
        "schema_version": 3,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "scanner_version": str(cfg.get("version") or "unknown"),
        "public_snapshot": True,
        "privacy_note": "Market/model fields plus public-safe tracked-card identities; no purchase prices, inventory quantities, secrets, or seller-level data.",
        "latest_predictions": predictions,
        "market_routes": routes,
        "discovery_candidates": discovery,
        "tracked_cards": tracked,
        "maturity": maturity(conn),
        "source_sync_state": sync_state(conn),
        "latest_outcomes_by_card": latest_outcomes_by_card(conn, product_ids),
    }
    conn.close()
    return snapshot


def main() -> int:
    snapshot = build_snapshot()
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Dashboard snapshot written to {DEFAULT_OUTPUT.relative_to(ROOT)} "
        f"({len(snapshot['latest_predictions'])} predictions, "
        f"{len(snapshot['market_routes'])} routes, "
        f"{len(snapshot['discovery_candidates'])} discovery candidates)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
