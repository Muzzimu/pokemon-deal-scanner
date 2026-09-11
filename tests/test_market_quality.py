from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from deal_scanner.market_quality import apply_market_quality


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
        "fx": {"fallback_usd_to_eur": 0.86, "fallback_gbp_to_eur": 1.16},
        "market_quality": {
            "min_liquidity_score": 55,
            "min_price_confidence_score": 65,
            "min_exit_confidence_score": 60,
            "min_bridge_opportunity_score": 60,
            "high_value_from_eur": 50,
            "high_value_min_liquidity_score": 60,
            "high_value_min_price_confidence_score": 70,
            "high_value_min_exit_confidence_score": 65,
            "high_value_min_bridge_opportunity_score": 65,
        },
    }


def _base_files(
    tmp_path: Path,
    *,
    cm_trend: float = 120.0,
    cm_live: float = 121.0,
    acquisition: float = 90.0,
    ct_gross: float = 125.0,
    ct_sellers: int = 5,
    ct_units: int = 12,
    eu_ebay: float = 119.0,
    eu_ebay_sales: int = 6,
    us_ebay: float = 122.0,
    us_ebay_sales: int = 6,
    tcg_market: float = 121.0,
    tcg_recent: float = 120.0,
    tcg_sales_90d: int = 90,
    tcg_qty: int = 8,
    tcg_sellers: int = 4,
):
    routes = tmp_path / "routes.csv"
    ct = tmp_path / "ct.csv"
    ebay = tmp_path / "ebay.csv"
    tcg = tmp_path / "tcg.csv"
    mapping = tmp_path / "mapping.csv"
    core = tmp_path / "core.csv"
    out = tmp_path / "quality.csv"

    _write(routes, [
        "snapshot_date", "id_product", "name", "expansion_name", "number",
        "best_validated_buy_eur", "cardmarket_trend_eur", "ebay_expected_eur",
        "best_sell_channel", "best_sell_gross_eur", "best_sell_net_eur",
        "net_spread_eur", "net_roi_pct", "required_net_spread_eur",
        "required_net_roi_pct", "route_signal", "notes",
        "cm_live_robust_floor_eur", "cm_live_sellers", "cm_live_units",
    ], [{
        "snapshot_date": "2026-09-11", "id_product": 123, "name": "Palkia Test",
        "expansion_name": "Test", "number": "001", "best_validated_buy_eur": acquisition,
        "cardmarket_trend_eur": cm_trend, "ebay_expected_eur": eu_ebay,
        "best_sell_channel": "CARDTRADER_ZERO", "best_sell_gross_eur": ct_gross,
        "best_sell_net_eur": ct_gross * 0.91, "net_spread_eur": ct_gross * 0.91 - acquisition,
        "net_roi_pct": (ct_gross * 0.91 - acquisition) / acquisition * 100,
        "required_net_spread_eur": 15, "required_net_roi_pct": 25,
        "route_signal": "RESELL_TEST", "notes": "base",
        "cm_live_robust_floor_eur": cm_live, "cm_live_sellers": 5, "cm_live_units": 10,
    }])

    _write(ct, [
        "id_product", "best_ct_channel", "best_ct_gross_eur", "ct_zero_sellers", "ct_zero_units",
        "ct_direct_sellers", "ct_direct_units",
    ], [{
        "id_product": 123, "best_ct_channel": "CARDTRADER_ZERO", "best_ct_gross_eur": ct_gross,
        "ct_zero_sellers": ct_sellers, "ct_zero_units": ct_units,
        "ct_direct_sellers": 0, "ct_direct_units": 0,
    }])

    _write(ebay, [
        "snapshot_date", "id_product", "region", "currency", "chosen_reference",
        "smoothed_reference", "strength", "confirmed_sales", "inferred_sales",
    ], [
        {
            "snapshot_date": "2026-09-11", "id_product": 123, "region": "EU", "currency": "EUR",
            "chosen_reference": eu_ebay, "smoothed_reference": eu_ebay,
            "strength": "STRONG", "confirmed_sales": eu_ebay_sales, "inferred_sales": 0,
        },
        {
            "snapshot_date": "2026-09-11", "id_product": 123, "region": "GLOBAL", "currency": "EUR",
            "chosen_reference": us_ebay, "smoothed_reference": us_ebay,
            "strength": "STRONG", "confirmed_sales": us_ebay_sales, "inferred_sales": 0,
        },
    ])

    _write(tcg, [
        "id_product", "market_price_eur", "most_recent_sale_eur", "current_quantity",
        "current_sellers", "sales_90d", "reference_strength", "checked_at", "listing_count",
    ], [{
        "id_product": 123, "market_price_eur": tcg_market, "most_recent_sale_eur": tcg_recent,
        "current_quantity": tcg_qty, "current_sellers": tcg_sellers, "sales_90d": tcg_sales_90d,
        "reference_strength": "STRONG", "checked_at": "2026-09-11", "listing_count": 999,
    }])

    _write(mapping, ["resolved_id_product", "mapping_status"], [{
        "resolved_id_product": 123, "mapping_status": "EXACT",
    }])
    _write(core, ["id_product", "watch_priority"], [{"id_product": 123, "watch_priority": "A"}])
    return routes, ct, ebay, tcg, mapping, core, out


