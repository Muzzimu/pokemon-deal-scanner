from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_scanner.config import load_config, resolve_path
from deal_scanner.cross_price import build_cross_price_research, configured_bands
from deal_scanner.db import connect, latest_rows_with_history
from deal_scanner.reports import CROSS_PRICE_FIELDS, scored_rows, write_csv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--output", default="output/cross_price_research.csv")
    args = parser.parse_args()

    cfg = load_config(args.config)
    db_path = resolve_path(cfg, cfg["paths"]["database"])
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path

    conn = connect(db_path)
    try:
        rows = scored_rows(latest_rows_with_history(conn), cfg)
        selected = build_cross_price_research(rows, cfg)
    finally:
        conn.close()

    write_csv(output_path, selected, CROSS_PRICE_FIELDS)

    bands = configured_bands(cfg)
    counts = {band.label: 0 for band in bands}
    validated = 0
    for row in selected:
        counts[row["reference_band"]] = counts.get(row["reference_band"], 0) + 1
        if row.get("acquisition_basis") == "VALIDATED_EN_NM":
            validated += 1

    print(f"Cross-price research written to {output_path.relative_to(ROOT)} ({len(selected)} rows)")
    print("Band counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    print(f"Validated EN/NM acquisition rows: {validated}/{len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
