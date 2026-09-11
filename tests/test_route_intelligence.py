from __future__ import annotations

import csv
from pathlib import Path

from deal_scanner.route_intelligence import apply_route_intelligence


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _read(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _cfg() -> dict:
    return {
        "cardtrader_resale": {
            "minimum_net_spread_eur": 2.0,
            "minimum_net_roi_pct": 25.0,
            "manual_verify_above_eur": 100.0,
            "price_bands": [
                {"label": "MICRO_0_10", "max_acquisition_eur": 10, "min_net_spread_eur": 2.5, "min_net_roi_pct": 35.0},
                {"label": "LOW_10_30", "max_acquisition_eur": 30, "min_net_spread_eur": 5.0, "min_net_roi_pct": 30.0},
                {"label": "MID_30_50", "max_acquisition_eur": 50, "min_net_spread_eur": 8.0, "min_net_roi_pct": 25.0},
                {"label": "HIGH_50_100", "max_acquisition_eur": 100, "min_net_spread_eur": 15.0, "min_net_roi_pct": 25.0},
                {"label": "PREMIUM_100_PLUS", "max_acquisition_eur": None, "min_net_spread_eur": 25.0, "min_net_roi_pct": 20.0},
            ],
        },
        "core_watch": {
            "min_reference_value_eur": 15.0,
            "max_reference_value_eur": 120.0,
            "minimum_ct_sellers": 2,
            "minimum_ct_units": 2,
            "require_ebay_or_three_ct_sellers": True,
            "max_rows": 100,
        },
    }


def _files(tmp_path: Path, *, acquisition: float, ct_net: float, ct_gross: float,
           spread: float, roi: float, sellers: int = 4, units: int = 10,
           cm_trend: float = 60.0, ebay_expected: float = 80.0):
    ct = tmp_path / "ct.csv"
    routes = tmp_path / "routes.csv"
    ebay = tmp_path / "ebay.csv"
    core = tmp_path / "core.csv"

    _write(ct, [
        "snapshot_date", "id_product", "name", "expansion_name", "number",
        "acquisition_eur", "best_ct_channel", "best_ct_gross_eur", "best_ct_net_eur",
        "ct_direct_sellers", "ct_direct_units", "ct_zero_sellers", "ct_zero_units",
        "net_spread_eur", "net_roi_pct", "ct_signal", "notes",
    ], [{
        "snapshot_date": "2026-09-11", "id_product": 123, "name": "Pikachu Test",
        "expansion_name": "Test", "number": "001", "acquisition_eur": acquisition,
        "best_ct_channel": "CARDTRADER_ZERO", "best_ct_gross_eur": ct_gross,
        "best_ct_net_eur": ct_net, "ct_direct_sellers": sellers,
        "ct_direct_units": units, "ct_zero_sellers": sellers, "ct_zero_units": units,
        "net_spread_eur": spread, "net_roi_pct": roi, "ct_signal": "RESELL_TEST", "notes": "base",
    }])

    _write(routes, [
        "snapshot_date", "id_product", "name", "expansion_name", "number",
        "best_validated_buy_eur", "cardmarket_trend_eur", "ebay_expected_eur",
        "best_sell_channel", "best_sell_gross_eur", "best_sell_net_eur",
        "net_spread_eur", "net_roi_pct", "route_signal", "notes",
    ], [{
        "snapshot_date": "2026-09-11", "id_product": 123, "name": "Pikachu Test",
        "expansion_name": "Test", "number": "001", "best_validated_buy_eur": acquisition,
        "cardmarket_trend_eur": cm_trend, "ebay_expected_eur": ebay_expected,
        "best_sell_channel": "CARDTRADER_ZERO", "best_sell_gross_eur": ct_gross,
        "best_sell_net_eur": ct_net, "net_spread_eur": spread, "net_roi_pct": roi,
        "route_signal": "RESELL_TEST", "notes": "base",
    }])

    _write(ebay, ["id_product", "expected_resale_eur", "reference_strength", "reference_type"], [{
        "id_product": 123, "expected_resale_eur": ebay_expected,
        "reference_strength": "STRONG", "reference_type": "CONFIRMED_SOLD",
    }])
    return ct, routes, ebay, core


def test_high_value_band_rejects_small_absolute_profit(tmp_path):
    ct, routes, ebay, core = _files(
        tmp_path, acquisition=70.0, ct_net=82.0, ct_gross=90.0, spread=12.0, roi=17.1,
    )
    apply_route_intelligence(_cfg(), ct, routes, ebay, core)
    ct_row = _read(ct)[0]
    route = _read(routes)[0]

    assert ct_row["price_band"] == "HIGH_50_100"
    assert float(ct_row["required_min_spread_eur"]) == 15.0
    assert ct_row["ct_signal"] == "NO_EDGE"
    assert route["route_signal"] == "NO_EDGE"


def test_confirmed_ct_gap_gets_high_lag_score_and_core_watch(tmp_path):
    ct, routes, ebay, core = _files(
        tmp_path, acquisition=55.0, ct_net=80.0, ct_gross=85.0, spread=25.0, roi=45.5,
        sellers=4, units=10, cm_trend=60.0, ebay_expected=80.0,
    )
    status = apply_route_intelligence(_cfg(), ct, routes, ebay, core)
    route = _read(routes)[0]
    watch = _read(core)

    assert route["route_signal"] == "RESELL_TEST"
    assert route["ct_lag_label"] == "HIGH"
    assert int(route["ct_lag_score"]) >= 70
    assert status["core_watch_rows"] == 1
    assert watch[0]["watch_priority"] == "A"


def test_over_100_requires_manual_verification_even_with_edge(tmp_path):
    ct, routes, ebay, core = _files(
        tmp_path, acquisition=120.0, ct_net=155.0, ct_gross=170.0, spread=35.0, roi=29.2,
        cm_trend=120.0, ebay_expected=160.0,
    )
    apply_route_intelligence(_cfg(), ct, routes, ebay, core)
    route = _read(routes)[0]

    assert route["price_band"] == "PREMIUM_100_PLUS"
    assert route["manual_verification_required"] == "1"
    assert route["route_signal"] == "WATCH_ONLY"