def test_tcgplayer_does_not_drag_eu_fair_value(tmp_path):
    files = _base_files(
        tmp_path,
        cm_trend=120,
        cm_live=121,
        eu_ebay=118,
        us_ebay=98,
        tcg_market=95,
        tcg_recent=93,
        ct_gross=135,
    )
    apply_market_quality(_cfg(), *files, today=date(2026, 9, 11))
    row = _read(files[-1])[0]

    assert float(row["eu_fair_value_eur"]) >= 118
    assert float(row["us_fair_value_eur"]) <= 98
    assert float(row["fair_value_eur"]) == float(row["eu_fair_value_eur"])
    assert row["fair_value_scope"] == "EU_TRANSACTIONAL"


def test_supported_cardtrader_bridge_scores_high(tmp_path):
    files = _base_files(
        tmp_path,
        cm_trend=92,
        cm_live=92,
        acquisition=80,
        eu_ebay=91,
        ct_gross=125,
        us_ebay=122,
        tcg_market=123,
        tcg_recent=121,
        tcg_sales_90d=120,
        tcg_qty=10,
        tcg_sellers=5,
    )
    apply_market_quality(_cfg(), *files, today=date(2026, 9, 11))
    row = _read(files[-1])[0]

    assert int(row["bridge_opportunity_score"]) >= 65
    assert int(row["us_price_confidence_score"]) >= 70
    assert int(row["exit_confidence_score"]) >= 65


def test_unsupported_cardtrader_premium_is_downgraded(tmp_path):
    files = _base_files(
        tmp_path,
        cm_trend=92,
        cm_live=92,
        acquisition=80,
        eu_ebay=91,
        ct_gross=125,
        us_ebay=96,
        tcg_market=94,
        tcg_recent=93,
        tcg_sales_90d=90,
        tcg_qty=8,
        tcg_sellers=4,
    )
    status = apply_market_quality(_cfg(), *files, today=date(2026, 9, 11))
    row = _read(files[-1])[0]
    route = _read(files[0])[0]

    assert int(row["bridge_opportunity_score"]) < 65
    assert route["route_signal"] == "WATCH_ONLY"
    assert status["routes_downgraded_by_quality_gate"] == 1


def test_legacy_listing_count_does_not_inflate_us_depth(tmp_path):
    files = _base_files(
        tmp_path,
        tcg_market=100,
        tcg_recent=99,
        tcg_sales_90d=0,
        tcg_qty=1,
        tcg_sellers=1,
    )
    # listing_count=999 is deliberately absurd. Exact current_quantity/current_sellers must win.
    apply_market_quality(_cfg(), *files, today=date(2026, 9, 11))
    row = _read(files[-1])[0]

    assert row["tcgplayer_listing_count"] == "999"
    assert row["tcgplayer_current_quantity"] == "1"
    assert row["tcgplayer_current_sellers"] == "1"
    assert int(row["us_liquidity_score"]) < 85
