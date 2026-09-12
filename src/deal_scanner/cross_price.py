from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferenceBand:
    label: str
    min_eur: float
    max_eur: float | None


DEFAULT_REFERENCE_BANDS = [
    {"label": "REF_0_10", "min_reference_eur": 0.0, "max_reference_eur": 10.0},
    {"label": "REF_10_30", "min_reference_eur": 10.0, "max_reference_eur": 30.0},
    {"label": "REF_30_50", "min_reference_eur": 30.0, "max_reference_eur": 50.0},
    {"label": "REF_50_100", "min_reference_eur": 50.0, "max_reference_eur": 100.0},
    {"label": "REF_100_PLUS", "min_reference_eur": 100.0, "max_reference_eur": None},
]


def configured_bands(cfg: dict) -> list[ReferenceBand]:
    raw = (cfg.get("cross_price_research") or {}).get("reference_bands") or DEFAULT_REFERENCE_BANDS
    out: list[ReferenceBand] = []
    for band in raw:
        out.append(
            ReferenceBand(
                label=str(band.get("label") or "UNLABELLED"),
                min_eur=float(band.get("min_reference_eur") or 0.0),
                max_eur=None if band.get("max_reference_eur") in (None, "") else float(band["max_reference_eur"]),
            )
        )
    return out


def reference_band(value: float | None, cfg: dict) -> str | None:
    if value is None or value <= 0:
        return None
    for band in configured_bands(cfg):
        if value < band.min_eur:
            continue
        if band.max_eur is None or value < band.max_eur:
            return band.label
    return None


def build_cross_price_research(rows: list[dict], cfg: dict) -> list[dict]:
    """Build a research-only cross-price candidate panel.

    This is deliberately not a BUY/route score. It samples candidates across
    reference-value bands using Cardmarket avg30 as a diagnostic reference.
    Validated EN/NM acquisition evidence is preferred when present; otherwise the
    generic Cardmarket low may be used only as a screening price and is explicitly
    labelled as such.
    """
    rcfg = cfg.get("cross_price_research") or {}
    per_band = int(rcfg.get("candidates_per_band", 15))
    min_age = int((cfg.get("rules") or {}).get("min_product_age_days_for_flip_signal", 0))
    min_reference = float(rcfg.get("minimum_reference_eur", 0.20))

    grouped: dict[str, list[dict]] = {band.label: [] for band in configured_bands(cfg)}

    for source in rows:
        row = dict(source)
        reference = row.get("avg30")
        try:
            reference = None if reference in (None, "") else float(reference)
        except (TypeError, ValueError):
            reference = None
        if reference is None or reference < min_reference:
            continue

        age = row.get("product_age_days")
        if age is not None:
            try:
                if int(age) < min_age:
                    continue
            except (TypeError, ValueError):
                pass

        validated = row.get("best_validated_sourcing_price")
        generic_low = row.get("low")
        try:
            validated = None if validated in (None, "") else float(validated)
        except (TypeError, ValueError):
            validated = None
        try:
            generic_low = None if generic_low in (None, "") else float(generic_low)
        except (TypeError, ValueError):
            generic_low = None

        screening_price = validated if validated is not None else generic_low
        if screening_price is None or screening_price <= 0:
            continue

        headroom = reference - screening_price
        if headroom <= 0:
            continue

        band = reference_band(reference, cfg)
        if band is None or band not in grouped:
            continue

        gap_pct = headroom / reference * 100.0
        acquisition_basis = "VALIDATED_EN_NM" if validated is not None else "CARDMARKET_GENERIC_LOW_SCREENING_ONLY"
        research_state = "READY_FOR_ROUTE_ECONOMICS" if validated is not None else "NEEDS_VALIDATED_ACQUISITION"

        row.update(
            {
                "reference_band": band,
                "reference_value_eur": round(reference, 2),
                "reference_basis": "CARDMARKET_AVG30_DIAGNOSTIC",
                "screening_acquisition_eur": round(screening_price, 2),
                "acquisition_basis": acquisition_basis,
                "gross_headroom_eur": round(headroom, 2),
                "friction_budget_eur": round(headroom, 2),
                "cross_price_gap_pct": round(gap_pct, 1),
                "research_state": research_state,
            }
        )
        grouped[band].append(row)

    selected: list[dict] = []
    for band in configured_bands(cfg):
        candidates = grouped.get(band.label, [])
        candidates.sort(
            key=lambda row: (
                0 if row.get("acquisition_basis") == "VALIDATED_EN_NM" else 1,
                -float(row.get("gross_headroom_eur") or 0.0),
                -float(row.get("cross_price_gap_pct") or 0.0),
                -float(row.get("popularity_score") or 0.0),
                -float(row.get("ct_visible_sellers") or 0.0),
                int(row.get("id_product") or 0),
            )
        )
        selected.extend(candidates[:per_band])

    return selected
