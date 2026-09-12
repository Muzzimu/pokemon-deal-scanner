from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_scanner.db import connect
from deal_scanner.scrapebadger_research import (
    EBAY_COMPLETED_FIELDS,
    ScrapeBadgerClient,
    normalize_ebay_completed,
    persist_ebay_completed,
    utc_now,
    write_csv,
)


WATCHLIST = ROOT / "data" / "reference" / "ebay_watchlist.csv"
DB_PATH = ROOT / "db" / "scrapebadger_research.sqlite"
OUTPUT = ROOT / "output" / "ebay_completed_candidates_scrapebadger.csv"
STATUS = ROOT / "output" / "scrapebadger_ebay_status.json"
PUBLIC_FIELDS = [field for field in EBAY_COMPLETED_FIELDS if field != "seller_name"]

# Keep the first pilot deliberately small. These three domains cover local Ireland,
# one large continental-EU market, and global/US context without duplicating the
# production Browse API's role as the active-listing collector.
DOMAINS = ("ie", "de", "com")


def load_watchlist() -> list[dict]:
    if not WATCHLIST.exists():
        return []
    with WATCHLIST.open(newline="", encoding="utf-8") as f:
        rows = []
        for row in csv.DictReader(f):
            if not row.get("id_product") or not row.get("search_query"):
                continue
            item = dict(row)
            item["query_id"] = f"ebay_{item['id_product']}"
            rows.append(item)
        return rows


def write_status(payload: dict) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    snapshot_date, observed_at = utc_now()
    watches = load_watchlist()
    client = ScrapeBadgerClient()

    if not client.configured:
        write_csv(OUTPUT, [], PUBLIC_FIELDS)
        write_status({
            "source": "SCRAPEBADGER_EBAY_COMPLETED",
            "status": "UNAVAILABLE",
            "reason": "missing SCRAPEBADGER_API_KEY",
            "snapshot_date": snapshot_date,
            "queries": 0,
            "rows": 0,
        })
        print("ScrapeBadger eBay completed pilot skipped: missing SCRAPEBADGER_API_KEY")
        return 0

    rows: list[dict] = []
    errors: list[dict] = []
    requests_made = 0

    for watch in watches:
        for domain in DOMAINS:
            requests_made += 1
            try:
                payload = client.ebay_completed(
                    str(watch["search_query"]),
                    domain=domain,
                    per_page=60,
                    sort_by="newly_listed",
                )
            except Exception as exc:  # provider outage/rate-limit must not poison research collection
                errors.append({
                    "id_product": watch.get("id_product"),
                    "domain": domain,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                continue

            for item in payload.get("results") or []:
                if not isinstance(item, dict):
                    continue
                row = normalize_ebay_completed(
                    item,
                    snapshot_date=snapshot_date,
                    observed_at=str(payload.get("scraped_at") or observed_at),
                    domain=domain,
                    watch=watch,
                )
                if row:
                    rows.append(row)

    conn = connect(DB_PATH)
    inserted = persist_ebay_completed(conn, rows)
    conn.close()
    write_csv(OUTPUT, rows, PUBLIC_FIELDS)

    status = "OK" if not errors else ("DEGRADED" if rows else "UNAVAILABLE")
    write_status({
        "source": "SCRAPEBADGER_EBAY_COMPLETED",
        "status": status,
        "snapshot_date": snapshot_date,
        "watch_cards": len(watches),
        "domains": list(DOMAINS),
        "requests": requests_made,
        "estimated_doc_credits": requests_made * 5,
        "rows": len(rows),
        "exact_title_matches": sum(r["identity_status"] == "EXACT_TITLE_MATCH" for r in rows),
        "db_rows_written": inserted,
        "errors": errors,
        "role": "EBAY_COMPLETED_CANDIDATE",
        "valuation_weight": 0,
        "storage": "isolated research database",
    })
    print(
        f"ScrapeBadger eBay completed pilot: status={status} requests={requests_made} "
        f"rows={len(rows)} exact={sum(r['identity_status'] == 'EXACT_TITLE_MATCH' for r in rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
