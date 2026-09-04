from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_demo_pipeline(tmp_path):
    config = (ROOT / "config.yaml").read_text(encoding="utf-8")
    config = config.replace("db/pokemon_deal_scanner.sqlite", str(tmp_path / "scanner.sqlite"))
    config = config.replace("output_dir: output", f"output_dir: {tmp_path / 'output'}")
    config = config.replace("raw_dir: data/raw/cardmarket", f"raw_dir: {tmp_path / 'raw'}")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(config, encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_daily.py"), "--demo", "--no-archive", "--config", str(cfg)], check=True)

    out = tmp_path / "output"
    assert (out / "cheap_ex.csv").exists()
    assert (out / "dragonite.csv").exists()
    assert (out / "top_flips.csv").exists()
    assert (out / "bundle_candidates.csv").exists()
    assert (out / "seller_baskets.csv").exists()
    assert (out / "cardmarket_sourcing.csv").exists()
    with (out / "cheap_ex.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows
    assert any(r["status"] in ("BUY_CT_EN_NM", "CHECK_CM_IRELAND_LANDED", "VALIDATE_EN_NM") for r in rows)
