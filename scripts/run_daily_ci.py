from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_DAILY = ROOT / "scripts" / "run_daily.py"

spec = importlib.util.spec_from_file_location("pokemon_run_daily", RUN_DAILY)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load {RUN_DAILY}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

_original_insert_price_snapshot = mod.insert_price_snapshot


def safe_insert_price_snapshot(conn, rows, snapshot_date, source_created_at):
    """Ignore Cardmarket price-guide rows whose product IDs are absent from the downloaded catalogue.

    Cardmarket's daily price guide can temporarily contain stale/retired product IDs that are not
    present in products_singles_6.json. With the database foreign-key constraint enabled, inserting
    those rows would abort the whole daily scan. We retain only IDs that exist in the current product
    table and report the skipped count to stdout.
    """
    valid_ids = {int(r[0]) for r in conn.execute("SELECT id_product FROM products")}
    filtered = []
    skipped = 0
    for row in rows:
        pid = row.get("idProduct", row.get("id_product", row.get("id")))
        try:
            pid_i = int(pid)
        except (TypeError, ValueError):
            skipped += 1
            continue
        if pid_i in valid_ids:
            filtered.append(row)
        else:
            skipped += 1
    if skipped:
        print(f"Cardmarket price rows skipped because product is absent from catalogue: {skipped}")
    return _original_insert_price_snapshot(conn, filtered, snapshot_date, source_created_at)


mod.insert_price_snapshot = safe_insert_price_snapshot

if __name__ == "__main__":
    raise SystemExit(mod.main())
