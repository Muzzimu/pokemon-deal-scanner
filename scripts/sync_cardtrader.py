from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_scanner.cardtrader import CardTraderClient, blueprint_rows, expansion_id, expansion_name, pokemon_expansions
from deal_scanner.config import load_config, resolve_path
from deal_scanner.db import cardtrader_mapping_count, connect, set_sync_state, upsert_cardtrader_blueprints


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/refresh CardTrader Blueprint -> Cardmarket product mapping")
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--bootstrap", action="store_true", help="Explicitly confirm full Pokémon Blueprint bootstrap")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if not args.bootstrap:
        raise SystemExit("Use --bootstrap to confirm the full initial mapping refresh.")
    token = os.environ.get(cfg["cardtrader"]["token_env"])
    if not token:
        raise SystemExit(f"Missing environment variable {cfg['cardtrader']['token_env']}")
    conn = connect(resolve_path(cfg, cfg["paths"]["database"]))
    client = CardTraderClient(
        cfg["sources"]["cardtrader_base_url"], token,
        other_delay=float(cfg["cardtrader"]["other_delay_seconds"]),
        marketplace_delay=float(cfg["cardtrader"]["marketplace_delay_seconds"]),
    )
    now = datetime.now(timezone.utc).isoformat()
    exps = pokemon_expansions(client.expansions())
    totals = {"expansions": 0, "blueprints": 0, "mappings": 0}
    for e in exps:
        eid = expansion_id(e)
        if eid is None:
            continue
        bps = blueprint_rows(client.blueprints(eid))
        b, m = upsert_cardtrader_blueprints(
            conn, bps, expansion_id=eid, expansion_name=expansion_name(e), updated_at=now
        )
        totals["expansions"] += 1
        totals["blueprints"] += b
        totals["mappings"] += m
        print(f"{totals['expansions']:>4} expansions | {totals['blueprints']:>7} blueprints | {totals['mappings']:>7} mappings", end="\r")
    set_sync_state(conn, "cardtrader_blueprint_bootstrap", now, now)
    totals["mapping_rows_in_db"] = cardtrader_mapping_count(conn)
    print()
    print(json.dumps(totals, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
