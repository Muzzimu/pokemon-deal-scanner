from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tcg_importer", ROOT / "scripts" / "import_tcgplayer_reference.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_importer_extracts_exact_cardmarket_id_from_url():
    row = {
        "card": "Pikachu ex",
        "cardmarketUrl": "https://www.cardmarket.com/en/Pokemon/Products?idProduct=123456",
        "productId": 998877,
        "usMarketUsd": 80.0,
        "usMarketEur": 68.8,
    }
    out = MODULE._normalize(row, "test", "MEDIUM")
    assert out is not None
    assert out["id_product"] == "123456"
    assert out["tcgplayer_product_id"] == 998877
    assert out["market_price_usd"] == 80.0
    assert out["market_price_eur"] == 68.8


def test_importer_rejects_name_collector_only_mapping():
    row = {
        "name": "Charizard ex",
        "number": "199/165",
        "marketPrice": 95.0,
    }
    assert MODULE._normalize(row, "test", "MEDIUM") is None


def test_importer_keeps_transaction_velocity_and_live_supply_separate():
    row = {
        "id_product": 123456,
        "name": "Origin Forme Palkia VSTAR",
        "marketPrice": 112.98,
        "mostRecentSale": 103.51,
        "lowestListingPriceUsd": 119.99,
        "lowestListingShippingUsd": 19.99,
        "sales90d": 107,
        "avgDailySold": 1,
        "currentQuantity": 4,
        "currentSellers": 2,
        # A search/provider aggregate may expose a large listing_count. It is
        # retained for audit but market_quality no longer uses it as exact depth.
        "totalListings": 110,
    }
    out = MODULE._normalize(row, "test", "STRONG")
    assert out is not None
    assert out["market_price_usd"] == 112.98
    assert out["most_recent_sale_usd"] == 103.51
    assert out["lowest_listing_price_usd"] == 119.99
    assert out["lowest_listing_shipping_usd"] == 19.99
    assert out["executable_floor_usd"] == 139.98
    assert out["sales_90d"] == 107
    assert out["current_quantity"] == 4
    assert out["current_sellers"] == 2
    assert out["listing_count"] == 110
