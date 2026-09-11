from __future__ import annotations

import csv
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from deal_scanner.model_validation import (
    ensure_model_validation_schema,
    freeze_predictions,
    mature_outcomes,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_model_validation_schema(conn)
    return conn


def _route(path: Path, fair: float = 30.0):
    fields = [
        "id_product", "eu_fair_value_eur", "eu_price_confidence_score", "liquidity_score",
        "us_fair_value_eur", "us_price_confidence_score", "us_liquidity_score",
        "exit_confidence_score", "bridge_opportunity_score", "best_validated_buy_eur",
        "best_sell_channel", "best_sell_gross_eur", "best_sell_net_eur", "route_signal",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "id_product": 123, "eu_fair_value_eur": fair, "eu_price_confidence_score": 85,
            "liquidity_score": 80, "us_fair_value_eur": 28, "us_price_confidence_score": 82,
            "us_liquidity_score": 84, "exit_confidence_score": 75,
            "bridge_opportunity_score": 72, "best_validated_buy_eur": 20,
            "best_sell_channel": "CARDTRADER_ZERO", "best_sell_gross_eur": 40,
            "best_sell_net_eur": 36, "route_signal": "RESELL_TEST",
        })


def _cfg():
    return {
        "version": "0.11",
        "model_validation": {
            "calibration_horizons_days": [7],
            "holding_horizons_days": [90],
            "terminal_window_half_width_days": 2,
        },
    }


def test_forecast_is_immutable_and_first_snapshot_of_week_is_benchmark(tmp_path):
    conn = _conn()
    route = tmp_path / "routes.csv"
    monday = date(2026, 9, 14)
    _route(route, 30.0)
    assert freeze_predictions(conn, _cfg(), route, monday) == 1

    # Re-running the same model/date with a changed input must not rewrite history.
    _route(route, 99.0)
    assert freeze_predictions(conn, _cfg(), route, monday) == 0
    row = conn.execute("SELECT * FROM model_predictions").fetchone()
    assert row["eu_fair_value_eur"] == 30.0
    assert row["is_weekly_benchmark"] == 1
    assert row["benchmark_week"] == "2026-W38"

    # A later daily snapshot in the same ISO week remains rolling-only.
    assert freeze_predictions(conn, {**_cfg(), "version": "0.11b"}, route, monday + timedelta(days=1)) == 1
    row2 = conn.execute("SELECT * FROM model_predictions WHERE model_version='0.11b'").fetchone()
    assert row2["is_weekly_benchmark"] == 0


def test_t7_outcome_uses_future_window_and_stores_error(tmp_path):
    conn = _conn()
    route = tmp_path / "routes.csv"
    start = date(2026, 9, 1)
    _route(route, 30.0)
    freeze_predictions(conn, _cfg(), route, start)

    # Confirmed future EU sales; median is 31, so forecast error is +3.333%.
    for i, price in enumerate((29.0, 31.0, 34.0), start=1):
        conn.execute(
            """INSERT INTO model_realised_sales(
              sale_id,id_product,sale_date,market,region,price_value,currency,price_eur,
              condition,language,evidence_strength,source,notes
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f"s{i}", 123, (start + timedelta(days=i)).isoformat(), "EBAY_IE", "EU", price, "EUR", price,
             "NM", "English", "CONFIRMED", "test", ""),
        )
    conn.commit()

    added = mature_outcomes(conn, _cfg(), start + timedelta(days=7))
    assert added >= 1
    out = conn.execute(
        "SELECT * FROM model_outcomes WHERE horizon_days=7 AND target_scope='EU_FAIR_VALUE'"
    ).fetchone()
    assert round(out["realised_value_eur"], 2) == 31.00
    assert round(out["error_pct"], 2) == 3.33
    assert out["evidence_quality"] == "CONFIRMED"
    assert out["window_start"] == "2026-09-02"
    assert out["window_end"] == "2026-09-08"


def test_90_day_holding_target_uses_terminal_window_not_full_path(tmp_path):
    conn = _conn()
    route = tmp_path / "routes.csv"
    start = date(2026, 1, 1)
    _route(route, 100.0)
    freeze_predictions(conn, _cfg(), route, start)

    # An early observation must not contaminate the 90d holding mark.
    conn.execute(
        "INSERT INTO model_market_observations VALUES(?,?,?,?,?,?,?,?)",
        ((start + timedelta(days=2)).isoformat(), 123, "EU", "CARDMARKET_AVG1_PROXY", 50.0, "PROXY", 1, "{}"),
    )
    for offset, value in ((88, 108.0), (90, 110.0), (92, 112.0)):
        conn.execute(
            "INSERT INTO model_market_observations VALUES(?,?,?,?,?,?,?,?)",
            ((start + timedelta(days=offset)).isoformat(), 123, "EU", "CARDMARKET_AVG1_PROXY", value, "PROXY", 1, "{}"),
        )
    conn.commit()

    mature_outcomes(conn, _cfg(), start + timedelta(days=92))
    out = conn.execute(
        "SELECT * FROM model_outcomes WHERE horizon_days=90 AND target_scope='EU_FAIR_VALUE'"
    ).fetchone()
    assert out["horizon_class"] == "HOLDING"
    assert out["window_start"] == "2026-03-30"
    assert out["window_end"] == "2026-04-03"
    assert round(out["realised_value_eur"], 2) == 110.00
