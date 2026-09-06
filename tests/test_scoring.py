from __future__ import annotations

from pathlib import Path

from deal_scanner.config import load_config
from deal_scanner.reports import build_top_flips
from deal_scanner.scoring import score_row


ROOT = Path(__file__).resolve().parents[1]


def _base_row():
    return {
        "id_product": 1,
        "name": "Dragonite V",
        "low": 0.50,
        "avg30": 10.00,
        "cm_en_nm_floor": None,
        "ct_en_nm_floor": None,
        "hist_avg_low": None,
        "hist_avg_sq": None,
        "ct_visible_units": 0,
    }


def test_generic_low_is_discovery_only_for_flip_gap():
    cfg = load_config(ROOT / "config.yaml")
    scored = score_row(_base_row(), cfg)

    assert round(scored["generic_gap_pct"], 1) == 95.0
    assert scored["gap_pct"] is None
    assert scored["best_validated_sourcing_price"] is None
    assert scored["status"] == "VALIDATE_EN_NM"

    scored["product_age_days"] = 100
    assert build_top_flips([scored], cfg) == []


def test_validated_en_nm_price_defines_flip_gap_not_generic_low():
    cfg = load_config(ROOT / "config.yaml")
    row = _base_row()
    row["cm_en_nm_floor"] = 8.00
    scored = score_row(row, cfg)

    # Generic low still appears as discovery context, but the actual flip gap is
    # calculated from the validated English/NM price: (10 - 8) / 10 = 20%.
    assert round(scored["generic_gap_pct"], 1) == 95.0
    assert round(scored["gap_pct"], 1) == 20.0
    assert scored["best_validated_sourcing_price"] == 8.00

    scored["product_age_days"] = 100
    flips = build_top_flips([scored], cfg)
    assert len(flips) == 1
    assert flips[0]["id_product"] == 1
