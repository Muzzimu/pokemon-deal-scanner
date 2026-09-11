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
        "fx": {"fallback_usd_to_eur": 0.86},
        "market_quality": {
            "min_liquidity_score": 65,
            "min_price_confidence_score": 75,
            "min_exit_confidence_score": 65,
            "high_value_from_eur": 50,
            "high_value_min_liquidity_score": 70,
            "high_value_min_price_confidence_score": 80,
            "high_value_min_exit_confidence_score": 70,
        },
    }


def _base_files(tmp_path: Path, *, ct_gross: float, ebay_price: float, tcg_price: float,
                acquisition: float = 54.0, ct_sellers: int = 6, ct_units: int = 14,
                ebay_sales: int = 6, tcg_sales: int = 12):
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
        "net_spread_eur", "net_roi_pct", "route_signal", "notes",
    ], [{
        "snapshot_date": "2026-09-11", "id_product": 123, "name": "Pikachu Test",
        "expansion_name": "Test", "number": "001", "best_validated_buy_eur": acquisition,
        "cardmarket_trend_eur": 58.0, "ebay_expected_eur": ebay_price,
        "best_sell_channel": "CARDTRADER_ZERO", "best_sell_gross_eur": ct_gross,
        "best_sell_net_eur": ct_gross * 0.91, "net_spread_eur": ct_gross * 0.91 - acquisition,
        "net_roi_pct": 35, "route_signal": "RESELL_TEST", "notes": "base",
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
        "snapshot_date", "id_product", "strength", "confirmed_sales", "inferred_sales",
    ], [{
        "snapshot_date": "2026-09-11", "id_product": 123, "strength": "STRONG",
        "confirmed_sales": ebay_sales, "inferred_sales": 0,
    }])

    _write(tcg, [
        "id_product", "market_price_eur", "low_price_eur", "listing_count", "sales_30d",
        "reference_strength", "checked_at",
    ], [{
        "id_product": 123, "market_price_eur": tcg_price, "low_price_eur": tcg_price - 2,
        "listing_count": 25, "sales_30d": tcg_sales, "reference_strength": "STRONG",
        "checked_at": "2026-09-11",
    }])

    _write(mapping, ["resolved_id_product", "mapping_status"], [{
        "resolved_id_product": 123, "mapping_status": "EXACT",
    }])

    _write(core, ["id_product", "watch_priority"], [{"id_product": 123, "watch_priority": "A"}])
    return routes, ct, ebay, tcg, mapping, core, out


def test_convergent_markets_get_high_quality_scores(tmp_path):
    files = _base_files(tmp_path, ct_gross=79, ebay_price=78, tcg_price=77)
    status = apply_market_quality(_cfg(), *files, today=date(2026, 9, 11))
    row = _read(files[-1])[0]
    route = _read(files[0])[0]

    assert int(row["liquidity_score"]) >= 70
    assert int(row["price_confidence_score"]) >= 80
    assert int(row["exit_confidence_score"]) >= 70
    assert row["quality_gate_pass"] == "1"
    assert route["route_signal"] == "RESELL_TEST"
    assert status["routes_with_tcgplayer_evidence"] == 1


def test_cardtrader_outlier_is_downgraded_even_when_fair_value_is_confident(tmp_path):
    files = _base_files(tmp_path, ct_gross=95, ebay_price=60, tcg_price=59, ct_sellers=2, ct_units=2)
    status = apply_market_quality(_cfg(), *files, today=date(2026, 9, 11))
    row = _read(files[-1])[0]
    route = _read(files[0])[0]

    assert int(row["price_confidence_score"]) >= 70
    assert int(row["exit_confidence_score"]) < 70
    assert row["quality_gate_pass"] == "0"
    assert route["route_signal"] == "WATCH_ONLY"
    assert status["routes_downgraded_by_quality_gate"] == 1


def test_missing_tcgplayer_does_not_break_scoring(tmp_path):
    files = _base_files(tmp_path, ct_gross=79, ebay_price=78, tcg_price=77)
    # Replace TCG reference with an empty, valid file.
    _write(files[3], ["id_product", "market_price_eur", "reference_strength", "checked_at"], [])
    status = apply_market_quality(_cfg(), *files, today=date(2026, 9, 11))
    row = _read(files[-1])[0]

    assert status["tcgplayer_rows_loaded"] == 0
    assert row["tcgplayer_strength"] == "NONE"
    assert int(row["liquidity_score"]) >= 0
    assert int(row["price_confidence_score"]) >= 0
