from __future__ import annotations

import csv
import math
import re
from datetime import date, timedelta
from pathlib import Path


SIGNAL_FIELDS = [
    "snapshot_date", "id_product", "name", "expansion_name", "number",
    "cm_trend_eur", "cm_avg7_eur", "cm_avg30_eur", "cm_short_momentum_pct",
    "cm_30d_change_pct", "cm_price_basis",
    "ebay_reference_region", "ebay_reference_currency", "ebay_reference_value",
    "ebay_30d_change_pct", "cross_market_confirmation",
    "sales_7d", "sales_prev_23d", "sales_velocity_ratio",
    "active_supply_now", "active_supply_30d_ago", "supply_change_pct",
    "event_flag", "event_direction", "event_title", "event_type",
    "signal_score", "signal_label", "confidence", "coverage_count", "notes",
]


def _norm(value: str | None) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _finite(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _pct_change(current, prior) -> float | None:
    a = _finite(current)
    b = _finite(prior)
    if a is None or b in (None, 0):
        return None
    return round((a / b - 1.0) * 100.0, 2)


def _direction(value: float | None, neutral_pct: float) -> int:
    if value is None:
        return 0
    if value >= neutral_pct:
        return 1
    if value <= -neutral_pct:
        return -1
    return 0


def cross_market_confirmation(cm_pct: float | None, ebay_pct: float | None, neutral_pct: float = 3.0) -> str:
    if cm_pct is None or ebay_pct is None:
        return "INSUFFICIENT"
    cm_dir = _direction(cm_pct, neutral_pct)
    ebay_dir = _direction(ebay_pct, neutral_pct)
    if cm_dir == 0 and ebay_dir == 0:
        return "BOTH_FLAT"
    if cm_dir == ebay_dir == 1:
        return "CONFIRMS_UP"
    if cm_dir == ebay_dir == -1:
        return "CONFIRMS_DOWN"
    if cm_dir == 0 or ebay_dir == 0:
        return "MIXED"
    return "DIVERGES"


def sales_velocity_ratio(recent_7d: int, previous_23d: int) -> float | None:
    recent_7d = max(0, int(recent_7d or 0))
    previous_23d = max(0, int(previous_23d or 0))
    if previous_23d == 0:
        return None if recent_7d == 0 else 2.0
    return round((recent_7d / 7.0) / (previous_23d / 23.0), 2)


def classify_market_signal(metrics: dict, cfg: dict | None = None) -> dict:
    """Classify trend strength without turning one noisy price print into a BUY signal.

    Positive score means firmer demand; negative means cooling. Event flags are context,
    not proof of causation. A short-term pullback after a positive 30-day move is called
    PULLBACK instead of DECLINING.
    """
    cfg = cfg or {}
    neutral = float(cfg.get("neutral_price_move_pct", 3.0))
    strong = float(cfg.get("strong_price_move_pct", 10.0))
    velocity_up = float(cfg.get("velocity_acceleration_ratio", 1.5))
    velocity_down = float(cfg.get("velocity_cooling_ratio", 0.67))
    supply_move = float(cfg.get("meaningful_supply_change_pct", 10.0))

    cm_short = _finite(metrics.get("cm_short_momentum_pct"))
    cm_30d = _finite(metrics.get("cm_30d_change_pct"))
    ebay_30d = _finite(metrics.get("ebay_30d_change_pct"))
    velocity = _finite(metrics.get("sales_velocity_ratio"))
    supply = _finite(metrics.get("supply_change_pct"))

    price_driver = cm_30d if cm_30d is not None else cm_short
    score = 0
    if price_driver is not None:
        if price_driver >= strong:
            score += 2
        elif price_driver >= neutral:
            score += 1
        elif price_driver <= -strong:
            score -= 2
        elif price_driver <= -neutral:
            score -= 1

    if velocity is not None:
        if velocity >= velocity_up:
            score += 1
        elif velocity <= velocity_down:
            score -= 1

    # Falling available supply is supportive; rising supply is a headwind.
    if supply is not None:
        if supply <= -supply_move:
            score += 1
        elif supply >= supply_move:
            score -= 1

    cross = cross_market_confirmation(price_driver, ebay_30d, neutral)
    if cross == "CONFIRMS_UP":
        score += 1
    elif cross == "CONFIRMS_DOWN":
        score -= 1

    event_direction = _norm(metrics.get("event_direction"))
    if metrics.get("event_flag"):
        if event_direction in {"up", "bullish", "positive"}:
            score += 1
        elif event_direction in {"down", "bearish", "negative"}:
            score -= 1

    pullback = cm_short is not None and cm_short <= -neutral and cm_30d is not None and cm_30d >= neutral
    if pullback:
        label = "PULLBACK"
    elif cm_short is not None and cm_30d is not None and cm_short <= -neutral and cm_30d <= -neutral and score <= -1:
        label = "COOLING"
    elif cm_short is not None and cm_30d is not None and cm_short >= neutral and cm_30d >= neutral and score >= 1:
        label = "FIRMING"
    elif cross == "DIVERGES" and -2 <= score <= 2:
        label = "DIVERGENT_NOISY"
    elif score >= 4:
        label = "ACCELERATING"
    elif score >= 2:
        label = "FIRMING"
    elif score <= -4:
        label = "DECLINING"
    elif score <= -2:
        label = "COOLING"
    else:
        label = "MIXED_STABLE"

    coverage = sum(x is not None for x in (price_driver, velocity, supply, ebay_30d))
    if coverage >= 4 and cross != "DIVERGES":
        confidence = "HIGH"
    elif coverage >= 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    if cross == "DIVERGES" and confidence == "HIGH":
        confidence = "MEDIUM"

    return {
        "signal_score": score,
        "signal_label": label,
        "confidence": confidence,
        "coverage_count": coverage,
        "cross_market_confirmation": cross,
    }


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return bool(row)


def _latest_price_metrics(conn, id_product: int, today: date) -> dict:
    row = conn.execute(
        """SELECT snapshot_date,trend,avg7,avg30 FROM price_snapshots
           WHERE id_product=? ORDER BY snapshot_date DESC LIMIT 1""",
        (id_product,),
    ).fetchone()
    if not row:
        return {
            "cm_trend_eur": None, "cm_avg7_eur": None, "cm_avg30_eur": None,
            "cm_short_momentum_pct": None, "cm_30d_change_pct": None,
            "cm_price_basis": "NONE",
        }

    current_trend = _finite(row["trend"])
    avg7 = _finite(row["avg7"])
    avg30 = _finite(row["avg30"])
    short_pct = _pct_change(avg7, avg30)

    target = today - timedelta(days=30)
    history = conn.execute(
        """SELECT snapshot_date,trend FROM price_snapshots
           WHERE id_product=? AND snapshot_date<=? AND trend IS NOT NULL
           ORDER BY snapshot_date DESC LIMIT 1""",
        (id_product, target.isoformat()),
    ).fetchone()
    historical_pct = _pct_change(current_trend, history["trend"]) if history else None
    if historical_pct is not None:
        basis = "SNAPSHOT_30D"
    else:
        historical_pct = _pct_change(current_trend, avg30)
        basis = "TREND_VS_AVG30_PROXY" if historical_pct is not None else "AVG7_VS_AVG30_FALLBACK"
    return {
        "cm_trend_eur": current_trend,
        "cm_avg7_eur": avg7,
        "cm_avg30_eur": avg30,
        "cm_short_momentum_pct": short_pct,
        "cm_30d_change_pct": historical_pct,
        "cm_price_basis": basis,
    }


def _best_ebay_series(conn, id_product: int) -> tuple[str | None, str | None, list]:
    if not _table_exists(conn, "ebay_reference_history"):
        return None, None, []
    priorities = [("IRELAND", "EUR"), ("EU", "EUR"), ("UK", "GBP"), ("GLOBAL", "USD")]
    for region, currency in priorities:
        rows = conn.execute(
            """SELECT snapshot_date,chosen_reference FROM ebay_reference_history
               WHERE id_product=? AND region=? AND currency=? AND chosen_reference IS NOT NULL
               ORDER BY snapshot_date ASC""",
            (id_product, region, currency),
        ).fetchall()
        if rows:
            return region, currency, rows
    return None, None, []


def _ebay_reference_metrics(conn, id_product: int, today: date) -> dict:
    region, currency, rows = _best_ebay_series(conn, id_product)
    if not rows:
        return {
            "ebay_reference_region": None, "ebay_reference_currency": None,
            "ebay_reference_value": None, "ebay_30d_change_pct": None,
        }
    current = _finite(rows[-1]["chosen_reference"])
    target = today - timedelta(days=30)
    historical = None
    for row in rows:
        try:
            row_day = date.fromisoformat(str(row["snapshot_date"])[:10])
        except ValueError:
            continue
        if row_day <= target:
            historical = _finite(row["chosen_reference"])
        else:
            break
    return {
        "ebay_reference_region": region,
        "ebay_reference_currency": currency,
        "ebay_reference_value": current,
        "ebay_30d_change_pct": _pct_change(current, historical),
    }


def _manual_sale_dates(path: Path, id_product: int) -> list[date]:
    if not path.exists():
        return []
    dates: list[date] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                if int(row.get("id_product") or 0) != id_product:
                    continue
                if _norm(row.get("language")) not in {"", "en", "english"}:
                    continue
                dates.append(date.fromisoformat(str(row["sale_date"])[:10]))
            except (TypeError, ValueError, KeyError):
                continue
    return dates


def _sales_metrics(conn, sold_path: Path, id_product: int, today: date) -> dict:
    recent_cutoff = today - timedelta(days=6)
    prior_cutoff = today - timedelta(days=29)
    prior_end = today - timedelta(days=7)
    manual = _manual_sale_dates(sold_path, id_product)
    manual_recent = sum(recent_cutoff <= d <= today for d in manual)
    manual_prior = sum(prior_cutoff <= d <= prior_end for d in manual)

    inferred_recent = inferred_prior = 0
    if _table_exists(conn, "ebay_listing_state"):
        rows = conn.execute(
            """SELECT DISTINCT item_id,gone_at FROM ebay_listing_state
               WHERE id_product=? AND inferred_quick_sale=1 AND gone_at IS NOT NULL""",
            (id_product,),
        ).fetchall()
        dates = []
        for row in rows:
            try:
                dates.append(date.fromisoformat(str(row["gone_at"])[:10]))
            except ValueError:
                pass
        inferred_recent = sum(recent_cutoff <= d <= today for d in dates)
        inferred_prior = sum(prior_cutoff <= d <= prior_end for d in dates)

    # Manual verified sales and inferred disappearances can overlap; max() is a
    # conservative anti-double-counting rule until a shared sale ID exists.
    recent = max(manual_recent, inferred_recent)
    prior = max(manual_prior, inferred_prior)
    return {
        "sales_7d": recent,
        "sales_prev_23d": prior,
        "sales_velocity_ratio": sales_velocity_ratio(recent, prior),
    }


def _active_supply_on(conn, id_product: int, day: date) -> int | None:
    if not _table_exists(conn, "ebay_listing_state"):
        return None
    row = conn.execute(
        """SELECT COUNT(DISTINCT item_id) AS n FROM ebay_listing_state
           WHERE id_product=? AND first_seen_at<=?
             AND (gone_at IS NULL OR gone_at>?)""",
        (id_product, day.isoformat(), day.isoformat()),
    ).fetchone()
    return int(row["n"] or 0) if row else 0


def _supply_metrics(conn, id_product: int, today: date) -> dict:
    now = _active_supply_on(conn, id_product, today)
    prior = _active_supply_on(conn, id_product, today - timedelta(days=30))
    # A zero prior supply usually means the product was not being observed yet;
    # call that missing history rather than an infinite supply increase.
    change = None if prior in (None, 0) else _pct_change(now, prior)
    return {
        "active_supply_now": now,
        "active_supply_30d_ago": prior,
        "supply_change_pct": change,
    }


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _event_matches(event: dict, product: dict, today: date, lookback_days: int) -> bool:
    try:
        start = date.fromisoformat(str(event.get("event_date") or "")[:10])
    except ValueError:
        return False
    try:
        end = date.fromisoformat(str(event.get("end_date") or "")[:10]) if event.get("end_date") else start
    except ValueError:
        end = start
    if end < today - timedelta(days=lookback_days) or start > today:
        return False

    scope = _norm(event.get("scope_type") or "global")
    value = _norm(event.get("scope_value"))
    if scope == "global":
        return True
    if not value:
        return False
    if scope == "card":
        return value in _norm(f"{product.get('name')} {product.get('number')}")
    if scope == "pokemon":
        return value in _norm(product.get("name"))
    if scope == "set":
        return value in _norm(product.get("expansion_name"))
    return False


def _event_metrics(events: list[dict], product: dict, today: date, lookback_days: int) -> dict:
    matches = [e for e in events if _event_matches(e, product, today, lookback_days)]
    if not matches:
        return {"event_flag": False, "event_direction": "", "event_title": "", "event_type": ""}
    matches.sort(key=lambda e: str(e.get("event_date") or ""), reverse=True)
    event = matches[0]
    return {
        "event_flag": True,
        "event_direction": event.get("direction") or "neutral",
        "event_title": event.get("title") or "",
        "event_type": event.get("event_type") or "",
    }


def generate_market_signals(
    conn,
    cfg: dict,
    watchlist_path: Path,
    sold_path: Path,
    event_path: Path,
    output_path: Path,
    *,
    today: date | None = None,
) -> list[dict]:
    today = today or date.today()
    today_s = today.isoformat()
    signal_cfg = cfg.get("market_signals", {})
    events = read_events(event_path)
    lookback = int(signal_cfg.get("event_lookback_days", 30))

    if not watchlist_path.exists():
        rows = []
    else:
        with watchlist_path.open(newline="", encoding="utf-8") as f:
            rows = [dict(r) for r in csv.DictReader(f) if r.get("id_product")]

    output: list[dict] = []
    seen: set[int] = set()
    for watch in rows:
        try:
            pid = int(watch["id_product"])
        except (TypeError, ValueError, KeyError):
            continue
        if pid in seen:
            continue
        seen.add(pid)
        product_row = conn.execute(
            "SELECT id_product,name,expansion_name,number FROM products WHERE id_product=?", (pid,)
        ).fetchone()
        if not product_row:
            continue
        product = dict(product_row)
        row = {"snapshot_date": today_s, **product}
        row.update(_latest_price_metrics(conn, pid, today))
        row.update(_ebay_reference_metrics(conn, pid, today))
        row.update(_sales_metrics(conn, sold_path, pid, today))
        row.update(_supply_metrics(conn, pid, today))
        row.update(_event_metrics(events, product, today, lookback))
        classification = classify_market_signal(row, signal_cfg)
        row.update(classification)

        note_parts = []
        if row["cm_price_basis"] == "TREND_VS_AVG30_PROXY":
            note_parts.append("30d Cardmarket snapshot history unavailable; trend-vs-30d-average proxy used")
        elif row["cm_price_basis"] == "AVG7_VS_AVG30_FALLBACK":
            note_parts.append("30d Cardmarket snapshot history unavailable; short-vs-30d average used")
        if row["sales_velocity_ratio"] is None:
            note_parts.append("insufficient prior sold evidence for velocity")
        if row["supply_change_pct"] is None:
            note_parts.append("30d supply history not yet established")
        if row["cross_market_confirmation"] == "INSUFFICIENT":
            note_parts.append("30d eBay reference history not yet established")
        if not row["event_flag"]:
            note_parts.append("no matching event recorded in event registry")
        row["notes"] = "; ".join(note_parts)
        output.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SIGNAL_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(output)
    return output
