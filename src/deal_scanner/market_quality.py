from __future__ import annotations

import csv
import math
from datetime import date, datetime
from pathlib import Path


QUALITY_FIELDS = [
    "snapshot_date", "id_product", "name", "expansion_name", "number",
    # EU market is the primary valuation market for an Ireland-based buyer.
    "fair_value_eur", "fair_value_scope", "eu_fair_value_eur", "eu_price_confidence_score",
    "eu_price_confidence_label", "eu_market_count", "eu_dispersion_pct",
    "eu_executable_value_eur", "eu_executable_source",
    # US market is separated and used mainly to validate CardTrader/global exits.
    "us_fair_value_eur", "us_price_confidence_score", "us_price_confidence_label",
    "us_liquidity_score", "us_liquidity_label", "us_market_count", "us_dispersion_pct",
    # Bridge-market diagnostics.
    "bridge_opportunity_score", "bridge_opportunity_label", "bridge_us_support_pct",
    "bridge_ct_premium_vs_eu_pct", "bridge_ct_premium_vs_us_pct",
    # Legacy aliases retained for downstream compatibility. They now mean EU/Ireland-facing values.
    "cross_market_dispersion_pct", "independent_market_count",
    "tcgplayer_market_eur", "tcgplayer_recent_sale_eur",
    "tcgplayer_executable_floor_eur", "tcgplayer_item_floor_eur", "tcgplayer_shipping_floor_eur",
    "tcgplayer_market_to_executable_gap_pct", "tcgplayer_recent_sale_vs_market_pct",
    "tcgplayer_sales_30d", "tcgplayer_sales_90d", "tcgplayer_avg_daily_sold",
    "tcgplayer_monthly_sales_equiv", "tcgplayer_current_quantity", "tcgplayer_current_sellers",
    "tcgplayer_supply_coverage_days", "tcgplayer_supply_state",
    "tcgplayer_low_eur", "tcgplayer_listing_count",
    "tcgplayer_strength", "tcgplayer_vs_us_fair_pct",
    "liquidity_score", "liquidity_label", "price_confidence_score",
    "price_confidence_label", "exit_confidence_score", "exit_confidence_label",
    "quality_gate_pass", "quality_gate_profile", "quality_gate_reason",
]


