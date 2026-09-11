from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_scanner.arbitrage import build_arbitrage_report, fetch_fx_rates, write_status
from deal_scanner.config import load_config, resolve_path
from deal_scanner.db import connect
from deal_scanner.gumtree import scan_gumtree
from deal_scanner.gumtree_catalog_match import enrich_gumtree_catalog_matches


def main() -> int:
    cfg = load_config(ROOT / "config.yaml")
    db_path = resolve_path(cfg, cfg["paths"]["database"])
    output_dir = resolve_path(cfg, cfg["paths"]["output_dir"])
    watchlist = resolve_path(cfg, cfg["paths"]["gumtree_watchlist"])
    resale_path = output_dir / "resale_candidates.csv"
    gumtree_path = output_dir / "gumtree_candidates.csv"

    conn = connect(db_path)
    gumtree_status = scan_gumtree(
        conn,
        cfg,
        watchlist,
        gumtree_path,
        today=date.today(),
    )
    catalog_status = enrich_gumtree_catalog_matches(conn, gumtree_path)
    gumtree_status["catalog_match"] = catalog_status
    gumtree_status["exact_match_rows"] = int(gumtree_status.get("exact_match_rows") or 0) + int(
        catalog_status.get("new_exact_matches") or 0
    )

    fx = fetch_fx_rates(cfg)
    rows, arbitrage_status = build_arbitrage_report(
        conn,
        cfg,
        gumtree_path,
        resale_path,
        output_dir / "arbitrage_candidates.csv",
        fx=fx,
        today=date.today(),
    )
    write_status(output_dir / "gumtree_arbitrage_status.json", gumtree_status, arbitrage_status)

    scanner_status_path = output_dir / "scanner_status.json"
    if scanner_status_path.exists():
        scanner_status = json.loads(scanner_status_path.read_text(encoding="utf-8"))
    else:
        scanner_status = {}
    scanner_status["version"] = str(cfg.get("version", scanner_status.get("version", "unknown")))
    scanner_status["gumtree"] = gumtree_status
    scanner_status["arbitrage"] = arbitrage_status
    scanner_status_path.write_text(json.dumps(scanner_status, indent=2), encoding="utf-8")

    print(json.dumps({
        "gumtree": gumtree_status,
        "arbitrage": arbitrage_status,
        "output_rows": len(rows),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
