from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_scanner.db import connect
from deal_scanner.provider_usage import append_provider_usage
from deal_scanner.scrapebadger_research import (
    ScrapeBadgerClient,
    VINTED_FIELDS,
    merge_vinted_detail,
    normalize_vinted_item,
    persist_vinted,
    read_watchlist,
    utc_now,
    write_csv,
)


WATCHLIST = ROOT / "data" / "reference" / "vinted_watchlist.csv"
DB_PATH = ROOT / "db" / "scrapebadger_research.sqlite"
OUTPUT = ROOT / "output" / "vinted_candidates.csv"
STATUS = ROOT / "output" / "scrapebadger_vinted_status.json"
USAGE_PATH = ROOT / "dashboard" / "data" / "provider_usage.csv"
PUBLIC_FIELDS = [field for field in VINTED_FIELDS if field != "seller_id"]
MARKET = "ie"


def write_status(payload: dict) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    snapshot_date, observed_at = utc_now()
    watches = read_watchlist(WATCHLIST)
    client = ScrapeBadgerClient()

    if not client.configured:
        write_csv(OUTPUT, [], PUBLIC_FIELDS)
        write_status({
            "source": "SCRAPEBADGER_VINTED",
            "status": "UNAVAILABLE",
            "reason": "missing SCRAPEBADGER_API_KEY",
            "snapshot_date": snapshot_date,
            "queries": 0,
            "rows": 0,
        })
        append_provider_usage(
            USAGE_PATH, provider="SCRAPEBADGER", operation="vinted_research", requests=0,
            documented_credits=0, status="UNAVAILABLE", rows=0, notes="missing SCRAPEBADGER_API_KEY",
        )
        print("ScrapeBadger Vinted pilot skipped: missing SCRAPEBADGER_API_KEY")
        return 0

    all_rows: list[dict] = []
    errors: list[dict] = []
    search_requests = 0
    detail_requests = 0

    for watch in watches:
        search_requests += 1
        try:
            payload = client.vinted_search(
                str(watch["search_query"]),
                market=MARKET,
                per_page=20,
                catalog_ids=watch.get("catalog_id") or None,
                order="newest_first",
            )
        except Exception as exc:  # optional source degrades independently
            errors.append({
                "query_id": watch.get("query_id"),
                "stage": "search",
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue

        search_items = [x for x in (payload.get("items") or []) if isinstance(x, dict)]
        query_rows: list[dict] = []
        item_by_id: dict[str, dict] = {}
        for item in search_items:
            item_id = str(item.get("id") or "")
            if item_id:
                item_by_id[item_id] = item
            row = normalize_vinted_item(
                item,
                snapshot_date=snapshot_date,
                observed_at=observed_at,
                market=MARKET,
                watch=watch,
                detail_checked=False,
            )
            if row:
                query_rows.append(row)

        try:
            detail_limit = max(0, int(watch.get("max_detail_rows") or 0))
        except (TypeError, ValueError):
            detail_limit = 0

        # Prefer title-level matches. If Vinted's fuzzy search produced none, detail
        # the first result as an audit/control rather than pretending the query failed.
        matching = [
            row for row in query_rows
            if row["identity_status"] not in {"REVIEW_OR_REJECT", "LOT_OR_BUNDLE"}
        ]
        detail_targets = matching[:detail_limit]
        if detail_limit and not detail_targets and query_rows:
            detail_targets = query_rows[:1]

        for search_row in detail_targets:
            item_id = str(search_row["item_id"])
            detail_requests += 1
            try:
                detail_payload = client.vinted_item(item_id, market=MARKET)
                merged = merge_vinted_detail(item_by_id.get(item_id, {}), detail_payload)
                detail_row = normalize_vinted_item(
                    merged,
                    snapshot_date=snapshot_date,
                    observed_at=observed_at,
                    market=MARKET,
                    watch=watch,
                    detail_checked=True,
                )
                if detail_row:
                    query_rows = [detail_row if r["item_id"] == item_id else r for r in query_rows]
            except Exception as exc:
                errors.append({
                    "query_id": watch.get("query_id"),
                    "item_id": item_id,
                    "stage": "detail",
                    "error": f"{type(exc).__name__}: {exc}",
                })
                # Search visibility is not executable proof. A failed detail call is
                # recorded as unknown rather than sold/removed.
                for row in query_rows:
                    if row["item_id"] == item_id:
                        row["detail_checked"] = 1
                        row["listing_state"] = "DETAIL_UNAVAILABLE"

        all_rows.extend(query_rows)

    conn = connect(DB_PATH)
    written = persist_vinted(conn, all_rows)
    conn.close()
    write_csv(OUTPUT, all_rows, PUBLIC_FIELDS)

    status = "OK" if not errors else ("DEGRADED" if all_rows else "UNAVAILABLE")
    counts: dict[str, int] = {}
    for row in all_rows:
        state = str(row.get("listing_state") or "UNKNOWN")
        counts[state] = counts.get(state, 0) + 1

    estimated_credits = search_requests * 5 + detail_requests * 10
    write_status({
        "source": "SCRAPEBADGER_VINTED",
        "status": status,
        "snapshot_date": snapshot_date,
        "market": MARKET,
        "watch_queries": len(watches),
        "search_requests": search_requests,
        "detail_requests": detail_requests,
        "estimated_doc_credits": estimated_credits,
        "rows": len(all_rows),
        "db_rows_written": written,
        "listing_state_counts": counts,
        "exact_or_likely_matches": sum(
            str(r.get("identity_status", "")).startswith(("EXACT_", "LIKELY_", "SEARCH_MATCH_"))
            for r in all_rows
        ),
        "lot_or_bundle_rows": sum(r.get("identity_status") == "LOT_OR_BUNDLE" for r in all_rows),
        "errors": errors,
        "roles": [
            "VINTED_ACTIVE_DISCOVERY",
            "VINTED_LOT_DISCOVERY",
            "VINTED_RESALE_DIAGNOSTIC",
            "VINTED_CLOSED_STATE_UNPRICED",
        ],
        "valuation_weight": 0,
        "storage": "isolated research database",
    })
    append_provider_usage(
        USAGE_PATH,
        provider="SCRAPEBADGER",
        operation="vinted_research",
        requests=search_requests + detail_requests,
        documented_credits=estimated_credits,
        status=status,
        rows=len(all_rows),
        notes=f"search={search_requests}; detail={detail_requests}",
    )
    print(
        f"ScrapeBadger Vinted pilot: status={status} search={search_requests} detail={detail_requests} "
        f"rows={len(all_rows)} states={counts}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
