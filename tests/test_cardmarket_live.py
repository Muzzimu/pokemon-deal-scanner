from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from deal_scanner.cardmarket_live import validate_cardmarket_live


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


class FakeClient:
    def __init__(self, prices):
        self.prices = prices

    def listings(self, product_id: int):
        return {
            "status": "success",
            "data": {
                "product_id": product_id,
                "listings": [
                    {"seller_name": f"s{i}", "price": price, "quantity": 1, "condition": "NM", "language": "English"}
                    for i, price in enumerate(self.prices, start=1)
                ],
            },
        }


def _cfg() -> dict:
    return {
        "cardmarket_live": {
            "enabled": True,
            "provider": "parsebot",
            "watch_priorities": ["A", "B"],
            "minimum_ct_lag_score": 40,
            "max_candidates_per_run": 20,
            "robust_floor_sample_size": 3,
            "minimum_live_sellers": 2,
            "stale_upward_pct": 10.0,
            "cheaper_candidate_pct": 10.0,
        }
    }


def _seed_files(tmp_path: Path, validated_buy: float = 50.0):
    core = tmp_path / "core.csv"
    live = tmp_path / "live.csv"
    routes = tmp_path / "routes.csv"
    ct = tmp_path / "ct.csv"
    _write(core, [
        "id_product", "name", "expansion_name", "number", "watch_priority", "ct_lag_score",
        "net_spread_eur", "validated_buy_eur",
    ], [{
        "id_product": 123, "name": "Pikachu Test", "expansion_name": "Test Set", "number": "001",
        "watch_priority": "A", "ct_lag_score": 80, "net_spread_eur": 25.0,
        "validated_buy_eur": validated_buy,
    }])
    _write(routes, ["id_product", "route_signal", "notes"], [{
        "id_product": 123, "route_signal": "RESELL_TEST", "notes": "base"
    }])
    _write(ct, ["id_product", "ct_signal", "notes"], [{
        "id_product": 123, "ct_signal": "RESELL_TEST", "notes": "base"
    }])
    return core, live, routes, ct


def test_live_validation_uses_robust_cheapest_offer_median(tmp_path):
    core, live, routes, ct = _seed_files(tmp_path, validated_buy=50.0)
    status = validate_cardmarket_live(
        _cfg(), core, live, routes, ct,
        client=FakeClient([45.0, 46.0, 47.0, 60.0]),
        today=date(2026, 9, 11),
    )
    row = _read(live)[0]
    assert status["queried"] == 1
    assert float(row["live_article_floor_eur"]) == 45.0
    assert float(row["live_robust_floor_eur"]) == 46.0
    assert row["validation_signal"] == "LIVE_ALIGNED"


def test_stale_manual_source_downgrades_actionable_routes(tmp_path):
    core, live, routes, ct = _seed_files(tmp_path, validated_buy=50.0)
    status = validate_cardmarket_live(
        _cfg(), core, live, routes, ct,
        client=FakeClient([60.0, 61.0, 62.0]),
        today=date(2026, 9, 11),
    )
    live_row = _read(live)[0]
    route_row = _read(routes)[0]
    ct_row = _read(ct)[0]
    assert live_row["validation_signal"] == "REVALIDATE_STALE_SOURCE"
    assert route_row["route_signal"] == "REVALIDATE_SOURCE"
    assert ct_row["ct_signal"] == "WATCH_ONLY"
    assert status["routes_downgraded"] == 1
    assert status["ct_candidates_downgraded"] == 1


def test_live_cheaper_offer_never_auto_upgrades_buy_signal(tmp_path):
    core, live, routes, ct = _seed_files(tmp_path, validated_buy=50.0)
    validate_cardmarket_live(
        _cfg(), core, live, routes, ct,
        client=FakeClient([35.0, 36.0, 37.0]),
        today=date(2026, 9, 11),
    )
    live_row = _read(live)[0]
    route_row = _read(routes)[0]
    assert live_row["validation_signal"] == "LIVE_CHEAPER_VERIFY_SHIPPING"
    assert route_row["route_signal"] == "RESELL_TEST"
