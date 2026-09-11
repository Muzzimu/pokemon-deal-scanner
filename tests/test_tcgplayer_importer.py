from __future__ import annotations

import importlib.util
import json
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
