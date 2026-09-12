from deal_scanner.cross_price import build_cross_price_research, reference_band


def row(pid, avg30, low, validated=None, popularity=0.45):
    return {
        "id_product": pid,
        "name": f"Card {pid}",
        "avg30": avg30,
        "low": low,
        "best_validated_sourcing_price": validated,
        "product_age_days": 100,
        "popularity_score": popularity,
        "ct_visible_sellers": 0,
    }


def test_default_reference_bands_cover_cross_price_range():
    cfg = {"rules": {"min_product_age_days_for_flip_signal": 14}}
    assert reference_band(5.0, cfg) == "REF_0_10"
    assert reference_band(10.0, cfg) == "REF_10_30"
    assert reference_band(30.0, cfg) == "REF_30_50"
    assert reference_band(50.0, cfg) == "REF_50_100"
    assert reference_band(100.0, cfg) == "REF_100_PLUS"


def test_selects_per_band_and_labels_generic_screening():
    cfg = {
        "rules": {"min_product_age_days_for_flip_signal": 14},
        "cross_price_research": {"candidates_per_band": 1},
    }
    rows = [
        row(1, 5.0, 1.0),
        row(2, 20.0, 10.0, validated=12.0),
        row(3, 40.0, 20.0),
        row(4, 70.0, 30.0),
        row(5, 150.0, 80.0),
    ]
    selected = build_cross_price_research(rows, cfg)
    assert len(selected) == 5
    assert [r["reference_band"] for r in selected] == [
        "REF_0_10", "REF_10_30", "REF_30_50", "REF_50_100", "REF_100_PLUS"
    ]
    assert selected[0]["acquisition_basis"] == "CARDMARKET_GENERIC_LOW_SCREENING_ONLY"
    assert selected[0]["research_state"] == "NEEDS_VALIDATED_ACQUISITION"
    assert selected[1]["acquisition_basis"] == "VALIDATED_EN_NM"
    assert selected[1]["gross_headroom_eur"] == 8.0
    assert selected[1]["friction_budget_eur"] == 8.0


def test_validated_acquisition_ranks_ahead_of_generic_within_band():
    cfg = {
        "rules": {"min_product_age_days_for_flip_signal": 14},
        "cross_price_research": {"candidates_per_band": 1},
    }
    rows = [
        row(1, 20.0, 1.0),
        row(2, 20.0, 10.0, validated=15.0),
    ]
    selected = build_cross_price_research(rows, cfg)
    assert len(selected) == 1
    assert selected[0]["id_product"] == 2
    assert selected[0]["acquisition_basis"] == "VALIDATED_EN_NM"


def test_acquisition_source_tracks_cardtrader_vs_cardmarket_generic():
    cfg = {
        "rules": {"min_product_age_days_for_flip_signal": 14},
        "cross_price_research": {"candidates_per_band": 2},
    }
    validated = row(10, 40.0, 20.0, validated=25.0)
    validated["ct_en_nm_floor"] = 25.0
    generic = row(11, 40.0, 20.0)
    selected = build_cross_price_research([validated, generic], cfg)
    by_id = {r["id_product"]: r for r in selected}
    assert by_id[10]["screening_acquisition_source"] == "CARDTRADER_EN_NM"
    assert by_id[11]["screening_acquisition_source"] == "CARDMARKET_GENERIC_LOW"
