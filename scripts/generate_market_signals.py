from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_scanner.config import load_config, resolve_path
from deal_scanner.db import connect
from deal_scanner.market_signals import generate_market_signals


def main() -> int:
    cfg = load_config(ROOT / "config.yaml")
    db_path = resolve_path(cfg, cfg["paths"]["database"])
    output_dir = resolve_path(cfg, cfg["paths"]["output_dir"])
    watchlist = resolve_path(cfg, cfg["paths"]["ebay_watchlist"])
    sold = resolve_path(cfg, cfg["paths"]["ebay_sold_evidence"])
    events = resolve_path(cfg, cfg["paths"]["market_events"])

    conn = connect(db_path)
    rows = generate_market_signals(
        conn, cfg, watchlist, sold, events, output_dir / "market_signals.csv", today=date.today()
    )
    summary = {
        "rows": len(rows),
        "high_confidence": sum(1 for r in rows if r.get("confidence") == "HIGH"),
        "accelerating": sum(1 for r in rows if r.get("signal_label") == "ACCELERATING"),
        "firming": sum(1 for r in rows if r.get("signal_label") == "FIRMING"),
        "pullback": sum(1 for r in rows if r.get("signal_label") == "PULLBACK"),
        "cooling": sum(1 for r in rows if r.get("signal_label") == "COOLING"),
        "note": "Event flags are contextual only; missing event flag means no matching event is recorded, not proof that no external catalyst exists.",
    }

    status_path = output_dir / "scanner_status.json"
    if status_path.exists():
        status = json.loads(status_path.read_text(encoding="utf-8"))
    else:
        status = {}
    status["version"] = str(cfg.get("version", status.get("version", "unknown")))
    status["market_signals"] = summary
    status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({"market_signals": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
