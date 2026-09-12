from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "dashboard" / "data" / "dashboard_snapshot.json"
CROSS_PRICE_PATH = ROOT / "dashboard" / "data" / "cross_price_research_preview.csv"


def _blank(value) -> bool:
    return value is None or str(value).strip().lower() in {"", "none", "nan", "null"}


def _float(value):
    try:
        return None if _blank(value) else float(value)
    except (TypeError, ValueError):
        return None


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _discovery_row(source: dict) -> dict:
    validated = str(source.get("acquisition_basis") or "") == "VALIDATED_EN_NM"
    screening = _float(source.get("screening_acquisition_eur"))
    headroom = _float(source.get("gross_headroom_eur"))
    band = str(source.get("reference_band") or "UNKNOWN")
    evidence = "validated EN/NM" if validated else "generic Cardmarket low; validation required"
    note = (
        f"Cross-price research {band}; screening headroom "
        f"€{headroom:.2f}; acquisition evidence: {evidence}."
        if headroom is not None
        else f"Cross-price research {band}; acquisition evidence: {evidence}."
    )
    return {
        "snapshot_date": source.get("snapshot_date"),
        "id_product": source.get("id_product"),
        "name": source.get("name"),
        "expansion_name": source.get("expansion_name"),
        "number": source.get("number"),
        "rarity": source.get("rarity"),
        # Never expose a generic Cardmarket low through the dashboard field named
        # 'validated sourcing price'. Generic-low rows intentionally show no buy.
        "best_validated_sourcing_price": screening if validated else None,
        "deal_score": _float(source.get("deal_score")),
        "status": "CROSS_PRICE_VALIDATED_EN_NM" if validated else "CROSS_PRICE_NEEDS_VALIDATION",
        "trend": _float(source.get("trend")),
        "avg30": _float(source.get("reference_value_eur")) or _float(source.get("avg30")),
        "avg7": _float(source.get("avg7")),
        "avg1": _float(source.get("avg1")),
        "cm_en_nm_floor": _float(source.get("cm_en_nm_floor")),
        "ct_en_nm_floor": _float(source.get("ct_en_nm_floor")),
        "ct_visible_sellers": _float(source.get("ct_visible_sellers")),
        "ct_visible_units": _float(source.get("ct_visible_units")),
        "gap_pct": _float(source.get("cross_price_gap_pct")),
        "popularity_score": _float(source.get("popularity_score")),
        "research_note": note,
        # Extra research-only fields are safe for the public snapshot and allow a
        # future UI revision without changing scanner BUY/FV logic.
        "reference_band": band,
        "reference_value_eur": _float(source.get("reference_value_eur")),
        "screening_acquisition_eur": screening,
        "screening_acquisition_source": source.get("screening_acquisition_source"),
        "acquisition_basis": source.get("acquisition_basis"),
        "identity_source": source.get("identity_source"),
        "cardtrader_version": source.get("cardtrader_version"),
        "gross_headroom_eur": headroom,
        "friction_budget_eur": _float(source.get("friction_budget_eur")),
        "cross_price_gap_pct": _float(source.get("cross_price_gap_pct")),
        "research_state": source.get("research_state"),
    }


def main() -> int:
    if not SNAPSHOT_PATH.exists():
        raise SystemExit(f"Missing dashboard snapshot: {SNAPSHOT_PATH}")
    if not CROSS_PRICE_PATH.exists():
        raise SystemExit(f"Missing cross-price preview: {CROSS_PRICE_PATH}")

    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    cross_rows = [_discovery_row(row) for row in _read_csv(CROSS_PRICE_PATH)]

    # Preserve explicit research watches such as Zeraora. The old cheap-ranked
    # top-flip rows remain available in scanner outputs but no longer monopolise
    # the hosted dashboard discovery/card-detail universe.
    cross_ids = {str(row.get("id_product") or "") for row in cross_rows}
    research_watches = []
    for row in list(snapshot.get("discovery_candidates") or []):
        pid = str(row.get("id_product") or "")
        if str(row.get("status") or "").upper() == "RESEARCH_WATCH" and pid not in cross_ids:
            research_watches.append(row)

    snapshot["discovery_candidates"] = cross_rows + research_watches
    snapshot["discovery_mode"] = "CROSS_PRICE_RESEARCH_15_PER_REFERENCE_BAND"
    snapshot["discovery_note"] = (
        "Hosted discovery is a research-balanced 75-card panel across five Cardmarket 30d reference bands. "
        "Generic-low screening rows are never exposed as validated acquisition prices."
    )
    SNAPSHOT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Dashboard discovery replaced with {len(cross_rows)} cross-price rows + "
        f"{len(research_watches)} explicit research watches"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
