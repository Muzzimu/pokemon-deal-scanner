from scripts.refresh_owned_market import ask_diagnostics


def test_ask_diagnostics_structure():
    rows = [
        {"price_eur": 10.00, "seller_id": 1, "quantity": 2},
        {"price_eur": 10.20, "seller_id": 2, "quantity": 1},
        {"price_eur": 10.90, "seller_id": 1, "quantity": 2},
        {"price_eur": 12.00, "seller_id": 3, "quantity": 5},
    ]
    out = ask_diagnostics(rows, 3)
    assert out["floor_eur"] if "floor_eur" in out else out["floor"] == 10.0
    assert out["floor_depth_3pct_units"] == 3
    assert out["floor_depth_3pct_sellers"] == 2
    assert out["near_floor_10pct_units"] == 5
    assert out["near_floor_10pct_sellers"] == 2
    assert out["next_distinct_ask_gap_pct"] == 2.0
    assert out["top1_seller_unit_share_pct"] == 50.0