def _float(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _int(value, default=0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> tuple[list[dict], list[str]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader], list(reader.fieldnames or [])


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _append_fields(existing: list[str], additions: list[str]) -> list[str]:
    out = list(existing)
    for field in additions:
        if field not in out:
            out.append(field)
    return out


def _age_days(value: str | None, today: date) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return max(0, (today - datetime.fromisoformat(text.replace("Z", "+00:00")).date()).days)
    except ValueError:
        try:
            return max(0, (today - date.fromisoformat(text[:10])).days)
        except ValueError:
            return None


def _weighted_median(points: list[tuple[float, float]]) -> float | None:
    values = [(float(v), max(0.0, float(w))) for v, w in points if v > 0 and w > 0]
    if not values:
        return None
    values.sort(key=lambda x: x[0])
    total = sum(w for _, w in values)
    halfway = total / 2.0
    running = 0.0
    for value, weight in values:
        running += weight
        if running >= halfway:
            return round(value, 2)
    return round(values[-1][0], 2)


def _weighted_mad_pct(points: list[tuple[float, float]], center: float | None) -> float | None:
    if center in (None, 0):
        return None
    deviations = [(abs(value / center - 1.0) * 100.0, weight) for value, weight in points]
    return _weighted_median(deviations)


def _label(score: int, bands: tuple[tuple[int, str], ...]) -> str:
    for minimum, label in bands:
        if score >= minimum:
            return label
    return bands[-1][1]


def _eur(raw: dict, eur_key: str, usd_key: str, fx: float) -> float | None:
    direct = _float(raw.get(eur_key))
    if direct is not None:
        return round(direct, 2)
    usd = _float(raw.get(usd_key))
    return None if usd is None else round(usd * fx, 2)


def _best_tcg_rows(path: Path, cfg: dict) -> dict[str, dict]:
    rows, _ = _read_csv(path)
    fallback_usd_to_eur = float(cfg.get("fx", {}).get("fallback_usd_to_eur", 0.86))
    strength_rank = {"STRONG": 0, "MEDIUM": 1, "WEAK": 2, "VERY_WEAK": 3, "NONE": 9}
    out: dict[str, dict] = {}
    for raw in rows:
        pid = str(raw.get("id_product") or "").strip()
        if not pid:
            continue
        fx_row = _float(raw.get("fx_usd_to_eur"))
        fx = fx_row or fallback_usd_to_eur
        market_eur = _eur(raw, "market_price_eur", "market_price_usd", fx)
        recent_sale_eur = _eur(raw, "most_recent_sale_eur", "most_recent_sale_usd", fx)
        item_floor_eur = _eur(raw, "lowest_listing_price_eur", "lowest_listing_price_usd", fx)
        shipping_floor_eur = _eur(raw, "lowest_listing_shipping_eur", "lowest_listing_shipping_usd", fx)
        executable_floor_eur = _eur(raw, "executable_floor_eur", "executable_floor_usd", fx)
        if executable_floor_eur is None and item_floor_eur is not None and shipping_floor_eur is not None:
            executable_floor_eur = round(item_floor_eur + shipping_floor_eur, 2)
        low_eur = _eur(raw, "low_price_eur", "low_price_usd", fx)
        row = {
            **raw,
            "_market_eur": market_eur,
            "_recent_sale_eur": recent_sale_eur,
            "_item_floor_eur": item_floor_eur,
            "_shipping_floor_eur": shipping_floor_eur,
            "_executable_floor_eur": executable_floor_eur,
            "_low_eur": low_eur,
            "_fx_source": "ROW" if fx_row else "CONFIG_FALLBACK",
        }
        current = out.get(pid)
        if current is None:
            out[pid] = row
            continue
        new_rank = strength_rank.get(str(row.get("reference_strength") or "NONE").upper(), 9)
        old_rank = strength_rank.get(str(current.get("reference_strength") or "NONE").upper(), 9)
        new_date = str(row.get("checked_at") or "")
        old_date = str(current.get("checked_at") or "")
        if new_rank < old_rank or (new_rank == old_rank and new_date > old_date):
            out[pid] = row
    return out


def _tcg_monthly_sales(tcg: dict | None) -> float:
    if not tcg:
        return 0.0
    sales30 = _float(tcg.get("sales_30d"))
    if sales30 is not None and sales30 >= 0:
        return sales30
    sales90 = _float(tcg.get("sales_90d"))
    if sales90 is not None and sales90 >= 0:
        return sales90 / 3.0
    daily = _float(tcg.get("avg_daily_sold"))
    if daily is not None and daily >= 0:
        return daily * 30.0
    return 0.0


def _tcg_supply_metrics(tcg: dict | None) -> tuple[float | None, str]:
    if not tcg:
        return None, "UNKNOWN"
    qty = _float(tcg.get("current_quantity"))
    monthly = _tcg_monthly_sales(tcg)
    sellers = _int(tcg.get("current_sellers"))
    if qty is None:
        return None, "UNKNOWN"
    if qty <= 0:
        return 0.0, "NO_LIVE_SUPPLY"
    if monthly <= 0:
        return None, "DEPTH_ONLY"
    daily_velocity = monthly / 30.0
    coverage_days = round(qty / daily_velocity, 1) if daily_velocity > 0 else None
    if coverage_days is None:
        return None, "UNKNOWN"
    if coverage_days <= 7 or (sellers <= 2 and coverage_days <= 14):
        state = "TIGHT"
    elif coverage_days <= 30:
        state = "BALANCED"
    else:
        state = "DEEP"
    return coverage_days, state


def _strength_rank(value: str | None) -> int:
    return {"STRONG": 0, "MEDIUM": 1, "WEAK": 2, "VERY_WEAK": 3, "NONE": 9}.get(
        str(value or "NONE").upper(), 9
    )


def _best_ebay_rows(path: Path) -> tuple[dict[str, dict], dict[str, dict[str, dict]]]:
    """Return strongest-any row and strongest row per region for each exact product."""
    rows, _ = _read_csv(path)
    overall: dict[str, dict] = {}
    regional: dict[str, dict[str, dict]] = {}
    for row in rows:
        pid = str(row.get("id_product") or "").strip()
        if not pid:
            continue
        region = str(row.get("region") or "GLOBAL").upper()
        regional.setdefault(pid, {})
        current = regional[pid].get(region)
        if current is None:
            regional[pid][region] = row
        else:
            a, b = _strength_rank(row.get("strength")), _strength_rank(current.get("strength"))
            if a < b or (a == b and _int(row.get("confirmed_sales")) > _int(current.get("confirmed_sales"))):
                regional[pid][region] = row

        current_any = overall.get(pid)
        if current_any is None:
            overall[pid] = row
        else:
            a, b = _strength_rank(row.get("strength")), _strength_rank(current_any.get("strength"))
            if a < b or (a == b and _int(row.get("confirmed_sales")) > _int(current_any.get("confirmed_sales"))):
                overall[pid] = row
    return overall, regional


def _ebay_reference_eur(row: dict | None, cfg: dict) -> float | None:
    if not row:
        return None
    value = _float(row.get("smoothed_reference"))
    if value is None:
        value = _float(row.get("chosen_reference"))
    if value is None or value <= 0:
        return None
    currency = str(row.get("currency") or "EUR").upper()
    if currency == "EUR":
        return round(value, 2)
    fxcfg = cfg.get("fx", {})
    if currency == "USD":
        return round(value * float(fxcfg.get("fallback_usd_to_eur", 0.86)), 2)
    if currency == "GBP":
        return round(value * float(fxcfg.get("fallback_gbp_to_eur", 1.16)), 2)
    return None


def _best_eu_ebay(regional: dict[str, dict], cfg: dict) -> tuple[dict | None, float | None]:
    candidates = []
    for region in ("IRELAND", "EU"):
        row = regional.get(region)
        value = _ebay_reference_eur(row, cfg)
        if row and value:
            candidates.append((_strength_rank(row.get("strength")), -_int(row.get("confirmed_sales")), row, value))
    if not candidates:
        return None, None
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2], candidates[0][3]


def _us_ebay(regional: dict[str, dict], cfg: dict) -> tuple[dict | None, float | None]:
    # GLOBAL is produced from the EBAY_US marketplace in this project. It is kept
    # as US/global context because physical item location is not forced for GLOBAL.
    row = regional.get("GLOBAL")
    return row, _ebay_reference_eur(row, cfg)


def _mapping_statuses(path: Path) -> dict[str, str]:
    rows, _ = _read_csv(path)
    out: dict[str, str] = {}
    for row in rows:
        resolved = str(row.get("resolved_id_product") or "").strip()
        status = str(row.get("mapping_status") or "").upper()
        if resolved and status in {"EXACT", "VERIFIED_MULTI"}:
            out[resolved] = status
    return out


def _ct_map(path: Path) -> dict[str, dict]:
    rows, _ = _read_csv(path)
    return {str(r.get("id_product") or ""): r for r in rows if r.get("id_product")}


def _eu_executable_value(route: dict) -> tuple[float | None, str]:
    robust = _float(route.get("cm_live_robust_floor_eur"))
    sellers = _int(route.get("cm_live_sellers"))
    if robust is not None and robust > 0 and sellers >= 2:
        return robust, "CARDMARKET_LIVE_EN_NM_ARTICLE"
    return None, ""


def _eu_points(route: dict, eu_ebay: dict | None, eu_ebay_eur: float | None) -> list[tuple[float, float, str]]:
    """EU/Ireland fair value only. US and CardTrader are intentionally excluded."""
    points: list[tuple[float, float, str]] = []
    cm = _float(route.get("cardmarket_trend_eur"))
    if cm and cm > 0:
        points.append((cm, 1.00, "CARDMARKET"))
    cm_live = _float(route.get("cm_live_robust_floor_eur"))
    cm_live_sellers = _int(route.get("cm_live_sellers"))
    if cm_live and cm_live > 0 and cm_live_sellers >= 2:
        # Current EN/NM ask context: useful, but below confirmed transactions.
        points.append((cm_live, 0.70, "CARDMARKET_LIVE"))
    if eu_ebay_eur and eu_ebay_eur > 0:
        strength = str((eu_ebay or {}).get("strength") or "NONE").upper()
        weight = {"STRONG": 1.20, "MEDIUM": 0.90, "WEAK": 0.45, "VERY_WEAK": 0.25}.get(strength, 0.20)
        points.append((eu_ebay_eur, weight, "EBAY_EU"))
    return points


def _us_points(tcg: dict | None, us_ebay: dict | None, us_ebay_eur: float | None) -> list[tuple[float, float, str]]:
    """US/global value. Used mainly to validate CardTrader's bridge-market exit."""
    points: list[tuple[float, float, str]] = []
    if tcg:
        market = _float(tcg.get("_market_eur"))
        recent = _float(tcg.get("_recent_sale_eur"))
        strength = str(tcg.get("reference_strength") or "NONE").upper()
        if market and market > 0:
            weight = {"STRONG": 1.00, "MEDIUM": 0.75, "WEAK": 0.40, "VERY_WEAK": 0.20}.get(strength, 0.20)
            points.append((market, weight, "TCGPLAYER"))
        if recent and recent > 0:
            points.append((recent, 0.60, "TCGPLAYER_RECENT"))
    if us_ebay_eur and us_ebay_eur > 0:
        strength = str((us_ebay or {}).get("strength") or "NONE").upper()
        weight = {"STRONG": 1.00, "MEDIUM": 0.75, "WEAK": 0.40, "VERY_WEAK": 0.20}.get(strength, 0.20)
        points.append((us_ebay_eur, weight, "EBAY_US_GLOBAL"))
    return points


def _score_dispersion(dispersion_pct: float | None, max_points: float) -> float:
    if dispersion_pct is None:
        return 0.0
    return max_points * max(0.0, 1.0 - dispersion_pct / 25.0)


def _eu_liquidity_score(
    route: dict,
    eu_ebay: dict | None,
    eu_dispersion: float | None,
    source_count: int,
) -> int:
    confirmed = _int((eu_ebay or {}).get("confirmed_sales"))
    inferred = _int((eu_ebay or {}).get("inferred_sales"))
    realized = confirmed + 0.5 * inferred
    velocity = 0.0 if realized <= 0 else min(30.0, 30.0 * math.log1p(realized) / math.log1p(12))

    cm_sellers = _int(route.get("cm_live_sellers"))
    cm_units = _int(route.get("cm_live_units"))
    depth = min(16.0, cm_sellers / 5.0 * 16.0) + min(9.0, cm_units / 12.0 * 9.0)

    spread = _score_dispersion(eu_dispersion, 20.0)
    breadth = min(15.0, 15.0 * source_count / 3.0)
    if confirmed >= 5:
        immediacy = 10.0
    elif confirmed >= 2:
        immediacy = 7.0
    elif confirmed >= 1:
        immediacy = 5.0
    elif cm_sellers >= 3:
        immediacy = 3.0
    else:
        immediacy = 0.0
    return int(round(max(0.0, min(100.0, velocity + depth + spread + breadth + immediacy))))


def _us_liquidity_score(tcg: dict | None, us_ebay: dict | None, us_dispersion: float | None, source_count: int) -> int:
    tcg_monthly = _tcg_monthly_sales(tcg)
    ebay_confirmed = _int((us_ebay or {}).get("confirmed_sales"))
    ebay_inferred = _int((us_ebay or {}).get("inferred_sales"))
    realized = tcg_monthly + ebay_confirmed + 0.5 * ebay_inferred
    velocity = 0.0 if realized <= 0 else min(30.0, 30.0 * math.log1p(realized) / math.log1p(20))

    sellers = _int((tcg or {}).get("current_sellers"))
    qty = _int((tcg or {}).get("current_quantity"))
    depth = min(15.0, sellers / 5.0 * 15.0) + min(10.0, qty / 15.0 * 10.0)
    spread = _score_dispersion(us_dispersion, 20.0)
    breadth = min(15.0, 15.0 * source_count / 3.0)
    if realized >= 10:
        immediacy = 10.0
    elif realized >= 5:
        immediacy = 8.0
    elif realized >= 2:
        immediacy = 6.0
    elif realized >= 1:
        immediacy = 4.0
    else:
        immediacy = 0.0
    return int(round(max(0.0, min(100.0, velocity + depth + spread + breadth + immediacy))))


def _regional_confidence(
    *,
    dispersion: float | None,
    source_count: int,
    transaction_strength: str,
    transaction_sales: float,
    freshness_dates: list[str | None],
    liquidity_score: int,
    mapping_status: str | None,
    today: date,
) -> int:
    convergence = _score_dispersion(dispersion, 35.0) * min(1.0, source_count / 2.0)
    strength = str(transaction_strength or "NONE").upper()
    transaction = {"STRONG": 15.0, "MEDIUM": 10.0, "WEAK": 4.0, "VERY_WEAK": 2.0}.get(strength, 0.0)
    if transaction_sales > 0:
        transaction += min(10.0, 10.0 * math.log1p(transaction_sales) / math.log1p(15))
    transaction = min(25.0, transaction)

    freshness = 5.0
    for value in freshness_dates[:2]:
        age = _age_days(value, today)
        if age is not None:
            freshness += 5.0 if age <= 7 else (3.0 if age <= 30 else 1.0)
    freshness = min(15.0, freshness)

    liquidity = 15.0 * liquidity_score / 100.0
    identity = 10.0 if mapping_status in {"EXACT", "VERIFIED_MULTI"} else (8.0 if not mapping_status else 0.0)
    return int(round(max(0.0, min(100.0, convergence + transaction + freshness + liquidity + identity))))


def _ct_depth(ct: dict | None, channel: str) -> tuple[int, int]:
    if not ct:
        return 0, 0
    if channel == "CARDTRADER_ZERO":
        return _int(ct.get("ct_zero_sellers")), _int(ct.get("ct_zero_units"))
    return _int(ct.get("ct_direct_sellers")), _int(ct.get("ct_direct_units"))


def _bridge_opportunity_score(
    route: dict,
    ct: dict | None,
    eu_pcs: int,
    eu_lqs: int,
    us_fair: float | None,
    us_pcs: int,
    us_lqs: int,
) -> tuple[int, dict]:
    channel = str(route.get("best_sell_channel") or "")
    gross = _float(route.get("best_sell_gross_eur"))
    if not channel.startswith("CARDTRADER") or not ct or gross in (None, 0):
        return 0, {"economic": 0.0, "us_support": 0.0, "depth": 0.0, "eu_confidence": 0.0, "liquidity": 0.0}

    spread = max(0.0, _float(route.get("net_spread_eur")) or 0.0)
    roi = max(0.0, _float(route.get("net_roi_pct")) or 0.0)
    req_spread = max(1.0, _float(route.get("required_net_spread_eur")) or 8.0)
    req_roi = max(1.0, _float(route.get("required_net_roi_pct")) or 25.0)
    economic = min(17.5, 17.5 * spread / req_spread) + min(17.5, 17.5 * roi / req_roi)

    if us_fair and us_fair > 0:
        deviation = abs(gross / us_fair - 1.0) * 100.0
        us_alignment = 25.0 * max(0.0, 1.0 - deviation / 35.0)
        # Low US confidence should not fully validate a CT exit.
        us_support = us_alignment * (0.35 + 0.65 * us_pcs / 100.0)
    else:
        us_support = 0.0

    sellers, units = _ct_depth(ct, channel)
    depth = min(12.0, sellers / 5.0 * 12.0) + min(8.0, units / 12.0 * 8.0)
    eu_confidence = 10.0 * eu_pcs / 100.0
    liquidity = 10.0 * ((eu_lqs + us_lqs) / 2.0) / 100.0
    raw_score = economic + us_support + depth + eu_confidence + liquidity
    # CardTrader is the bridge market: when its premium is not supported by the
    # US/global reference, the apparent edge must be heavily discounted rather
    # than rescued by a large nominal spread alone.
    support_factor = 0.45 + 0.55 * (us_support / 25.0) if us_fair and us_fair > 0 else 0.45
    score = int(round(max(0.0, min(100.0, raw_score * support_factor))))
    return score, {
        "economic": round(economic, 1),
        "us_support": round(us_support, 1),
        "depth": round(depth, 1),
        "eu_confidence": round(eu_confidence, 1),
        "liquidity": round(liquidity, 1),
        "support_factor": round(support_factor, 3),
    }


def _exit_confidence_score(
    route: dict,
    ct: dict | None,
    ebay_any: dict | None,
    eu_fair: float | None,
    us_fair: float | None,
    eu_lqs: int,
    us_lqs: int,
    bridge_score: int,
) -> int:
    channel = str(route.get("best_sell_channel") or "")
    gross = _float(route.get("best_sell_gross_eur"))
    if not channel or gross in (None, 0):
        return 0

    if channel.startswith("CARDTRADER") and ct:
        sellers, units = _ct_depth(ct, channel)
        depth = min(30.0, sellers / 5.0 * 30.0) + min(10.0, units / 12.0 * 10.0)
        if us_fair and us_fair > 0:
            deviation = abs(gross / us_fair - 1.0) * 100.0
            alignment = 35.0 * max(0.0, 1.0 - deviation / 35.0)
        elif eu_fair and eu_fair > 0:
            # Without US confirmation, EU value may provide a weak sanity check only.
            deviation = abs(gross / eu_fair - 1.0) * 100.0
            alignment = 15.0 * max(0.0, 1.0 - deviation / 35.0)
        else:
            alignment = 0.0
        liquidity = 10.0 * us_lqs / 100.0 + 5.0 * eu_lqs / 100.0
        bridge_confirmation = 10.0 * bridge_score / 100.0
        return int(round(max(0.0, min(100.0, depth + alignment + liquidity + bridge_confirmation))))

    if channel.startswith("EBAY"):
        strength = str((ebay_any or {}).get("strength") or "NONE").upper()
        depth = {"STRONG": 40.0, "MEDIUM": 30.0, "WEAK": 14.0, "VERY_WEAK": 8.0}.get(strength, 0.0)
        sales = _int((ebay_any or {}).get("confirmed_sales"))
        confirmation = min(10.0, 10.0 * sales / 5.0)
        if eu_fair and eu_fair > 0:
            deviation = abs(gross / eu_fair - 1.0) * 100.0
            alignment = 35.0 * max(0.0, 1.0 - deviation / 35.0)
        else:
            alignment = 0.0
        return int(round(max(0.0, min(100.0, depth + confirmation + alignment + 15.0 * eu_lqs / 100.0))))

    return int(round(min(100.0, 10.0 + 15.0 * eu_lqs / 100.0)))


def _gate(
    acquisition: float | None,
    eu_lqs: int,
    eu_pcs: int,
    ecs: int,
    bridge_score: int,
    channel: str,
    cfg: dict,
) -> tuple[bool, str, str]:
    qcfg = cfg.get("market_quality", {})
    high_from = float(qcfg.get("high_value_from_eur", 50.0))
    if acquisition is not None and acquisition >= high_from:
        profile = "HIGH_VALUE"
        min_lqs = int(qcfg.get("high_value_min_liquidity_score", 70))
        min_pcs = int(qcfg.get("high_value_min_price_confidence_score", 80))
        min_ecs = int(qcfg.get("high_value_min_exit_confidence_score", 70))
        min_bridge = int(qcfg.get("high_value_min_bridge_opportunity_score", 70))
    else:
        profile = "STANDARD"
        min_lqs = int(qcfg.get("min_liquidity_score", 65))
        min_pcs = int(qcfg.get("min_price_confidence_score", 75))
        min_ecs = int(qcfg.get("min_exit_confidence_score", 65))
        min_bridge = int(qcfg.get("min_bridge_opportunity_score", 65))

    failures = []
    if eu_lqs < min_lqs:
        failures.append(f"EU-LQS {eu_lqs}<{min_lqs}")
    if eu_pcs < min_pcs:
        failures.append(f"EU-PCS {eu_pcs}<{min_pcs}")
    if ecs < min_ecs:
        failures.append(f"ECS {ecs}<{min_ecs}")
    if channel.startswith("CARDTRADER") and bridge_score < min_bridge:
        failures.append(f"BOS {bridge_score}<{min_bridge}")
    return not failures, profile, "PASS" if not failures else "; ".join(failures)


def apply_market_quality(
    cfg: dict,
    route_path: Path,
    ct_path: Path,
    ebay_reference_path: Path,
    tcgplayer_reference_path: Path,
    mapping_audit_path: Path,
    core_watch_path: Path,
    output_path: Path,
    *,
    today: date | None = None,
) -> dict:
    """Score EU value separately from US value and use CardTrader as the bridge market.

    Cardmarket + EU/Ireland eBay drive EU fair value for an Ireland-based buyer.
    TCGplayer + US/global eBay drive a separate US reference. TCGplayer does not
    drag EU fair value down or up. Its main decision role is validating whether a
    CardTrader premium is supported by the US/global market.
    """
    today = today or date.today()
    route_rows, route_fields = _read_csv(route_path)
    ct = _ct_map(ct_path)
    ebay_any, ebay_regional = _best_ebay_rows(ebay_reference_path)
    tcg = _best_tcg_rows(tcgplayer_reference_path, cfg)
    mappings = _mapping_statuses(mapping_audit_path)

    quality_rows: list[dict] = []
    downgraded = 0
    tcg_used = 0

    for row in route_rows:
        pid = str(row.get("id_product") or "")
        if not pid:
            continue
        ct_row = ct.get(pid)
        ebay_any_row = ebay_any.get(pid)
        regions = ebay_regional.get(pid, {})
        eu_ebay_row, eu_ebay_eur = _best_eu_ebay(regions, cfg)
        us_ebay_row, us_ebay_eur = _us_ebay(regions, cfg)
        tcg_row = tcg.get(pid)
        if tcg_row and _float(tcg_row.get("_market_eur")):
            tcg_used += 1

        eu_raw = _eu_points(row, eu_ebay_row, eu_ebay_eur)
        eu_weighted = [(v, w) for v, w, _ in eu_raw]
        eu_fair = _weighted_median(eu_weighted)
        eu_dispersion = _weighted_mad_pct(eu_weighted, eu_fair)
        eu_sources = {name for _, _, name in eu_raw}

        us_raw = _us_points(tcg_row, us_ebay_row, us_ebay_eur)
        us_weighted = [(v, w) for v, w, _ in us_raw]
        us_fair = _weighted_median(us_weighted)
        us_dispersion = _weighted_mad_pct(us_weighted, us_fair)
        us_sources = {name for _, _, name in us_raw}

        eu_lqs = _eu_liquidity_score(row, eu_ebay_row, eu_dispersion, len(eu_sources))
        us_lqs = _us_liquidity_score(tcg_row, us_ebay_row, us_dispersion, len(us_sources))

        eu_pcs = _regional_confidence(
            dispersion=eu_dispersion,
            source_count=len(eu_sources),
            transaction_strength=str((eu_ebay_row or {}).get("strength") or "NONE"),
            transaction_sales=_int((eu_ebay_row or {}).get("confirmed_sales")),
            freshness_dates=[(eu_ebay_row or {}).get("snapshot_date"), row.get("snapshot_date")],
            liquidity_score=eu_lqs,
            mapping_status=mappings.get(pid),
            today=today,
        )
        tcg_strength = str((tcg_row or {}).get("reference_strength") or "NONE")
        us_transaction_strength = tcg_strength
        if _strength_rank((us_ebay_row or {}).get("strength")) < _strength_rank(tcg_strength):
            us_transaction_strength = str((us_ebay_row or {}).get("strength") or "NONE")
        us_pcs = _regional_confidence(
            dispersion=us_dispersion,
            source_count=len(us_sources),
            transaction_strength=us_transaction_strength,
            transaction_sales=_tcg_monthly_sales(tcg_row) + _int((us_ebay_row or {}).get("confirmed_sales")),
            freshness_dates=[(tcg_row or {}).get("checked_at"), (us_ebay_row or {}).get("snapshot_date")],
            liquidity_score=us_lqs,
            mapping_status=mappings.get(pid),
            today=today,
        )

        bridge_score, _ = _bridge_opportunity_score(
            row, ct_row, eu_pcs, eu_lqs, us_fair, us_pcs, us_lqs
        )
        ecs = _exit_confidence_score(
            row, ct_row, ebay_any_row, eu_fair, us_fair, eu_lqs, us_lqs, bridge_score
        )
        acquisition = _float(row.get("best_validated_buy_eur"))
        channel = str(row.get("best_sell_channel") or "")
        gate_pass, profile, gate_reason = _gate(
            acquisition, eu_lqs, eu_pcs, ecs, bridge_score, channel, cfg
        )

        eu_exec, eu_exec_source = _eu_executable_value(row)
        tcg_market = _float((tcg_row or {}).get("_market_eur"))
        tcg_recent = _float((tcg_row or {}).get("_recent_sale_eur"))
        tcg_exec = _float((tcg_row or {}).get("_executable_floor_eur"))
        tcg_item = _float((tcg_row or {}).get("_item_floor_eur"))
        tcg_ship = _float((tcg_row or {}).get("_shipping_floor_eur"))
        tcg_low = _float((tcg_row or {}).get("_low_eur"))
        tcg_vs_us = None if tcg_market is None or us_fair in (None, 0) else round((tcg_market / us_fair - 1.0) * 100.0, 1)
        market_exec_gap = None if tcg_market in (None, 0) or tcg_exec is None else round((tcg_exec / tcg_market - 1.0) * 100.0, 1)
        recent_vs_market = None if tcg_market in (None, 0) or tcg_recent is None else round((tcg_recent / tcg_market - 1.0) * 100.0, 1)
        monthly_sales = _tcg_monthly_sales(tcg_row)
        coverage_days, supply_state = _tcg_supply_metrics(tcg_row)

        ct_gross = _float(row.get("best_sell_gross_eur")) if channel.startswith("CARDTRADER") else None
        ct_vs_eu = None if ct_gross is None or eu_fair in (None, 0) else round((ct_gross / eu_fair - 1.0) * 100.0, 1)
        ct_vs_us = None if ct_gross is None or us_fair in (None, 0) else round((ct_gross / us_fair - 1.0) * 100.0, 1)
        us_support = None if ct_vs_us is None else round(max(0.0, 100.0 - min(100.0, abs(ct_vs_us) / 35.0 * 100.0)), 1)

        quality = {
            "snapshot_date": row.get("snapshot_date") or today.isoformat(),
            "id_product": pid,
            "name": row.get("name") or "",
            "expansion_name": row.get("expansion_name") or "",
            "number": row.get("number") or "",
            "fair_value_eur": eu_fair if eu_fair is not None else "",
            "fair_value_scope": "EU_TRANSACTIONAL",
            "eu_fair_value_eur": eu_fair if eu_fair is not None else "",
            "eu_price_confidence_score": eu_pcs,
            "eu_price_confidence_label": _label(eu_pcs, ((85, "VERY_HIGH"), (75, "HIGH"), (60, "MEDIUM"), (40, "LOW"), (0, "VERY_LOW"))),
            "eu_market_count": len(eu_sources),
            "eu_dispersion_pct": "" if eu_dispersion is None else round(eu_dispersion, 1),
            "eu_executable_value_eur": eu_exec if eu_exec is not None else "",
            "eu_executable_source": eu_exec_source,
            "us_fair_value_eur": us_fair if us_fair is not None else "",
            "us_price_confidence_score": us_pcs,
            "us_price_confidence_label": _label(us_pcs, ((85, "VERY_HIGH"), (75, "HIGH"), (60, "MEDIUM"), (40, "LOW"), (0, "VERY_LOW"))),
            "us_liquidity_score": us_lqs,
            "us_liquidity_label": _label(us_lqs, ((85, "EXTREMELY_LIQUID"), (70, "HIGH"), (55, "MODERATE"), (40, "THIN"), (0, "ILLIQUID"))),
            "us_market_count": len(us_sources),
            "us_dispersion_pct": "" if us_dispersion is None else round(us_dispersion, 1),
            "bridge_opportunity_score": bridge_score,
            "bridge_opportunity_label": _label(bridge_score, ((85, "STRONG_BRIDGE"), (70, "GOOD_BRIDGE"), (55, "WATCH"), (0, "WEAK_OR_UNSUPPORTED"))),
            "bridge_us_support_pct": "" if us_support is None else us_support,
            "bridge_ct_premium_vs_eu_pct": "" if ct_vs_eu is None else ct_vs_eu,
            "bridge_ct_premium_vs_us_pct": "" if ct_vs_us is None else ct_vs_us,
            "cross_market_dispersion_pct": "" if eu_dispersion is None else round(eu_dispersion, 1),
            "independent_market_count": len(eu_sources),
            "tcgplayer_market_eur": tcg_market if tcg_market is not None else "",
            "tcgplayer_recent_sale_eur": tcg_recent if tcg_recent is not None else "",
            "tcgplayer_executable_floor_eur": tcg_exec if tcg_exec is not None else "",
            "tcgplayer_item_floor_eur": tcg_item if tcg_item is not None else "",
            "tcgplayer_shipping_floor_eur": tcg_ship if tcg_ship is not None else "",
            "tcgplayer_market_to_executable_gap_pct": "" if market_exec_gap is None else market_exec_gap,
            "tcgplayer_recent_sale_vs_market_pct": "" if recent_vs_market is None else recent_vs_market,
            "tcgplayer_sales_30d": _int((tcg_row or {}).get("sales_30d")),
            "tcgplayer_sales_90d": _int((tcg_row or {}).get("sales_90d")),
            "tcgplayer_avg_daily_sold": _float((tcg_row or {}).get("avg_daily_sold")) or 0,
            "tcgplayer_monthly_sales_equiv": round(monthly_sales, 1),
            "tcgplayer_current_quantity": _int((tcg_row or {}).get("current_quantity")),
            "tcgplayer_current_sellers": _int((tcg_row or {}).get("current_sellers")),
            "tcgplayer_supply_coverage_days": "" if coverage_days is None else coverage_days,
            "tcgplayer_supply_state": supply_state,
            "tcgplayer_low_eur": tcg_low if tcg_low is not None else "",
            "tcgplayer_listing_count": _int((tcg_row or {}).get("listing_count")),
            "tcgplayer_strength": str((tcg_row or {}).get("reference_strength") or "NONE").upper(),
            "tcgplayer_vs_us_fair_pct": "" if tcg_vs_us is None else tcg_vs_us,
            "liquidity_score": eu_lqs,
            "liquidity_label": _label(eu_lqs, ((85, "EXTREMELY_LIQUID"), (70, "HIGH"), (55, "MODERATE"), (40, "THIN"), (0, "ILLIQUID"))),
            "price_confidence_score": eu_pcs,
            "price_confidence_label": _label(eu_pcs, ((85, "VERY_HIGH"), (75, "HIGH"), (60, "MEDIUM"), (40, "LOW"), (0, "VERY_LOW"))),
            "exit_confidence_score": ecs,
            "exit_confidence_label": _label(ecs, ((85, "VERY_HIGH"), (70, "HIGH"), (55, "MEDIUM"), (35, "LOW"), (0, "VERY_LOW"))),
            "quality_gate_pass": int(gate_pass),
            "quality_gate_profile": profile,
            "quality_gate_reason": gate_reason,
        }
        quality_rows.append(quality)
        row.update(quality)

        if not gate_pass and str(row.get("route_signal") or "") == "RESELL_TEST":
            row["route_signal"] = "WATCH_ONLY"
            downgraded += 1
            row["notes"] = (
                str(row.get("notes") or "")
                + f"; segmented-market gate failed: {gate_reason}; EU-LQS={eu_lqs}, EU-PCS={eu_pcs}, ECS={ecs}, BOS={bridge_score}"
            ).strip("; ")
        elif gate_pass:
            row["notes"] = (
                str(row.get("notes") or "")
                + f"; segmented-market gate passed ({profile}): EU-LQS={eu_lqs}, EU-PCS={eu_pcs}, ECS={ecs}, BOS={bridge_score}"
            ).strip("; ")

    _write_csv(route_path, route_rows, _append_fields(route_fields, QUALITY_FIELDS))
    _write_csv(output_path, quality_rows, QUALITY_FIELDS)

    core_rows, core_fields = _read_csv(core_watch_path)
    quality_map = {str(r.get("id_product") or ""): r for r in quality_rows}
    for row in core_rows:
        q = quality_map.get(str(row.get("id_product") or ""))
        if q:
            row.update({k: q[k] for k in QUALITY_FIELDS if k not in {"snapshot_date", "id_product", "name", "expansion_name", "number"}})
    if core_fields:
        _write_csv(core_watch_path, core_rows, _append_fields(core_fields, QUALITY_FIELDS))

    return {
        "enabled": True,
        "route_rows_scored": len(quality_rows),
        "tcgplayer_rows_loaded": len(tcg),
        "routes_with_tcgplayer_evidence": tcg_used,
        "routes_downgraded_by_quality_gate": downgraded,
        "output": str(output_path),
        "policy": (
            "EU fair value is driven by Cardmarket + EU/Ireland eBay. "
            "TCGplayer + US/global eBay form a separate US reference used mainly to validate CardTrader bridge exits. "
            "TCGplayer no longer moves EU fair value."
        ),
    }
