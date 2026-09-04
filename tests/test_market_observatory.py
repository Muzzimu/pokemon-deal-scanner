from __future__ import annotations

from datetime import date

from deal_scanner.db import connect
from deal_scanner.market_observatory import (
    choose_reference,
    ensure_ebay_schema,
    reconcile_listing_state,
    title_matches,
)


def test_exact_raw_card_title_matcher_rejects_slabs_and_wrong_language():
    watch = {
        "required_tokens": "dragonite|076|pokemon go",
        "excluded_tokens": "",
        "language": "en",
    }
    assert title_matches("Pokemon GO Dragonite V 076/078 Ultra Rare English NM", watch)
    assert not title_matches("PSA 10 Pokemon GO Dragonite V 076/078", watch)
    assert not title_matches("Pokemon GO Dragonite V 076/078 Japanese", watch)
    assert not title_matches("Pokemon GO Dragonite V 049/078 English", watch)


def test_reference_precedence_keeps_asks_labelled_as_weak():
    strong = choose_reference([18, 19, 20, 21, 22], [15, 16, 17], [14, 15, 16])
    assert strong["reference_type"] == "CONFIRMED_SALES"
    assert strong["strength"] == "STRONG"
    assert strong["chosen_reference"] == 16

    inferred = choose_reference([18, 19, 20], [], [14, 15, 16])
    assert inferred["reference_type"] == "INFERRED_QUICK_SALES"
    assert inferred["strength"] == "MEDIUM"

    asks = choose_reference([18, 19, 20, 21, 22], [], [])
    assert asks["reference_type"] == "ACTIVE_ASKS"
    assert asks["strength"] == "WEAK"


def test_disappearance_requires_two_successful_missing_scans(tmp_path):
    conn = connect(tmp_path / "obs.sqlite")
    ensure_ebay_schema(conn)
    listing = {
        "item_id": "v1|123|0",
        "title": "Pokemon GO Dragonite V 076/078 English",
        "price_value": 18.0,
        "currency": "EUR",
        "item_location_country": "IE",
        "seller_username": "seller",
        "seller_account_type": "INDIVIDUAL",
        "condition_id": "3000",
        "buying_options": ["FIXED_PRICE"],
    }
    reconcile_listing_state(
        conn, id_product=665687, marketplace="EBAY_IE", region="IRELAND",
        listings=[listing], seen_date="2026-09-01", confirm_missing_days=1,
        quick_sale_max_days=3,
    )
    first_miss = reconcile_listing_state(
        conn, id_product=665687, marketplace="EBAY_IE", region="IRELAND",
        listings=[], seen_date="2026-09-02", confirm_missing_days=1,
        quick_sale_max_days=3,
    )
    assert first_miss["confirmed_gone"] == 0
    row = conn.execute("SELECT gone_at,missing_since_at FROM ebay_listing_state").fetchone()
    assert row["gone_at"] is None
    assert row["missing_since_at"] == "2026-09-02"

    second_miss = reconcile_listing_state(
        conn, id_product=665687, marketplace="EBAY_IE", region="IRELAND",
        listings=[], seen_date="2026-09-03", confirm_missing_days=1,
        quick_sale_max_days=3,
    )
    assert second_miss["confirmed_gone"] == 1
    assert second_miss["inferred_quick_sales"] == 1
    row = conn.execute("SELECT gone_at,inferred_quick_sale FROM ebay_listing_state").fetchone()
    assert row["gone_at"] == "2026-09-02"
    assert row["inferred_quick_sale"] == 1
