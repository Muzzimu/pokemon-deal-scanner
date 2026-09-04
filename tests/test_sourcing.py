from __future__ import annotations

from pathlib import Path

from deal_scanner.config import load_config
from deal_scanner.db import connect
from deal_scanner.sourcing import analyze_sourcing_offers, seller_confidence


ROOT = Path(__file__).resolve().parents[1]


def _conn(tmp_path):
    conn = connect(tmp_path / "test.sqlite")
    conn.execute(
        "INSERT INTO products(id_product,name,category_name,expansion_name,number,last_seen_catalog) VALUES(?,?,?,?,?,?)",
        (665687, "Dragonite V [Hyper Beam | Buster Tail]", "Pokémon Single", "Pokémon GO", "076", "2026-09-04"),
    )
    conn.commit()
    return conn


def test_rating_quality_beats_sales_volume():
    quutamo = seller_confidence("Outstanding", 180)
    andys = seller_confidence("Very Good", 23000)
    new_seller = seller_confidence("Unrated", 3)
    assert quutamo > andys > new_seller
    assert quutamo >= 90
    assert andys >= 85


def test_strict_ireland_nm_filter_and_dragonite_decision(tmp_path):
    cfg = load_config(ROOT / "config.yaml")
    conn = _conn(tmp_path)
    rows = [
        {
            "id_product": "665687", "article_price_eur": "9.00",
            "shipping_total_eur": "1.55", "shipping_allocation_eur": "0.775",
            "seller": "Andys-Pokeshop", "seller_rating": "Very Good", "seller_sales": "23000",
            "ships_to_ireland": "yes", "language": "en", "condition": "NM",
        },
        {
            "id_product": "665687", "article_price_eur": "7.95",
            "shipping_total_eur": "3.65", "shipping_allocation_eur": "1.825",
            "seller": "Quutamo", "seller_rating": "Outstanding", "seller_sales": "180",
            "ships_to_ireland": "yes", "language": "en", "condition": "EX",
        },
        {
            "id_product": "665687", "article_price_eur": "8.00",
            "seller": "NoIreland", "seller_rating": "Outstanding", "seller_sales": "1000",
            "ships_to_ireland": "no", "language": "en", "condition": "NM",
        },
    ]
    result = analyze_sourcing_offers(conn, cfg, rows)
    by_seller = {r["seller"]: r for r in result}
    assert by_seller["Andys-Pokeshop"]["allocated_landed_cost_eur"] == 9.78
    assert by_seller["Andys-Pokeshop"]["decision"] == "BUNDLE_BUY"
    assert by_seller["Quutamo"]["decision"] == "INELIGIBLE"
    assert "NOT_NM" in by_seller["Quutamo"]["eligibility_reason"]
    assert by_seller["NoIreland"]["decision"] == "INELIGIBLE"
    assert "NO_IRELAND_SHIPPING" in by_seller["NoIreland"]["eligibility_reason"]


def test_unknown_shipping_requires_landed_verification(tmp_path):
    cfg = load_config(ROOT / "config.yaml")
    conn = _conn(tmp_path)
    result = analyze_sourcing_offers(conn, cfg, [{
        "id_product": "665687", "article_price_eur": "7.60",
        "seller": "Tjanpf", "seller_rating": "Unrated", "seller_sales": "3",
        "ships_to_ireland": "yes", "language": "en", "condition": "NM",
    }])
    assert result[0]["decision"] == "VERIFY_LANDED"
    assert result[0]["allocated_landed_cost_eur"] is None
