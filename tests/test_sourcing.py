from __future__ import annotations

from pathlib import Path

from deal_scanner.config import load_config
from deal_scanner.db import connect
from deal_scanner.sourcing import analyze_sourcing_offers, generate_cardmarket_sourcing_report, seller_confidence


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


def test_robust_floor_uses_median_of_cheapest_three_and_ignores_tiny_seller(tmp_path):
    cfg = load_config(ROOT / "config.yaml")
    conn = _conn(tmp_path)
    rows = [
        {"id_product": "665687", "article_price_eur": "7.60", "seller": "Tiny", "seller_sales": "3", "ships_to_ireland": "yes", "language": "en", "condition": "NM"},
        {"id_product": "665687", "article_price_eur": "8.50", "seller": "A", "seller_sales": "36", "ships_to_ireland": "yes", "language": "en", "condition": "NM"},
        {"id_product": "665687", "article_price_eur": "8.90", "seller": "B", "seller_sales": "11", "ships_to_ireland": "yes", "language": "en", "condition": "NM"},
        {"id_product": "665687", "article_price_eur": "9.00", "seller": "C", "seller_sales": "264", "ships_to_ireland": "yes", "language": "en", "condition": "NM"},
        {"id_product": "665687", "article_price_eur": "9.50", "seller": "D", "seller_sales": "500", "ships_to_ireland": "yes", "language": "en", "condition": "NM"},
    ]
    result = analyze_sourcing_offers(conn, cfg, rows)
    assert all(r["robust_en_nm_floor_eur"] == 8.90 for r in result)
    assert all(r["robust_floor_sample_size"] == 3 for r in result)
    # The €7.60 offer remains visible/actionable, but does not define planning value.
    tiny = next(r for r in result if r["seller"] == "Tiny")
    assert tiny["decision"] == "VERIFY_LANDED"


def test_robust_floor_persists_as_cardmarket_en_nm_benchmark(tmp_path):
    cfg = load_config(ROOT / "config.yaml")
    conn = _conn(tmp_path)
    reference = tmp_path / "offers.csv"
    reference.write_text(
        "id_product,article_price_eur,shipping_total_eur,shipping_allocation_eur,seller,seller_rating,seller_sales,ships_to_ireland,language,condition,checked_at,source,notes\n"
        "665687,8.50,,,A,,36,yes,en,NM,2026-09-05,test,\n"
        "665687,8.90,,,B,,11,yes,en,NM,2026-09-05,test,\n"
        "665687,9.00,,,C,,264,yes,en,NM,2026-09-05,test,\n",
        encoding="utf-8",
    )
    output = tmp_path / "sourcing.csv"
    status = generate_cardmarket_sourcing_report(conn, cfg, reference, output)
    row = conn.execute("SELECT en_nm_floor_eur,source FROM cardmarket_en_nm_overrides WHERE id_product=665687").fetchone()
    assert status["robust_floor_products"] == 1
    assert row["en_nm_floor_eur"] == 8.90
    assert row["source"] == "Cardmarket robust median"
