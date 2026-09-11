from __future__ import annotations

import csv
from pathlib import Path

from deal_scanner.cardtrader_resale import generate_cardtrader_resale_reports
from deal_scanner.db import connect, insert_cardtrader_offers, insert_price_snapshot, upsert_products


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _cfg(min_sellers: int = 2) -> dict:
    return {
        "cardtrader_resale": {
            "enabled": True,
            "direct_fee_pct": 5.3,
            "zero_fee_pct": 7.3,
            "fee_vat_pct": 23.0,
            "minimum_fee_eur": 0.01,
            "undercut_eur": 0.01,
            "direct_operational_reserve_eur": 0.0,
            "zero_operational_reserve_eur": 0.0,
            "minimum_competing_sellers": min_sellers,
            "minimum_net_spread_eur": 2.0,
            "minimum_net_roi_pct": 25.0,
            "ebay_exit_cost_pct": 8.0,
            "excluded_seller_usernames": [],
        },
        "resale": {"minimum_gross_spread_eur": 2.0, "minimum_gross_roi_pct": 25.0},
        "arbitrage": {"exit_cost_pct": 8.0},
    }


def _seed(conn, *, sellers: int = 2) -> None:
    upsert_products(conn, [{
        "idProduct": 123,
        "name": "Pikachu Test",
        "categoryName": "Pokemon",
        "expansionName": "Test Set",
        "number": "001",
    }], "2026-09-11")
    insert_price_snapshot(conn, [{
        "idProduct": 123,
        "low": 9.0,
        "trend": 15.0,
        "avg1": 15.0,
        "avg7": 15.0,
        "avg30": 15.0,
    }], "2026-09-11", None)
    offers = [{
        "offer_id": 1,
        "blueprint_id": 1001,
        "id_product": 123,
        "seller_id": 10,
        "seller_username": "seller1",
        "seller_country": "IT",
        "quantity": 1,
        "price_eur": 20.0,
        "language": "en",
        "condition": "Near Mint",
        "graded": False,
        "on_vacation": False,
        "ct_zero": True,
    }]
    if sellers >= 2:
        offers.append({
            "offer_id": 2,
            "blueprint_id": 1001,
            "id_product": 123,
            "seller_id": 11,
            "seller_username": "seller2",
            "seller_country": "DE",
            "quantity": 2,
            "price_eur": 21.0,
            "language": "en",
            "condition": "Near Mint",
            "graded": False,
            "on_vacation": False,
            "ct_zero": True,
        })
    insert_cardtrader_offers(conn, offers, "2026-09-11")


def _sourcing(path: Path) -> None:
    _write_csv(path, [
        "id_product", "name", "expansion_name", "number", "seller", "decision",
        "risk_adjusted_landed_eur",
    ], [{
        "id_product": 123,
        "name": "Pikachu Test",
        "expansion_name": "Test Set",
        "number": "001",
        "seller": "cm_seller",
        "decision": "VALIDATED_SOURCE",
        "risk_adjusted_landed_eur": 10.0,
    }])


def test_cardtrader_resale_edge_requires_competing_seller_depth(tmp_path):
    conn = connect(tmp_path / "scanner.sqlite")
    _seed(conn, sellers=2)
    sourcing = tmp_path / "sourcing.csv"
    ebay = tmp_path / "ebay.csv"
    ct_out = tmp_path / "ct.csv"
    routes = tmp_path / "routes.csv"
    _sourcing(sourcing)
    _write_csv(ebay, ["id_product", "expected_resale_eur", "reference_strength", "reference_type"], [])

    status = generate_cardtrader_resale_reports(conn, _cfg(2), sourcing, ebay, ct_out, routes)
    rows = _read_csv(ct_out)

    assert status["resell_test_rows"] == 1
    assert len(rows) == 1
    assert rows[0]["best_ct_channel"] == "CARDTRADER_DIRECT"
    assert rows[0]["ct_signal"] == "RESELL_TEST"
    assert float(rows[0]["ct_direct_target_eur"]) == 19.99
    assert float(rows[0]["ct_direct_net_eur"]) == 18.69


def test_single_cardtrader_seller_stays_watch_only(tmp_path):
    conn = connect(tmp_path / "scanner.sqlite")
    _seed(conn, sellers=1)
    sourcing = tmp_path / "sourcing.csv"
    ebay = tmp_path / "ebay.csv"
    ct_out = tmp_path / "ct.csv"
    routes = tmp_path / "routes.csv"
    _sourcing(sourcing)
    _write_csv(ebay, ["id_product", "expected_resale_eur", "reference_strength", "reference_type"], [])

    generate_cardtrader_resale_reports(conn, _cfg(2), sourcing, ebay, ct_out, routes)
    rows = _read_csv(ct_out)

    assert rows[0]["ct_signal"] == "WATCH_ONLY"
    assert rows[0]["confidence"] == "LOW"


def test_market_route_can_choose_stronger_ebay_exit(tmp_path):
    conn = connect(tmp_path / "scanner.sqlite")
    _seed(conn, sellers=2)
    sourcing = tmp_path / "sourcing.csv"
    ebay = tmp_path / "ebay.csv"
    ct_out = tmp_path / "ct.csv"
    routes = tmp_path / "routes.csv"
    _sourcing(sourcing)
    _write_csv(ebay, [
        "id_product", "expected_resale_eur", "reference_strength", "reference_type",
    ], [{
        "id_product": 123,
        "expected_resale_eur": 25.0,
        "reference_strength": "STRONG",
        "reference_type": "CONFIRMED_SOLD",
    }])

    generate_cardtrader_resale_reports(conn, _cfg(2), sourcing, ebay, ct_out, routes)
    route_rows = _read_csv(routes)

    assert len(route_rows) == 1
    assert route_rows[0]["best_sell_channel"] == "EBAY_IE_EU"
    assert float(route_rows[0]["best_sell_net_eur"]) == 23.0
    assert float(route_rows[0]["consensus_value_eur"]) == 20.0
    assert route_rows[0]["route_signal"] == "RESELL_TEST"
