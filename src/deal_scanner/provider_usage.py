from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

USAGE_FIELDS = [
    "observed_at_utc",
    "snapshot_date",
    "provider",
    "operation",
    "requests",
    "documented_credits",
    "status",
    "rows",
    "run_id",
    "notes",
]


def _clean(value) -> str:
    return "" if value is None else str(value)


def append_provider_usage(
    path: Path,
    *,
    provider: str,
    operation: str,
    requests: int = 0,
    documented_credits: int | float | None = None,
    status: str = "OK",
    rows: int | None = None,
    notes: str = "",
    observed_at_utc: str | None = None,
) -> dict:
    """Append one provider-usage observation without creating duplicate run rows.

    `documented_credits` is only populated when the provider documents the unit cost
    or account UI confirms it. Unknown credit conversion remains blank.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    now = observed_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    snapshot_date = now[:10]
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    record = {
        "observed_at_utc": now,
        "snapshot_date": snapshot_date,
        "provider": provider,
        "operation": operation,
        "requests": int(requests or 0),
        "documented_credits": "" if documented_credits is None else documented_credits,
        "status": status,
        "rows": "" if rows is None else int(rows),
        "run_id": run_id,
        "notes": notes,
    }

    existing: list[dict] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            existing = [dict(row) for row in csv.DictReader(fh)]
    key = (run_id, provider, operation)
    existing = [
        row for row in existing
        if (str(row.get("run_id")), str(row.get("provider")), str(row.get("operation"))) != key
    ]
    existing.append({field: _clean(record.get(field)) for field in USAGE_FIELDS})
    existing.sort(key=lambda r: (r.get("observed_at_utc", ""), r.get("provider", ""), r.get("operation", "")))

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=USAGE_FIELDS)
        writer.writeheader()
        writer.writerows(existing)
    return record
