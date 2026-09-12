from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_scanner.cardtrader import CardTraderClient, normalize_marketplace
from deal_scanner.config import load_config, resolve_path
from deal_scanner.cross_price import build_cross_price_research, configured_bands
from deal_scanner.db import (
    blueprint_product_map_for_expansion,
    connect,
    expansion_ids_for_products,
    insert_cardtrader_offers,
    latest_rows_with_history,
    latest_snapshot_date,
)
from deal_scanner.mapping_audit import apply_cardtrader_mapping_guard
from deal_scanner.reports import CROSS_PRICE_FIELDS, scored_rows, write_csv


def panel(conn, cfg: dict) -> list[dict]:
    return build_cross_price_research(scored_rows(latest_rows_with_history(conn), cfg), cfg)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--output", default="output/cross_price_research.csv")
    args = parser.parse_args()

    cfg = load_config(args.config)
    token_env = cfg["cardtrader"]["token_env"]
    token = os.environ.get(token_env)
    if not token:
        raise SystemExit(f"Missing {token_env}")

    db_path = resolve_path(cfg, cfg["paths"]["database"])
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path

    conn = connect(db_path)
    try:
        snapshot_date = latest_snapshot_date(conn)
        if not snapshot_date:
            raise SystemExit("No Cardmarket snapshot available")

        initial = panel(conn, cfg)
        candidate_ids = sorted({int(row["id_product"]) for row in initial})
        candidate_set = set(candidate_ids)
        expansion_ids = expansion_ids_for_products(conn, candidate_ids)

        client = CardTraderClient(
            cfg["sources"]["cardtrader_base_url"],
            token,
            other_delay=float(cfg["cardtrader"]["other_delay_seconds"]),
            marketplace_delay=float(cfg["cardtrader"]["marketplace_delay_seconds"]),
        )

        inserted = 0
        queried = 0
        failed: list[int] = []
        for eid in expansion_ids:
            bpmap = blueprint_product_map_for_expansion(conn, eid)
            try:
                payload = client.marketplace(eid, language=cfg["cardtrader"]["language"])
            except Exception as exc:
                print(f"CardTrader research query failed for expansion {eid}: {exc}", flush=True)
                failed.append(eid)
                continue
            normalized = normalize_marketplace(payload, bpmap)
            filtered = [offer for offer in normalized if offer.get("id_product") in candidate_set]
            inserted += insert_cardtrader_offers(conn, filtered, snapshot_date)
            queried += 1

        # Re-apply the exact mapping guard to the isolated research copy before
        # deriving any EN/NM floor from newly inserted offers.
        apply_cardtrader_mapping_guard(
            conn,
            snapshot_date,
            ROOT / "data" / "reference" / "cardtrader_mapping_overrides.csv",
            ROOT / "output" / "cross_price_mapping_audit.csv",
        )

        selected = panel(conn, cfg)
        write_csv(output_path, selected, CROSS_PRICE_FIELDS)
    finally:
        conn.close()

    bands = configured_bands(cfg)
    counts = {band.label: 0 for band in bands}
    validated = 0
    for row in selected:
        counts[row["reference_band"]] = counts.get(row["reference_band"], 0) + 1
        if row.get("acquisition_basis") == "VALIDATED_EN_NM":
            validated += 1

    print(f"Cross-price CardTrader research: candidates={len(candidate_ids)} expansions={len(expansion_ids)} queried={queried} failed={len(failed)} offers_inserted={inserted}")
    print("Band counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    print(f"Validated EN/NM acquisition rows after enrichment: {validated}/{len(selected)}")
    if failed:
        print("Failed expansion ids: " + ",".join(map(str, failed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
