from __future__ import annotations

from datetime import date, timedelta


def _distinct_dates(conn, table: str, column: str) -> list[date]:
    rows = conn.execute(f"SELECT DISTINCT {column} AS d FROM {table} ORDER BY {column}").fetchall()
    out = []
    for row in rows:
        try:
            out.append(date.fromisoformat(str(row["d"])[:10]))
        except (TypeError, ValueError):
            continue
    return out


def _keep_dates(dates: list[date], today: date, daily_days: int, weekly_days: int) -> set[date]:
    daily_cutoff = today - timedelta(days=max(0, daily_days))
    weekly_cutoff = today - timedelta(days=max(daily_days, weekly_days))
    keep: set[date] = set()
    weekly: dict[tuple[int, int], date] = {}
    monthly: dict[tuple[int, int], date] = {}

    for d in dates:
        if d >= daily_cutoff:
            keep.add(d)
        elif d >= weekly_cutoff:
            iso = d.isocalendar()
            weekly[(iso.year, iso.week)] = max(d, weekly.get((iso.year, iso.week), d))
        else:
            monthly[(d.year, d.month)] = max(d, monthly.get((d.year, d.month), d))
    keep.update(weekly.values())
    keep.update(monthly.values())
    return keep


def compact_history(conn, cfg: dict, today: date | None = None) -> dict:
    """Bound the SQLite cache without destroying useful long-term trend history.

    Cardmarket snapshots remain daily for the recent window, then weekly, then
    monthly.  Raw CardTrader offers are intentionally short-lived because the
    daily aggregate reports already preserve the useful signal.
    """
    today = today or date.today()
    hcfg = cfg.get("history_retention", {})
    daily_days = int(hcfg.get("cardmarket_daily_days", 90))
    weekly_days = int(hcfg.get("cardmarket_weekly_until_days", 365))
    ct_raw_days = int(hcfg.get("cardtrader_raw_offer_days", 30))
    ebay_gone_days = int(hcfg.get("ebay_gone_listing_days", 30))

    deleted_cm = 0
    cm_dates = _distinct_dates(conn, "price_snapshots", "snapshot_date")
    keep = _keep_dates(cm_dates, today, daily_days, weekly_days)
    drop = [d.isoformat() for d in cm_dates if d not in keep]
    for d in drop:
        cur = conn.execute("DELETE FROM price_snapshots WHERE snapshot_date=?", (d,))
        deleted_cm += max(0, cur.rowcount)

    ct_cutoff = (today - timedelta(days=ct_raw_days)).isoformat()
    cur = conn.execute("DELETE FROM cardtrader_offer_snapshots WHERE snapshot_date < ?", (ct_cutoff,))
    deleted_ct = max(0, cur.rowcount)

    deleted_ebay = 0
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ebay_listing_state'"
    ).fetchone()
    if table:
        ebay_cutoff = (today - timedelta(days=ebay_gone_days)).isoformat()
        cur = conn.execute(
            "DELETE FROM ebay_listing_state WHERE gone_at IS NOT NULL AND gone_at < ?",
            (ebay_cutoff,),
        )
        deleted_ebay = max(0, cur.rowcount)

    conn.commit()
    return {
        "cardmarket_snapshot_dates_before": len(cm_dates),
        "cardmarket_snapshot_dates_kept": len(keep),
        "cardmarket_rows_deleted": deleted_cm,
        "cardtrader_raw_rows_deleted": deleted_ct,
        "ebay_gone_listing_rows_deleted": deleted_ebay,
        "policy": f"Cardmarket daily {daily_days}d -> weekly to {weekly_days}d -> monthly; CardTrader raw {ct_raw_days}d; gone eBay listings {ebay_gone_days}d",
    }
