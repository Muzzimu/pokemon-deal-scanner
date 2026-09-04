from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_scanner.baskets import build_seller_baskets, write_seller_baskets
from deal_scanner.cardmarket import copy_fixture, download, latest_archive, read_catalog, read_price_guide
from deal_scanner.cardtrader import CardTraderClient, blueprint_rows, expansion_id, expansion_name, normalize_marketplace, pokemon_expansions
from deal_scanner.config import load_config, resolve_path
from deal_scanner.db import (
    blueprint_product_map_for_expansion,
    cardtrader_mapping_count,
    connect,
    expansion_ids_for_products,
    insert_cardtrader_offers,
    insert_price_snapshot,
    latest_cardtrader_snapshot_date,
    load_en_nm_overrides,
    product_ids_for_candidate_query,
    set_sync_state,
    upsert_cardtrader_blueprints,
    upsert_products,
)
from deal_scanner.reports import generate_reports
from deal_scanner.sourcing import generate_cardmarket_sourcing_report


def refresh_catalog_needed(cfg, archive_dir: Path, today: date) -> bool:
    existing = latest_archive(archive_dir, "products_singles_6")
    if not existing:
        return True
    age_days = (today - datetime.fromtimestamp(existing.stat().st_mtime).date()).days
    return today.weekday() == int(cfg["catalog"]["refresh_weekday"]) or age_days >= int(cfg["catalog"]["refresh_if_older_days"])


def bootstrap_cardtrader(conn, client: CardTraderClient) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    payload = client.expansions()
    exps = pokemon_expansions(payload)
    bp_count = map_count = exp_count = 0
    for e in exps:
        eid = expansion_id(e)
        if eid is None:
            continue
        bps = blueprint_rows(client.blueprints(eid))
        b, m = upsert_cardtrader_blueprints(
            conn, bps, expansion_id=eid, expansion_name=expansion_name(e), updated_at=now
        )
        exp_count += 1
        bp_count += b
        map_count += m
    set_sync_state(conn, "cardtrader_blueprint_bootstrap", now, now)
    return {"expansions": exp_count, "blueprints": bp_count, "mappings": map_count}


