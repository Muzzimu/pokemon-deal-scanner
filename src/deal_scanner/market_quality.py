from __future__ import annotations

import csv
import math
import statistics
from datetime import date, datetime
from pathlib import Path


QUALITY_FIELDS = [
    "snapshot_date", "id_product", "name", "expansion_name", "number",
    "fair_value_eur", "cross_market_dispersion_pct", "independent_market_count",
    "tcgplayer_market_eur", "tcgplayer_low_eur", "tcgplayer_sales_30d",
    "tcgplayer_listing_count", "tcgplayer_strength", "tcgplayer_vs_fair_pct",
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


def _best_tcg_rows(path: Path, cfg: dict) -> dict[str, dict]:
    rows, _ = _read_csv(path)
    fallback_usd_to_eur = float(cfg.get("fx", {}).get("fallback_usd_to_eur", 0.86))
    strength_rank = {"STRONG": 0, "MEDIUM": 1, "WEAK": 2, "VERY_WEAK": 3, "NONE": 9}
    out: dict[str, dict] = {}
    for raw in rows:
        pid = str(raw.get("id_product") or "").strip()
        if not pid:
            continue
        market_eur = _float(raw.get("market_price_eur"))
        low_eur = _float(raw.get("low_price_eur"))
        fx = _float(raw.get("fx_usd_to_eur")) or fallback_usd_to_eur
        fx_source = "ROW" if _float(raw.get("fx_usd_to_eur")) else "CONFIG_FALLBACK"
        if market_eur is None:
            usd = _float(raw.get("market_price_usd"))
            market_eur = None if usd is None else round(usd * fx, 2)
        if low_eur is None:
            usd = _float(raw.get("low_price_usd"))
            low_eur = None if usd is None else round(usd * fx, 2)
        row = {
            **raw,
            "_market_eur": market_eur,
            "_low_eur": low_eur,
            "_fx_source": fx_source,
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


def _market_points(route: dict, ct: dict | None, tcg: dict | None, ebay: dict | None) -> list[tuple[float, float, str]]:
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
    tcg_sales = _int((tcg or {}).get("sales_30d"))
    total_sales = ebay_confirmed + tcg_sales + int(round(0.5 * ebay_inferred))
    velocity = 0.0 if total_sales <= 0 else min(30.0, 30.0 * math.log1p(total_sales) / math.log1p(20))

    sellers = units = 0
    if ct:
        if str(ct.get("best_ct_channel")) == "CARDTRADER_ZERO":
            sellers = _int(ct.get("ct_zero_sellers"))
            units = _int(ct.get("ct_zero_units"))
        else:
            sellers = _int(ct.get("ct_direct_sellers"))
            units = _int(ct.get("ct_direct_units"))
    tcg_listings = _int((tcg or {}).get("listing_count"))
    depth = min(12.0, sellers / 5.0 * 12.0) + min(6.0, units / 12.0 * 6.0) + min(7.0, tcg_listings / 20.0 * 7.0)

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
        effective_breadth += 0.75  # correlated with US/eBay demand, so not a full independent vote
    breadth = min(15.0, 15.0 * effective_breadth / 3.75)

    if ebay_confirmed + tcg_sales >= 10:
        immediacy = 10.0
    elif ebay_confirmed + tcg_sales >= 5:
        immediacy = 8.0
    elif ebay_confirmed + tcg_sales >= 2:
        immediacy = 6.0
    elif ebay_confirmed + tcg_sales >= 1:
        immediacy = 4.0
    elif sellers >= 3:
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
    ebay_confirmed = _int((ebay or {}).get("confirmed_sales"))
    tcg_strength = str((tcg or {}).get("reference_strength") or "NONE").upper()
    tcg_sales = _int((tcg or {}).get("sales_30d"))
    transaction = 0.0
    if ebay_strength == "STRONG":
        transaction += 15.0
    elif ebay_strength == "MEDIUM":
        transaction += 10.0
    elif ebay_strength in {"WEAK", "VERY_WEAK"}:
        transaction += 3.0
    transaction += min(10.0, 10.0 * math.log1p(tcg_sales) / math.log1p(15)) if tcg_sales > 0 else ({"STRONG": 3.0, "MEDIUM": 2.0}.get(tcg_strength, 0.0))
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

    TCGplayer is a supporting valuation/liquidity market only. Its evidence can
    confirm or challenge a CardTrader exit price, but it never creates a sourcing
    BUY or becomes the selected exit channel in this function.
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

        lqs, lparts = _liquidity_score(row, ct_row, tcg_row, ebay_row, fair, dispersion)
        pcs, pparts = _price_confidence_score(
            row, tcg_row, ebay_row, mappings.get(pid), lqs, dispersion, len(sources), today
        )
        ecs, eparts = _exit_confidence_score(row, ct_row, ebay_row, fair, lqs, tcg_row)
        acquisition = _float(row.get("best_validated_buy_eur"))
        gate_pass, profile, gate_reason = _gate(acquisition, lqs, pcs, ecs, cfg)

        tcg_market = _float((tcg_row or {}).get("_market_eur"))
        tcg_low = _float((tcg_row or {}).get("_low_eur"))
        tcg_vs_fair = None if tcg_market is None or fair in (None, 0) else round((tcg_market / fair - 1.0) * 100.0, 1)

        quality = {
            "snapshot_date": row.get("snapshot_date") or today.isoformat(),
            "id_product": pid,
            "name": row.get("name") or "",
            "expansion_name": row.get("expansion_name") or "",
            "number": row.get("number") or "",
            "fair_value_eur": fair if fair is not None else "",
            "cross_market_dispersion_pct": "" if dispersion is None else round(dispersion, 1),
            "independent_market_count": len(sources),
            "tcgplayer_market_eur": tcg_market if tcg_market is not None else "",
            "tcgplayer_low_eur": tcg_low if tcg_low is not None else "",
            "tcgplayer_sales_30d": _int((tcg_row or {}).get("sales_30d")),
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
        "policy": "TCGplayer confirms/challenges fair value and liquidity; it cannot create a BUY or exit route by itself.",
    }
