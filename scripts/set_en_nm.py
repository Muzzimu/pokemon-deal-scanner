from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "data" / "reference" / "en_nm_overrides.csv"


def main() -> int:
    ap = argparse.ArgumentParser(description="Add/update a manually validated Cardmarket English+NM floor.")
    ap.add_argument("id_product", type=int)
    ap.add_argument("price", type=float)
    ap.add_argument("--source", default="Cardmarket EN+NM offer check")
    ap.add_argument("--notes", default="")
    ap.add_argument("--file", default=str(DEFAULT))
    args = ap.parse_args()
    path = Path(args.file)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "id_product": str(args.id_product),
        "en_nm_floor_eur": f"{args.price:.2f}",
        "checked_at": now,
        "source": args.source,
        "notes": args.notes,
    }
    by_id = {str(r.get("id_product")): r for r in rows if r.get("id_product")}
    by_id[str(args.id_product)] = item
    fields = ["id_product", "en_nm_floor_eur", "checked_at", "source", "notes"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for key in sorted(by_id, key=lambda x: int(x)):
            w.writerow(by_id[key])
    print(f"Saved Cardmarket EN+NM floor for {args.id_product}: €{args.price:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