def sync_cardtrader_marketplace(conn, cfg, client: CardTraderClient, today: str) -> dict:
    names = list(cfg["bundles"]["characters"])
    names.append(cfg["watchlists"]["dragonite"]["query"])
    candidate_ids = product_ids_for_candidate_query(
        conn,
        max_generic_low=float(cfg["cardtrader"]["candidate_generic_low_max_eur"]),
        names=sorted(set(names)),
        max_rows=int(cfg["cardtrader"]["max_candidate_products"]),
    )
    expansion_ids = expansion_ids_for_products(conn, candidate_ids)
    inserted = 0
    queried = 0
    candidate_set = set(candidate_ids)
    for eid in expansion_ids:
        bpmap = blueprint_product_map_for_expansion(conn, eid)
        payload = client.marketplace(eid, language=cfg["cardtrader"]["language"])
        normalized = normalize_marketplace(payload, bpmap)
        filtered = [o for o in normalized if o.get("id_product") in candidate_set]
        inserted += insert_cardtrader_offers(conn, filtered, today)
        queried += 1
    return {
        "candidate_products": len(candidate_ids),
        "expansions_queried": queried,
        "offer_rows_inserted": inserted,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--demo", action="store_true", help="Use bundled offline Cardmarket + CardTrader fixtures")
    ap.add_argument("--no-archive", action="store_true", help="Use temporary Cardmarket downloads instead of raw archive")
    ap.add_argument("--skip-cardtrader", action="store_true")
    ap.add_argument("--bootstrap-cardtrader", action="store_true", help="Force Blueprint-map refresh before marketplace sync")
    args = ap.parse_args()

    cfg = load_config(args.config)
    today = date.today()
    today_s = today.isoformat()
    db_path = resolve_path(cfg, cfg["paths"]["database"])
    raw_dir = resolve_path(cfg, cfg["paths"]["raw_dir"])
    output_dir = resolve_path(cfg, cfg["paths"]["output_dir"])
    override_csv = resolve_path(cfg, cfg["paths"]["en_nm_overrides"])
    sourcing_csv = resolve_path(cfg, cfg["paths"]["cardmarket_sourcing_offers"])
    conn = connect(db_path)

    archive_dir = None if args.no_archive else raw_dir
    if args.demo:
        fixtures = ROOT / "tests" / "fixtures"
        catalog_path = copy_fixture(fixtures / "products_singles_6_demo.json", archive_dir=archive_dir,
                                    stem="products_singles_6", snapshot_date=today)
        price_path = copy_fixture(fixtures / "price_guide_6_demo.json", archive_dir=archive_dir,
                                  stem="price_guide_6", snapshot_date=today)
    else:
        existing_catalog = latest_archive(raw_dir, "products_singles_6") if not args.no_archive else None
        if args.no_archive or refresh_catalog_needed(cfg, raw_dir, today):
            catalog_path = download(cfg["sources"]["cardmarket_catalog_url"], archive_dir=archive_dir,
                                    stem="products_singles_6", snapshot_date=today)
        else:
            catalog_path = existing_catalog
        price_path = download(cfg["sources"]["cardmarket_price_url"], archive_dir=archive_dir,
                              stem="price_guide_6", snapshot_date=today)

    catalog = read_catalog(catalog_path)
    prices, source_created_at = read_price_guide(price_path)
    product_count = upsert_products(conn, catalog, today_s)
    price_count = insert_price_snapshot(conn, prices, today_s, source_created_at)
    validated_count = load_en_nm_overrides(conn, override_csv)

    cardtrader_status: dict = {"enabled": False, "reason": "not configured"}
    if args.demo and not args.skip_cardtrader:
        fixtures = ROOT / "tests" / "fixtures"
        bp_payload = json.loads((fixtures / "cardtrader_blueprints_demo.json").read_text(encoding="utf-8"))
        bps = blueprint_rows(bp_payload)
        b, m = upsert_cardtrader_blueprints(
            conn, bps, expansion_id=999001, expansion_name="Demo Expansion",
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        market_payload = json.loads((fixtures / "cardtrader_marketplace_demo.json").read_text(encoding="utf-8"))
        bpmap = blueprint_product_map_for_expansion(conn, 999001)
        normalized = normalize_marketplace(market_payload, bpmap)
        offers = insert_cardtrader_offers(conn, normalized, today_s)
        cardtrader_status = {"enabled": True, "mode": "demo", "blueprints": b, "mappings": m, "offer_rows": offers}
    elif not args.skip_cardtrader and cfg.get("cardtrader", {}).get("enabled", True):
        token = os.environ.get(cfg["cardtrader"]["token_env"])
        if token:
            client = CardTraderClient(
                cfg["sources"]["cardtrader_base_url"], token,
                other_delay=float(cfg["cardtrader"]["other_delay_seconds"]),
                marketplace_delay=float(cfg["cardtrader"]["marketplace_delay_seconds"]),
            )
            bootstrap_status = None
            if args.bootstrap_cardtrader or (
                cardtrader_mapping_count(conn) == 0 and cfg["cardtrader"].get("auto_bootstrap_if_empty", True)
            ):
                bootstrap_status = bootstrap_cardtrader(conn, client)
            sync_status = sync_cardtrader_marketplace(conn, cfg, client, today_s)
            cardtrader_status = {"enabled": True, "mode": "live", "bootstrap": bootstrap_status, **sync_status}
        else:
            cardtrader_status = {"enabled": False, "reason": f"missing {cfg['cardtrader']['token_env']}"}

    generate_reports(conn, cfg, output_dir)
    ct_date = latest_cardtrader_snapshot_date(conn)
    seller_rows = build_seller_baskets(conn, ct_date, cfg)
    write_seller_baskets(output_dir / "seller_baskets.csv", seller_rows)
    sourcing_status = generate_cardmarket_sourcing_report(
        conn, cfg, sourcing_csv, output_dir / "cardmarket_sourcing.csv"
    )

    status_path = output_dir / "scanner_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status.update({
        "version": str(cfg.get("version", "unknown")),
        "products_upserted": product_count,
        "price_rows_upserted": price_count,
        "manual_cardmarket_en_nm_overrides_loaded": validated_count,
        "cardtrader": cardtrader_status,
        "cardmarket_sourcing": sourcing_status,
        "seller_basket_rows": len(seller_rows),
    })
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")

    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
