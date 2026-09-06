from __future__ import annotations

import math
import re


def matches_hit(name: str, patterns: list[str]) -> bool:
    return any(re.search(p, name, flags=re.IGNORECASE) for p in patterns)


def popularity_score(name: str, popularity: dict[str, float]) -> float:
    lname = name.lower()
    hits = [float(score) for pokemon, score in popularity.items() if pokemon.lower() in lname]
    return max(hits) if hits else 0.45


def safe_gap_pct(low: float | None, avg30: float | None) -> float | None:
    if low is None or avg30 is None or avg30 <= 0:
        return None
    return (avg30 - low) / avg30 * 100.0


def volatility(hist_avg: float | None, hist_avg_sq: float | None) -> float | None:
    if hist_avg in (None, 0) or hist_avg_sq is None:
        return None
    variance = max(0.0, hist_avg_sq - hist_avg * hist_avg)
    return math.sqrt(variance) / hist_avg


def score_row(row: dict, cfg: dict) -> dict:
    low = row.get("low")
    avg30 = row.get("avg30")
    cm_en = row.get("cm_en_nm_floor")
    ct_en = row.get("ct_en_nm_floor")
    pop = popularity_score(row["name"], cfg["rules"]["popularity"])
    vol = volatility(row.get("hist_avg_low"), row.get("hist_avg_sq"))

    generic_discovery = low is not None and low <= cfg["rules"]["cheap_hit_discovery_low_max_eur"]
    cm_price_candidate = cm_en is not None and cm_en <= cfg["rules"]["cheap_hit_actionable_en_nm_max_eur"]
    ct_actionable = ct_en is not None and ct_en <= cfg["cardtrader"]["actionable_en_nm_max_eur"]

    # Generic Cardmarket low is intentionally discovery-only: it may be a cheaper
    # language/condition and therefore must never create the flip-price gap.
    generic_gap = safe_gap_pct(low, avg30)

    # Only validated EN/NM evidence can define the acquisition price used for the
    # flip gap and price score. Cardmarket BUY still requires Ireland shipping and
    # landed-cost validation in the separate sourcing layer.
    validated_prices = [x for x in (cm_en, ct_en) if x is not None]
    sourcing_price = min(validated_prices) if validated_prices else None
    validated_gap = safe_gap_pct(sourcing_price, avg30)

    price_score = 0.0 if sourcing_price is None else max(0.0, 1.0 - min(sourcing_price, 2.0) / 2.0)
    gap_score = 0.0 if validated_gap is None else max(0.0, min(validated_gap / 80.0, 1.0))
    avg_support = 0.0 if avg30 is None else max(0.0, min(avg30 / 2.0, 1.0))
    supply = row.get("ct_visible_units") or 0
    supply_score = min(float(supply) / 10.0, 1.0)
    score = 100 * (0.36 * price_score + 0.23 * gap_score + 0.23 * pop + 0.10 * avg_support + 0.08 * supply_score)

    if ct_actionable:
        status = "BUY_CT_EN_NM"
    elif cm_price_candidate:
        status = "CHECK_CM_IRELAND_LANDED"
    elif sourcing_price is not None:
        status = "WATCH_VALIDATED_EN_NM"
    elif generic_discovery:
        status = "VALIDATE_EN_NM"
    else:
        status = "WATCH"

    return {
        **row,
        # Compatibility field: from v0.5 onward gap_pct always means the gap from
        # validated EN/NM acquisition evidence, never the generic Cardmarket low.
        "gap_pct": validated_gap,
        "generic_gap_pct": generic_gap,
        "popularity_score": pop,
        "volatility_30d": vol,
        "generic_discovery": generic_discovery,
        "cm_actionable": False,
        "cm_price_candidate": cm_price_candidate,
        "ct_actionable": ct_actionable,
        "best_validated_sourcing_price": sourcing_price,
        "deal_score": round(score, 1),
        "status": status,
    }
