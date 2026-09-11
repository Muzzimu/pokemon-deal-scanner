from __future__ import annotations

from deal_scanner.market_signals import (
    classify_market_signal,
    cross_market_confirmation,
    sales_velocity_ratio,
)


def test_cross_market_direction_requires_same_direction():
    assert cross_market_confirmation(12.0, 8.0) == "CONFIRMS_UP"
    assert cross_market_confirmation(-12.0, -8.0) == "CONFIRMS_DOWN"
    assert cross_market_confirmation(12.0, -8.0) == "DIVERGES"
    assert cross_market_confirmation(1.0, 2.0) == "BOTH_FLAT"


def test_sales_velocity_normalizes_different_windows():
    # 7 sales / 7d versus 23 sales / 23d = unchanged daily velocity.
    assert sales_velocity_ratio(7, 23) == 1.0
    assert sales_velocity_ratio(14, 23) == 2.0
    assert sales_velocity_ratio(0, 23) == 0.0


def test_palkia_style_pullback_is_not_called_acceleration():
    result = classify_market_signal({
        "cm_short_momentum_pct": -11.1,
        "cm_30d_change_pct": 14.0,
        "ebay_30d_change_pct": -8.0,
        "sales_velocity_ratio": 1.0,
        "supply_change_pct": -5.0,
        "event_flag": False,
        "event_direction": "",
    })
    assert result["signal_label"] == "PULLBACK"
    assert result["cross_market_confirmation"] == "DIVERGES"
    assert result["confidence"] == "MEDIUM"


def test_first_observation_can_call_cooling_but_keeps_low_confidence():
    result = classify_market_signal({
        "cm_short_momentum_pct": -11.1,
        "cm_30d_change_pct": -8.7,
        "ebay_30d_change_pct": None,
        "sales_velocity_ratio": None,
        "supply_change_pct": None,
        "event_flag": False,
    })
    assert result["signal_label"] == "COOLING"
    assert result["confidence"] == "LOW"
