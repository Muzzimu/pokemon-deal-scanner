from __future__ import annotations

import csv
import math
from pathlib import Path


CT_INTELLIGENCE_FIELDS = [
    "price_band", "required_min_spread_eur", "required_min_roi_pct",
    "manual_verification_required", "ct_gap_net_vs_buy_pct",
    "ct_premium_vs_cm_trend_pct", "ct_vs_ebay_pct", "ct_lag_score", "ct_lag_label",
]

ROUTE_INTELLIGENCE_FIELDS = list(CT_INTELLIGENCE_FIELDS)

CORE_WATCH_FIELDS = [
    "snapshot_date", "id_product", "name", "expansion_name", "number",
    "reference_value_eur", "validated_buy_eur", "ct_best_channel", "ct_best_gross_eur",
    "ct_best_net_eur", "ct_sellers", "ct_units", "ebay_expected_eur", "ebay_strength",
    "net_spread_eur", "net_roi_pct", "price_band", "required_min_spread_eur",
    "required_min_roi_pct", "ct_lag_score", "ct_lag_label", "watch_priority", "watch_reason",
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
        return int(value)
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


def _price_band(acquisition_eur: float, cfg: dict) -> dict:
    rcfg = cfg.get("cardtrader_resale", {})
    bands = rcfg.get("price_bands") or []
    for band in bands:
        maximum = _float(band.get("max_acquisition_eur"))
        if maximum is None or acquisition_eur <= maximum:
            return {
                "label": str(band.get("label") or "configured"),
                "min_spread": float(band.get("min_net_spread_eur", rcfg.get("minimum_net_spread_eur", 2.0))),
                "min_roi": float(band.get("min_net_roi_pct", rcfg.get("minimum_net_roi_pct", 25.0))),
            }
    return {
        "label": "fallback",
        "min_spread": float(rcfg.get("minimum_net_spread_eur", 2.0)),
        "min_roi": float(rcfg.get("minimum_net_roi_pct", 25.0)),
    }


def _best_ct_depth(ct_row: dict) -> tuple[int, int]:
    channel = str(ct_row.get("best_ct_channel") or "")
    if channel == "CARDTRADER_ZERO":
        return _int(ct_row.get("ct_zero_sellers")), _int(ct_row.get("ct_zero_units"))
    return _int(ct_row.get("ct_direct_sellers")), _int(ct_row.get("ct_direct_units"))


def _ebay_map(path: Path) -> dict[str, dict]:
    rows, _ = _read_csv(path)
    out: dict[str, dict] = {}
    strength_rank = {"STRONG": 0, "MEDIUM": 1, "WEAK": 2, "VERY_WEAK": 3, "NONE": 9}
    for row in rows:
        pid = str(row.get("id_product") or "")
        if not pid:
            continue
        current = out.get(pid)
        if current is None:
            out[pid] = row
            continue
        a = strength_rank.get(str(row.get("reference_strength") or "NONE").upper(), 9)
        b = strength_rank.get(str(current.get("reference_strength") or "NONE").upper(), 9)
        if a < b:
            out[pid] = row
        elif a == b:
            new_price = _float(row.get("expected_resale_eur")) or 999999.0
            old_price = _float(current.get("expected_resale_eur")) or 999999.0
            if new_price < old_price:
                out[pid] = row
    return out


def _lag_metrics(acquisition: float, ct_row: dict | None, route_row: dict, ebay_row: dict | None) -> dict:
    if not ct_row:
        return {
            "gap_pct": None, "premium_cm_pct": None, "vs_ebay_pct": None,
            "score": 0, "label": "NONE", "sellers": 0, "units": 0,
        }

    ct_net = _float(ct_row.get("best_ct_net_eur"))
    ct_gross = _float(ct_row.get("best_ct_gross_eur"))
    cm_trend = _float(route_row.get("cardmarket_trend_eur"))
    ebay_expected = _float(ebay_row.get("expected_resale_eur")) if ebay_row else None
    ebay_strength = str(ebay_row.get("reference_strength") or "NONE").upper() if ebay_row else "NONE"
    sellers, units = _best_ct_depth(ct_row)

    gap_pct = None if ct_net is None else round((ct_net / acquisition - 1.0) * 100.0, 1)
    premium_cm_pct = None
    if ct_gross is not None and cm_trend not in (None, 0):
        premium_cm_pct = round((ct_gross / cm_trend - 1.0) * 100.0, 1)
    vs_ebay_pct = None
    if ct_gross is not None and ebay_expected not in (None, 0):
        vs_ebay_pct = round((ct_gross / ebay_expected - 1.0) * 100.0, 1)

    # 0-100 score. A large CM->CT net gap creates the opportunity, but seller
    # depth and cross-market confirmation are needed before it can rank highly.
    positive_gap = max(0.0, gap_pct or 0.0)
    gap_component = min(50.0, positive_gap / 50.0 * 50.0)
    seller_component = min(20.0, sellers / 4.0 * 20.0)
    unit_component = min(10.0, units / 10.0 * 10.0)
    confirmation_component = 0.0
    if ct_gross and ebay_expected and ebay_strength in {"STRONG", "MEDIUM"}:
        ratio = ebay_expected / ct_gross
        if ratio >= 0.90:
            confirmation_component = 20.0
        elif ratio >= 0.80:
            confirmation_component = 16.0
        elif ratio >= 0.70:
            confirmation_component = 10.0
        elif ratio >= 0.60:
            confirmation_component = 5.0

    score = int(round(min(100.0, gap_component + seller_component + unit_component + confirmation_component)))
    if score >= 70:
        label = "HIGH"
    elif score >= 50:
        label = "MEDIUM"
    elif score >= 30:
        label = "LOW"
    else:
        label = "NONE"
    return {
        "gap_pct": gap_pct,
        "premium_cm_pct": premium_cm_pct,
        "vs_ebay_pct": vs_ebay_pct,
        "score": score,
        "label": label,
        "sellers": sellers,
        "units": units,
    }


def _dynamic_signal(existing_signal: str, spread: float | None, roi: float | None,
                    band: dict, manual_verify: bool) -> str:
    if spread is None or roi is None:
        return "INSUFFICIENT_EXIT_REFERENCE" if existing_signal == "INSUFFICIENT_EXIT_REFERENCE" else "NO_EDGE"
    meets = spread >= float(band["min_spread"]) and roi >= float(band["min_roi"])
    if not meets:
        return "NO_EDGE"
    if manual_verify:
        return "WATCH_ONLY"
    return "RESELL_TEST" if existing_signal == "RESELL_TEST" else "WATCH_ONLY"


def apply_route_intelligence(cfg: dict, ct_path: Path, route_path: Path,
                             ebay_resale_path: Path, core_watch_path: Path) -> dict:
    """Re-rank v0.8 routes using price-tier risk, CT/CM lag and a liquid watch universe."""
    ct_rows, ct_fields = _read_csv(ct_path)
    route_rows, route_fields = _read_csv(route_path)
    ebay = _ebay_map(ebay_resale_path)
    ct_by_pid = {str(r.get("id_product") or ""): r for r in ct_rows}
    routes_by_pid = {str(r.get("id_product") or ""): r for r in route_rows}

    rcfg = cfg.get("cardtrader_resale", {})
    manual_above = float(rcfg.get("manual_verify_above_eur", 100.0))

    for row in route_rows:
        pid = str(row.get("id_product") or "")
        acquisition = _float(row.get("best_validated_buy_eur"))
        if acquisition is None or acquisition <= 0:
            continue
        band = _price_band(acquisition, cfg)
        manual = acquisition >= manual_above
        lag = _lag_metrics(acquisition, ct_by_pid.get(pid), row, ebay.get(pid))
        row.update({
            "price_band": band["label"],
            "required_min_spread_eur": round(float(band["min_spread"]), 2),
            "required_min_roi_pct": round(float(band["min_roi"]), 1),
            "manual_verification_required": int(manual),
            "ct_gap_net_vs_buy_pct": lag["gap_pct"],
            "ct_premium_vs_cm_trend_pct": lag["premium_cm_pct"],
            "ct_vs_ebay_pct": lag["vs_ebay_pct"],
            "ct_lag_score": lag["score"],
            "ct_lag_label": lag["label"],
        })
        row["route_signal"] = _dynamic_signal(
            str(row.get("route_signal") or "NO_EDGE"),
            _float(row.get("net_spread_eur")), _float(row.get("net_roi_pct")), band, manual,
        )
        extra = (
            f"v0.8.1 price-band gate={band['label']} requires >=EUR {band['min_spread']:.2f} "
            f"and >= {band['min_roi']:.1f}% ROI; CT lag score={lag['score']}/{lag['label']}"
        )
        if manual:
            extra += f"; acquisition >= EUR {manual_above:.2f} requires manual photo/condition verification"
        row["notes"] = (str(row.get("notes") or "") + "; " + extra).strip("; ")

    for row in ct_rows:
        pid = str(row.get("id_product") or "")
        acquisition = _float(row.get("acquisition_eur"))
        if acquisition is None or acquisition <= 0:
            continue
        band = _price_band(acquisition, cfg)
        manual = acquisition >= manual_above
        route = routes_by_pid.get(pid, {})
        lag = _lag_metrics(acquisition, row, route, ebay.get(pid))
        row.update({
            "price_band": band["label"],
            "required_min_spread_eur": round(float(band["min_spread"]), 2),
            "required_min_roi_pct": round(float(band["min_roi"]), 1),
            "manual_verification_required": int(manual),
            "ct_gap_net_vs_buy_pct": lag["gap_pct"],
            "ct_premium_vs_cm_trend_pct": lag["premium_cm_pct"],
            "ct_vs_ebay_pct": lag["vs_ebay_pct"],
            "ct_lag_score": lag["score"],
            "ct_lag_label": lag["label"],
        })
        row["ct_signal"] = _dynamic_signal(
            str(row.get("ct_signal") or "NO_EDGE"),
            _float(row.get("net_spread_eur")), _float(row.get("net_roi_pct")), band, manual,
        )
        extra = (
            f"v0.8.1 price-band gate={band['label']} requires >=EUR {band['min_spread']:.2f} "
            f"and >= {band['min_roi']:.1f}% ROI; CT lag score={lag['score']}/{lag['label']}"
        )
        if manual:
            extra += f"; acquisition >= EUR {manual_above:.2f} requires manual photo/condition verification"
        row["notes"] = (str(row.get("notes") or "") + "; " + extra).strip("; ")

    _write_csv(ct_path, ct_rows, _append_fields(ct_fields, CT_INTELLIGENCE_FIELDS))
    _write_csv(route_path, route_rows, _append_fields(route_fields, ROUTE_INTELLIGENCE_FIELDS))

    wcfg = cfg.get("core_watch", {})
    min_value = float(wcfg.get("min_reference_value_eur", 15.0))
    max_value = float(wcfg.get("max_reference_value_eur", 120.0))
    min_sellers = int(wcfg.get("minimum_ct_sellers", 2))
    min_units = int(wcfg.get("minimum_ct_units", 2))
    max_rows = int(wcfg.get("max_rows", 100))
    require_confirmation = bool(wcfg.get("require_ebay_or_three_ct_sellers", True))

    core_rows: list[dict] = []
    for route in route_rows:
        pid = str(route.get("id_product") or "")
        ct = ct_by_pid.get(pid)
        if not ct:
            continue
        reference = _float(route.get("cardmarket_trend_eur")) or _float(route.get("best_validated_buy_eur"))
        if reference is None or not (min_value <= reference <= max_value):
            continue
        sellers, units = _best_ct_depth(ct)
        if sellers < min_sellers or units < min_units:
            continue
        ebay_row = ebay.get(pid)
        ebay_strength = str(ebay_row.get("reference_strength") or "NONE").upper() if ebay_row else "NONE"
        if require_confirmation and ebay_strength not in {"STRONG", "MEDIUM"} and sellers < 3:
            continue
        lag_score = _int(route.get("ct_lag_score"))
        if lag_score >= 70:
            priority = "A"
        elif lag_score >= 50:
            priority = "B"
        else:
            priority = "C"
        core_rows.append({
            "snapshot_date": route.get("snapshot_date") or "",
            "id_product": pid,
            "name": route.get("name") or "",
            "expansion_name": route.get("expansion_name") or "",
            "number": route.get("number") or "",
            "reference_value_eur": round(reference, 2),
            "validated_buy_eur": route.get("best_validated_buy_eur") or "",
            "ct_best_channel": ct.get("best_ct_channel") or "",
            "ct_best_gross_eur": ct.get("best_ct_gross_eur") or "",
            "ct_best_net_eur": ct.get("best_ct_net_eur") or "",
            "ct_sellers": sellers,
            "ct_units": units,
            "ebay_expected_eur": route.get("ebay_expected_eur") or "",
            "ebay_strength": ebay_strength,
            "net_spread_eur": ct.get("net_spread_eur") or "",
            "net_roi_pct": ct.get("net_roi_pct") or "",
            "price_band": route.get("price_band") or "",
            "required_min_spread_eur": route.get("required_min_spread_eur") or "",
            "required_min_roi_pct": route.get("required_min_roi_pct") or "",
            "ct_lag_score": lag_score,
            "ct_lag_label": route.get("ct_lag_label") or "",
            "watch_priority": priority,
            "watch_reason": (
                f"CM reference EUR {reference:.2f}; CT sellers={sellers}, units={units}; "
                f"eBay strength={ebay_strength}; lag={lag_score}"
            ),
        })

    core_rows.sort(key=lambda r: (
        {"A": 0, "B": 1, "C": 2}.get(str(r.get("watch_priority")), 9),
        -_int(r.get("ct_lag_score")),
        -(_float(r.get("net_spread_eur")) or -999999.0),
    ))
    core_rows = core_rows[:max_rows]
    _write_csv(core_watch_path, core_rows, CORE_WATCH_FIELDS)

    return {
        "price_band_rows": len(route_rows),
        "manual_verification_rows": sum(1 for r in route_rows if str(r.get("manual_verification_required")) == "1"),
        "high_lag_rows": sum(1 for r in route_rows if str(r.get("ct_lag_label")) == "HIGH"),
        "medium_lag_rows": sum(1 for r in route_rows if str(r.get("ct_lag_label")) == "MEDIUM"),
        "core_watch_rows": len(core_rows),
        "core_watch_a_priority": sum(1 for r in core_rows if r["watch_priority"] == "A"),
        "note": "Dynamic price-band risk gates, CT/CM lag scoring, and a liquid Core watch universe applied after base route construction.",
    }
