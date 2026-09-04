from __future__ import annotations

from datetime import date, timedelta

from deal_scanner.db import connect
from deal_scanner.maintenance import compact_history


def test_history_compaction_keeps_recent_and_downsamples_old_dates(tmp_path):
    conn = connect(tmp_path / "history.sqlite")
    conn.execute(
        "INSERT INTO products(id_product,name,last_seen_catalog) VALUES(?,?,?)",
        (1, "Test ex", "2026-09-04"),
    )
    today = date(2026, 9, 4)
    dates = [
        today,
        today - timedelta(days=10),
        today - timedelta(days=100),
        today - timedelta(days=101),
        today - timedelta(days=400),
        today - timedelta(days=401),
    ]
    for d in dates:
        conn.execute(
            "INSERT INTO price_snapshots(snapshot_date,id_product,low) VALUES(?,?,?)",
            (d.isoformat(), 1, 1.0),
        )
    conn.execute(
        "INSERT INTO cardtrader_offer_snapshots(snapshot_date,blueprint_id,offer_id,id_product,quantity,price_eur,language,condition,graded,on_vacation,ct_zero) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ((today - timedelta(days=40)).isoformat(), 1, 1, 1, 1, 1.0, "en", "Near Mint", 0, 0, 0),
    )
    conn.commit()

    cfg = {
        "history_retention": {
            "cardmarket_daily_days": 90,
            "cardmarket_weekly_until_days": 365,
            "cardtrader_raw_offer_days": 30,
            "ebay_gone_listing_days": 30,
        }
    }
    status = compact_history(conn, cfg, today=today)
    remaining = [r["snapshot_date"] for r in conn.execute("SELECT snapshot_date FROM price_snapshots ORDER BY snapshot_date")]
    assert today.isoformat() in remaining
    assert (today - timedelta(days=10)).isoformat() in remaining
    assert len(remaining) < len(dates)
    assert status["cardtrader_raw_rows_deleted"] == 1
