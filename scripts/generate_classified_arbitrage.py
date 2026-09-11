from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_scanner.arbitrage import ARBITRAGE_FIELDS, build_arbitrage_report, fetch_fx_rates, write_status
from deal_scanner.config import load_config, resolve_path
from deal_scanner.db import connect
from deal_scanner.gumtree import scan_gumtree
from deal_scanner.gumtree_catalog_match import enrich_gumtree_catalog_matches


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _reconcile_cardmarket_net_edges(rows: list[dict], resale_path: Path, cfg: dict) -> None:
    """Apply the v0.7 net-cost definition to the pre-existing CM->eBay layer."""
    decisions = {str(r.get("id_product") or ""): r for r in _read_csv(resale_path)}
    acfg = cfg.get("arbitrage", {})
    exit_pct = float(acfg.get("exit_cost_pct", 8.0))
    min_spread = float(acfg.get("minimum_net_spread_eur", 8.0))
    min_roi = float(acfg.get("minimum_net_roi_pct", 25.0))
    for row in rows:
        if row.get("source_platform") != "CARDMARKET":
            continue
        src = decisions.get(str(row.get("id_product") or ""))
        if not src:
            row["arbitrage_signal"] = "NO_EDGE"
            continue
        try:
            landed = float(row["landed_eur"])
            reference = float(row["chosen_exit_reference_eur"])
        except (TypeError, ValueError):
            row["arbitrage_signal"] = "NO_EDGE"
            continue
        exit_after = round(reference * (1.0 - exit_pct / 100.0), 2)
        spread = round(exit_after - landed, 2)
        roi = round(spread / landed * 100.0, 1) if landed > 0 else 0.0
        row["estimated_exit_after_costs_eur"] = exit_after
        row["net_spread_eur"] = spread
        row["net_roi_pct"] = roi
        row["arbitrage_signal"] = (
            "POSSIBLE_ARBITRAGE"
            if src.get("resale_decision") == "RESELL_TEST" and spread >= min_spread and roi >= min_roi
            else "NO_EDGE"
        )
        row["notes"] = (
            "Existing Cardmarket-to-eBay resale evidence, rechecked using v0.7 "
            "exit-cost reserve and net ROI thresholds."
        )


def _write_rows(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ARBITRAGE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    cfg = load_config(ROOT / "config.yaml")
    db_path = resolve_path(cfg, cfg["paths"]["database"])
    output_dir = resolve_path(cfg, cfg["paths"]["output_dir"])
    watchlist = resolve_path(cfg, cfg["paths"]["gumtree_watchlist"])
    resale_path = output_dir / "resale_candidates.csv"
    gumtree_path = output_dir / "gumtree_candidates.csv"
    arbitrage_path = output_dir / "arbitrage_candidates.csv"

    conn = connect(db_path)
    gumtree_status = scan_gumtree(
        conn, cfg, watchlist, gumtree_path, today=date.today()
    )
    catalog_status = enrich_gumtree_catalog_matches(conn, gumtree_path)
    gumtree_status["catalog_match"] = catalog_status
    gumtree_status["exact_match_rows"] = int(gumtree_status.get("exact_match_rows") or 0) + int(
        catalog_status.get("new_exact_matches") or 0
    )

    fx = fetch_fx_rates(cfg)
    rows, arbitrage_status = build_arbitrage_report(
        conn, cfg, gumtree_path, resale_path, arbitrage_path, fx=fx, today=date.today()
    )
    _reconcile_cardmarket_net_edges(rows, resale_path, cfg)
    _write_rows(arbitrage_path, rows)
    arbitrage_status.update({
        "strong_arbitrage": sum(1 for r in rows if r["arbitrage_signal"] == "STRONG_ARBITRAGE"),
        "possible_arbitrage": sum(1 for r in rows if r["arbitrage_signal"] == "POSSIBLE_ARBITRAGE"),
        "verify_variant": sum(1 for r in rows if r["arbitrage_signal"] == "VERIFY_VARIANT"),
        "verify_condition_language": sum(1 for r in rows if r["arbitrage_signal"] == "VERIFY_CONDITION_LANGUAGE"),
    })
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
