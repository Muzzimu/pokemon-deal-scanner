from __future__ import annotations

import csv
import math
import statistics
from datetime import date, datetime
from pathlib import Path


QUALITY_FIELDS = [
    "snapshot_date", "id_product", "name", "expansion_name", "number",
    "fair_value_eur", "fair_value_scope", "eu_executable_value_eur", "eu_executable_source",
    "cross_market_dispersion_pct", "independent_market_count",
    "tcgplayer_market_eur", "tcgplayer_recent_sale_eur",
    "tcgplayer_executable_floor_eur", "tcgplayer_item_floor_eur", "tcgplayer_shipping_floor_eur",
    "tcgplayer_market_to_executable_gap_pct", "tcgplayer_recent_sale_vs_market_pct",
    "tcgplayer_sales_30d", "tcgplayer_sales_90d", "tcgplayer_avg_daily_sold",
    "tcgplayer_monthly_sales_equiv", "tcgplayer_current_quantity", "tcgplayer_current_sellers",
    "tcgplayer_supply_coverage_days", "tcgplayer_supply_state",
    # Legacy/provider-ambiguous fields remain visible for audit but are not used as exact depth.
    "tcgplayer_low_eur", "tcgplayer_listing_count",
    "tcgplayer_strength", "tcgplayer_vs_fair_pct",
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


def _best_ebay_rows(path: Path) -> dict[str, dict]:
    rows, _ = _read_csv(path)
    strength_rank = {"STRONG": 0, "MEDIUM": 1, "WEAK": 2, "VERY_WEAK": 3, "NONE": 9}
    out: dict[str, dict] = {}
    for row in rows:
        pid = str(row.get("id_product") or "").strip()
        if not pid:
            continue
        current = out.get(pid)
        if current is None:
            out[pid] = row
            continue
        a = strength_rank.get(str(row.get("strength") or "NONE").upper(), 9)
        b = strength_rank.get(str(current.get("strength") or "NONE").upper(), 9)
        if a < b:
            out[pid] = row
        elif a == b and _int(row.get("confirmed_sales")) > _int(current.get("confirmed_sales")):
            out[pid] = row
    return out


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
    """Return current European EN/NM replacement context only when live CM depth exists.

    A validated historical/deal-specific buy price is intentionally not promoted to a
    general European replacement value. Live Cardmarket article prices remain asks,
    not sold-price fair value, and shipping still needs separate treatment for a BUY.
    """
    robust = _float(route.get("cm_live_robust_floor_eur"))
    sellers = _int(route.get("cm_live_sellers"))
    if robust is not None and robust > 0 and sellers >= 2:
        return robust, "CARDMARKET_LIVE_EN_NM_ARTICLE"
    return None, ""


def _market_points(route: dict, ct: dict | None, tcg: dict | None, ebay: dict | None) -> list[tuple[float, float, str]]:
    """Build GLOBAL TRANSACTIONAL fair-value points.

    Current executable asks (TCGplayer live floor / live Cardmarket floor) are kept
    outside this set. This prevents a temporary supply squeeze from being confused
    with realized fair value while still exposing replacement-value context separately.
    """
    points: list[tuple[float, float, str]] = []
    cm = _float(route.get("cardmarket_trend_eur"))
    if cm and cm > 0:
        points.append((cm, 1.00, "CARDMARKET"))

    ebay_price = _float(route.get("ebay_expected_eur"))
    ebay_strength = str((ebay or {}).get("strength") or "NONE").upper()
    if ebay_price and ebay_price > 0:
        weight = {"STRONG": 1.20, "MEDIUM": 0.90, "WEAK": 0.45, "VERY_WEAK": 0.25}.get(ebay_strength, 0.20)
        points.append((ebay_price, weight, "EBAY"))

    if tcg:
        market = _float(tcg.get("_market_eur"))
        strength = str(tcg.get("reference_strength") or "NONE").upper()
        if market and market > 0:
            weight = {"STRONG": 0.95, "MEDIUM": 0.75, "WEAK": 0.40, "VERY_WEAK": 0.20}.get(strength, 0.20)
            points.append((market, weight, "TCGPLAYER"))

    if ct:
        gross = _float(ct.get("best_ct_gross_eur"))
        sellers = _int(ct.get("ct_zero_sellers")) if str(ct.get("best_ct_channel")) == "CARDTRADER_ZERO" else _int(ct.get("ct_direct_sellers"))
        if gross and gross > 0:
            weight = 0.10 if sellers <= 1 else (0.30 if sellers == 2 else 0.50)
            points.append((gross, weight, "CARDTRADER"))
    return points


def _liquidity_score(route: dict, ct: dict | None, tcg: dict | None, ebay: dict | None,
                     fair_value: float | None, dispersion_pct: float | None) -> tuple[int, dict]:
    ebay_confirmed = _int((ebay or {}).get("confirmed_sales"))
    ebay_inferred = _int((ebay or {}).get("inferred_sales"))
    tcg_monthly = _tcg_monthly_sales(tcg)
    total_sales = ebay_confirmed + tcg_monthly + 0.5 * ebay_inferred
    velocity = 0.0 if total_sales <= 0 else min(30.0, 30.0 * math.log1p(total_sales) / math.log1p(20))

    ct_sellers = ct_units = 0
    if ct:
        if str(ct.get("best_ct_channel")) == "CARDTRADER_ZERO":
            ct_sellers = _int(ct.get("ct_zero_sellers"))
            ct_units = _int(ct.get("ct_zero_units"))
        else:
            ct_sellers = _int(ct.get("ct_direct_sellers"))
            ct_units = _int(ct.get("ct_direct_units"))

    # TCGplayer depth now uses exact-product CURRENT sellers/quantity only. The
    # legacy listing_count field may be a search-result count and is never used here.
    tcg_sellers = _int((tcg or {}).get("current_sellers"))
    tcg_qty = _int((tcg or {}).get("current_quantity"))
    depth = (
        min(12.0, ct_sellers / 5.0 * 12.0)
        + min(6.0, ct_units / 12.0 * 6.0)
        + min(4.0, tcg_sellers / 4.0 * 4.0)
        + min(3.0, tcg_qty / 12.0 * 3.0)
    )

    if dispersion_pct is None:
        spread = 0.0
    elif dispersion_pct <= 5:
        spread = 20.0
    elif dispersion_pct <= 10:
        spread = 20.0 - (dispersion_pct - 5.0) * 0.8
    elif dispersion_pct <= 20:
        spread = 16.0 - (dispersion_pct - 10.0) * 0.8
    elif dispersion_pct <= 35:
        spread = max(0.0, 8.0 - (dispersion_pct - 20.0) * (8.0 / 15.0))
    else:
        spread = 0.0

    effective_breadth = 0.0
    if _float(route.get("cardmarket_trend_eur")):
        effective_breadth += 1.0
    if ct and _float(ct.get("best_ct_gross_eur")):
        effective_breadth += 1.0
    if _float(route.get("ebay_expected_eur")):
        effective_breadth += 1.0
    if tcg and _float(tcg.get("_market_eur")):
        effective_breadth += 0.75  # correlated with US/eBay demand, not a full independent vote
    breadth = min(15.0, 15.0 * effective_breadth / 3.75)

    realized_velocity = ebay_confirmed + tcg_monthly
    if realized_velocity >= 10:
        immediacy = 10.0
    elif realized_velocity >= 5:
        immediacy = 8.0
    elif realized_velocity >= 2:
        immediacy = 6.0
    elif realized_velocity >= 1:
        immediacy = 4.0
    elif ct_sellers >= 3 or tcg_sellers >= 3:
        immediacy = 2.0
    else:
        immediacy = 0.0

    score = int(round(max(0.0, min(100.0, velocity + depth + spread + breadth + immediacy))))
    return score, {
        "velocity": round(velocity, 1), "depth": round(depth, 1), "spread": round(spread, 1),
        "breadth": round(breadth, 1), "immediacy": round(immediacy, 1),
    }


def _price_confidence_score(route: dict, tcg: dict | None, ebay: dict | None,
                            mapping_status: str | None, lqs: int,
                            dispersion_pct: float | None, source_count: int,
                            today: date) -> tuple[int, dict]:
    if dispersion_pct is None:
        convergence = 0.0
    else:
        convergence = 35.0 * max(0.0, 1.0 - dispersion_pct / 25.0)
        convergence *= min(1.0, source_count / 3.0)

    ebay_strength = str((ebay or {}).get("strength") or "NONE").upper()
    tcg_strength = str((tcg or {}).get("reference_strength") or "NONE").upper()
    tcg_monthly = _tcg_monthly_sales(tcg)
    transaction = 0.0
    if ebay_strength == "STRONG":
        transaction += 15.0
    elif ebay_strength == "MEDIUM":
        transaction += 10.0
    elif ebay_strength in {"WEAK", "VERY_WEAK"}:
        transaction += 3.0
    transaction += (
        min(10.0, 10.0 * math.log1p(tcg_monthly) / math.log1p(15))
        if tcg_monthly > 0
        else {"STRONG": 3.0, "MEDIUM": 2.0}.get(tcg_strength, 0.0)
    )
    transaction = min(25.0, transaction)

    freshness = 5.0  # daily Cardmarket feed is the baseline
    ebay_age = _age_days((ebay or {}).get("snapshot_date"), today)
    if ebay_age is not None:
        freshness += 5.0 if ebay_age <= 7 else (3.0 if ebay_age <= 30 else 1.0)
    tcg_age = _age_days((tcg or {}).get("checked_at"), today)
    if tcg_age is not None:
        freshness += 5.0 if tcg_age <= 7 else (3.0 if tcg_age <= 30 else 1.0)
    freshness = min(15.0, freshness)

    liquidity = 15.0 * lqs / 100.0
    identity = 10.0 if mapping_status in {"EXACT", "VERIFIED_MULTI"} else (8.0 if not mapping_status else 0.0)

    score = int(round(max(0.0, min(100.0, convergence + transaction + freshness + liquidity + identity))))
    return score, {
        "convergence": round(convergence, 1), "transaction": round(transaction, 1),
        "freshness": round(freshness, 1), "liquidity": round(liquidity, 1), "identity": round(identity, 1),
    }


def _exit_confidence_score(route: dict, ct: dict | None, ebay: dict | None,
                           fair_value: float | None, lqs: int, tcg: dict | None) -> tuple[int, dict]:
    channel = str(route.get("best_sell_channel") or "")
    gross = _float(route.get("best_sell_gross_eur"))
    if not channel or gross in (None, 0) or fair_value in (None, 0):
        return 0, {"depth": 0.0, "alignment": 0.0, "liquidity": round(15.0 * lqs / 100.0, 1), "confirmation": 0.0}

    deviation = abs(gross / fair_value - 1.0) * 100.0
    alignment = 35.0 * max(0.0, 1.0 - deviation / 35.0)
    liquidity = 15.0 * lqs / 100.0
    depth = confirmation = 0.0

    if channel.startswith("CARDTRADER") and ct:
        if channel == "CARDTRADER_ZERO":
            sellers, units = _int(ct.get("ct_zero_sellers")), _int(ct.get("ct_zero_units"))
        else:
            sellers, units = _int(ct.get("ct_direct_sellers")), _int(ct.get("ct_direct_units"))
        depth = min(30.0, sellers / 5.0 * 30.0) + min(10.0, units / 12.0 * 10.0)
        confirmations = []
        ebay_price = _float(route.get("ebay_expected_eur"))
        if ebay_price:
            confirmations.append(abs(ebay_price / gross - 1.0) * 100.0)
        # Use TCGplayer TRANSACTION market price for exit confirmation. The live
        # executable ask is supply context and must not validate a high CT exit by itself.
        tcg_price = _float((tcg or {}).get("_market_eur"))
        if tcg_price:
            confirmations.append(abs(tcg_price / gross - 1.0) * 100.0)
        if confirmations:
            best = min(confirmations)
            confirmation = 10.0 * max(0.0, 1.0 - best / 30.0)
    elif channel.startswith("EBAY"):
        strength = str((ebay or {}).get("strength") or "NONE").upper()
        depth = {"STRONG": 40.0, "MEDIUM": 30.0, "WEAK": 14.0, "VERY_WEAK": 8.0}.get(strength, 0.0)
        sales = _int((ebay or {}).get("confirmed_sales"))
        confirmation = min(10.0, 10.0 * sales / 5.0)
    else:
        depth = 10.0

    score = int(round(max(0.0, min(100.0, depth + alignment + liquidity + confirmation))))
    return score, {
        "depth": round(depth, 1), "alignment": round(alignment, 1),
        "liquidity": round(liquidity, 1), "confirmation": round(confirmation, 1),
    }


def _gate(acquisition: float | None, lqs: int, pcs: int, ecs: int, cfg: dict) -> tuple[bool, str, str]:
    qcfg = cfg.get("market_quality", {})
    high_from = float(qcfg.get("high_value_from_eur", 50.0))
    if acquisition is not None and acquisition >= high_from:
        profile = "HIGH_VALUE"
        min_lqs = int(qcfg.get("high_value_min_liquidity_score", 70))
        min_pcs = int(qcfg.get("high_value_min_price_confidence_score", 80))
        min_ecs = int(qcfg.get("high_value_min_exit_confidence_score", 70))
    else:
        profile = "STANDARD"
        min_lqs = int(qcfg.get("min_liquidity_score", 65))
        min_pcs = int(qcfg.get("min_price_confidence_score", 75))
        min_ecs = int(qcfg.get("min_exit_confidence_score", 65))
    failures = []
    if lqs < min_lqs:
        failures.append(f"LQS {lqs}<{min_lqs}")
    if pcs < min_pcs:
        failures.append(f"PCS {pcs}<{min_pcs}")
    if ecs < min_ecs:
        failures.append(f"ECS {ecs}<{min_ecs}")
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
    """Apply financial-market-style liquidity, fair-value and exit-confidence scores.

    TCGplayer transaction price/velocity confirms global fair value and liquidity.
    Its current listing floor/seller depth is stored separately as live supply context.
    Neither can create an Ireland-landed BUY or become the selected exit by itself.
    """
    today = today or date.today()
    route_rows, route_fields = _read_csv(route_path)
    ct = _ct_map(ct_path)
    ebay = _best_ebay_rows(ebay_reference_path)
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
        ebay_row = ebay.get(pid)
        tcg_row = tcg.get(pid)
        if tcg_row and _float(tcg_row.get("_market_eur")):
            tcg_used += 1

        raw_points = _market_points(row, ct_row, tcg_row, ebay_row)
        weighted = [(v, w) for v, w, _ in raw_points]
        fair = _weighted_median(weighted)
        dispersion = _weighted_mad_pct(weighted, fair)
        sources = {name for _, _, name in raw_points}

        lqs, _ = _liquidity_score(row, ct_row, tcg_row, ebay_row, fair, dispersion)
        pcs, _ = _price_confidence_score(
            row, tcg_row, ebay_row, mappings.get(pid), lqs, dispersion, len(sources), today
        )
        ecs, _ = _exit_confidence_score(row, ct_row, ebay_row, fair, lqs, tcg_row)
        acquisition = _float(row.get("best_validated_buy_eur"))
        gate_pass, profile, gate_reason = _gate(acquisition, lqs, pcs, ecs, cfg)

        eu_exec, eu_exec_source = _eu_executable_value(row)
        tcg_market = _float((tcg_row or {}).get("_market_eur"))
        tcg_recent = _float((tcg_row or {}).get("_recent_sale_eur"))
        tcg_exec = _float((tcg_row or {}).get("_executable_floor_eur"))
        tcg_item = _float((tcg_row or {}).get("_item_floor_eur"))
        tcg_ship = _float((tcg_row or {}).get("_shipping_floor_eur"))
        tcg_low = _float((tcg_row or {}).get("_low_eur"))
        tcg_vs_fair = None if tcg_market is None or fair in (None, 0) else round((tcg_market / fair - 1.0) * 100.0, 1)
        market_exec_gap = None if tcg_market in (None, 0) or tcg_exec is None else round((tcg_exec / tcg_market - 1.0) * 100.0, 1)
        recent_vs_market = None if tcg_market in (None, 0) or tcg_recent is None else round((tcg_recent / tcg_market - 1.0) * 100.0, 1)
        monthly_sales = _tcg_monthly_sales(tcg_row)
        coverage_days, supply_state = _tcg_supply_metrics(tcg_row)

        quality = {
            "snapshot_date": row.get("snapshot_date") or today.isoformat(),
            "id_product": pid,
            "name": row.get("name") or "",
            "expansion_name": row.get("expansion_name") or "",
            "number": row.get("number") or "",
            "fair_value_eur": fair if fair is not None else "",
            "fair_value_scope": "GLOBAL_TRANSACTIONAL",
            "eu_executable_value_eur": eu_exec if eu_exec is not None else "",
            "eu_executable_source": eu_exec_source,
            "cross_market_dispersion_pct": "" if dispersion is None else round(dispersion, 1),
            "independent_market_count": len(sources),
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
            "tcgplayer_vs_fair_pct": "" if tcg_vs_fair is None else tcg_vs_fair,
            "liquidity_score": lqs,
            "liquidity_label": _label(lqs, ((85, "EXTREMELY_LIQUID"), (70, "HIGH"), (55, "MODERATE"), (40, "THIN"), (0, "ILLIQUID"))),
            "price_confidence_score": pcs,
            "price_confidence_label": _label(pcs, ((85, "VERY_HIGH"), (75, "HIGH"), (60, "MEDIUM"), (40, "LOW"), (0, "VERY_LOW"))),
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
                + f"; market-quality gate failed: {gate_reason}; LQS={lqs}, PCS={pcs}, ECS={ecs}"
            ).strip("; ")
        elif gate_pass:
            row["notes"] = (
                str(row.get("notes") or "")
                + f"; market-quality gate passed ({profile}): LQS={lqs}, PCS={pcs}, ECS={ecs}"
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
        "policy": "TCGplayer transaction price/velocity informs global fair value and liquidity; exact live quantity/sellers/executable floor remain separate supply context and cannot create an Ireland BUY.",
    }
