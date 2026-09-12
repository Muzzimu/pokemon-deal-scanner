from __future__ import annotations

from deal_scanner.db import connect
from deal_scanner.scrapebadger_research import (
    classify_ebay_price_confidence,
    ensure_scrapebadger_schema,
    normalize_ebay_completed,
    normalize_vinted_item,
    persist_ebay_completed,
    persist_vinted,
    vinted_listing_state,
)


def test_ebay_completed_best_offer_keeps_price_uncertain():
    assert classify_ebay_price_confidence({"buying_format": "Auction", "is_auction": True}) == "HIGH_AUCTION_FINAL"
    assert classify_ebay_price_confidence({"buying_format": "Buy It Now", "is_auction": False}) == "HIGH_FIXED_PRICE_NO_BEST_OFFER_EVIDENCE"
    assert classify_ebay_price_confidence({"buying_format": "Best Offer", "is_auction": False}) == "PRICE_UNCERTAIN_BEST_OFFER"


def test_completed_row_preserves_identity_and_lineage():
    watch = {
        "id_product": "691922",
        "query_id": "ebay_691922",
        "required_tokens": "zeraora|gg42|crown zenith",
        "excluded_tokens": "japanese|graded|psa",
        "language": "en",
    }
    item = {
        "item_id": "123",
        "title": "Zeraora VMAX GG42/GG70 Crown Zenith English NM",
        "url": "https://example.test/123",
        "price": {"value": 31.5, "currency": "EUR"},
        "shipping_cost": {"value": 2.0, "currency": "EUR"},
        "sold_date": "12 Sep 2026",
        "sold_date_at": "2026-09-12",
        "buying_format": "Best Offer",
        "is_auction": False,
    }
    row = normalize_ebay_completed(
        item,
        snapshot_date="2026-09-12",
        observed_at="2026-09-12T09:00:00+00:00",
        domain="ie",
        watch=watch,
    )
    assert row is not None
    assert row["identity_status"] == "EXACT_TITLE_MATCH"
    assert row["price_confidence"] == "PRICE_UNCERTAIN_BEST_OFFER"
    assert row["source_lineage_key"] == "EBAY:ie:123"


def test_vinted_state_never_converts_closed_or_unknown_to_confirmed_sale():
    assert vinted_listing_state({"can_buy": True}, detail_checked=True) == "ACTIVE_VERIFIED"
    assert vinted_listing_state({"is_reserved": True}, detail_checked=True) == "RESERVED"
    assert vinted_listing_state({"is_closed": True}, detail_checked=True) == "CLOSED_UNPRICED"
    assert vinted_listing_state({}, detail_checked=True) == "DETAIL_STATE_UNKNOWN"
    assert vinted_listing_state({}, detail_checked=False) == "SEARCH_VISIBLE_UNVERIFIED"


def test_vinted_condition_is_preserved_not_mapped_to_nm():
    watch = {
        "query_id": "zeraora_gg42",
        "id_product": "691922",
        "query_kind": "exact",
        "required_tokens": "zeraora|gg42",
        "excluded_tokens": "japanese|graded|psa",
        "language": "en",
    }
    item = {
        "id": 999,
        "title": "Carte Pokemon Zeraora VMAX GG42/GG70 English",
        "description": "English Crown Zenith card",
        "price": {"amount": "27.0", "currency_code": "EUR"},
        "service_fee": "2.05",
        "total_item_price": "29.05",
        "status": "Very good",
        "can_buy": True,
        "is_reserved": False,
        "is_closed": False,
        "is_hidden": False,
        "seller": {"id": 42},
    }
    row = normalize_vinted_item(
        item,
        snapshot_date="2026-09-12",
        observed_at="2026-09-12T09:00:00+00:00",
        market="ie",
        watch=watch,
        detail_checked=True,
    )
    assert row is not None
    assert row["vinted_condition"] == "Very good"
    assert row["identity_status"] == "EXACT_TEXT_MATCH_LANGUAGE_EXPLICIT"
    assert row["listing_state"] == "ACTIVE_VERIFIED"
    assert row["ask_price"] == 27.0
    assert row["total_item_price"] == 29.05


def test_research_rows_persist_without_becoming_production_evidence(tmp_path):
    conn = connect(tmp_path / "research.sqlite")
    ensure_scrapebadger_schema(conn)

    ebay_row = {
        "snapshot_date": "2026-09-12", "observed_at": "2026-09-12T09:00:00+00:00",
        "provider": "SCRAPEBADGER", "domain": "ie", "id_product": 691922,
        "query_id": "ebay_691922", "item_id": "123", "title": "Zeraora VMAX GG42 Crown Zenith",
        "url": None, "reported_price": 30.0, "currency": "EUR", "shipping_cost": None,
        "sold_date": "12 Sep 2026", "sold_date_at": "2026-09-12", "buying_format": "Auction",
        "is_auction": 1, "bids": 4, "condition": "Used", "location": "Ireland", "seller_name": "seller",
        "identity_status": "EXACT_TITLE_MATCH", "sold_state_confidence": "PROVIDER_COMPLETED_STATE",
        "price_confidence": "HIGH_AUCTION_FINAL", "source_lineage_key": "EBAY:ie:123", "raw_json": "{}",
    }
    assert persist_ebay_completed(conn, [ebay_row]) == 1

    vinted_row = {
        "snapshot_date": "2026-09-12", "observed_at": "2026-09-12T09:00:00+00:00",
        "provider": "SCRAPEBADGER", "market": "ie", "query_id": "zeraora_gg42", "id_product": 691922,
        "query_kind": "exact", "item_id": "999", "title": "Zeraora VMAX GG42", "url": None,
        "ask_price": 27.0, "currency": "EUR", "service_fee": 2.05, "total_item_price": 29.05,
        "vinted_condition": "Very good", "catalog_id": 4875, "brand_id": None, "seller_id": "42",
        "seller_country_code": "FR", "favourite_count": 3, "view_count": 20, "can_buy": 1,
        "is_reserved": 0, "is_closed": 0, "is_hidden": 0, "listing_state": "ACTIVE_VERIFIED",
        "identity_status": "LIKELY_MATCH_LANGUAGE_UNVERIFIED", "detail_checked": 1, "raw_json": "{}",
    }
    assert persist_vinted(conn, [vinted_row]) == 1

    assert conn.execute("SELECT COUNT(*) FROM scrapebadger_ebay_completed_snapshots").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM scrapebadger_vinted_listing_snapshots").fetchone()[0] == 1
