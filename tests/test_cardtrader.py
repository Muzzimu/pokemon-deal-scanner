from __future__ import annotations

import json
from pathlib import Path

from deal_scanner.cardtrader import blueprint_rows, near_mint_english, normalize_marketplace


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"


def test_cardtrader_nm_filter_ignores_sp():
    bps = blueprint_rows(json.loads((FIX / "cardtrader_blueprints_demo.json").read_text(encoding="utf-8")))
    bpmap = {}
    for bp in bps:
        for cmid in bp.get("card_market_ids", []):
            bpmap.setdefault(int(bp["id"]), []).append(int(cmid))
    payload = json.loads((FIX / "cardtrader_marketplace_demo.json").read_text(encoding="utf-8"))
    offers = normalize_marketplace(payload, bpmap)
    nm = near_mint_english(offers)
    stunfisk = [o for o in nm if o.get("id_product") == 900005]
    assert stunfisk
    assert min(o["price_eur"] for o in stunfisk) == 0.29
    # The fixture contains a €0.18 SP copy that must not be treated as NM.
    assert any(o["price_eur"] == 0.18 and o["condition"] == "Slightly Played" for o in offers)


def test_normalized_prices_are_euros():
    payload = json.loads((FIX / "cardtrader_marketplace_demo.json").read_text(encoding="utf-8"))
    offers = normalize_marketplace(payload, {500001: [900001]})
    zeraora = [o for o in offers if o["blueprint_id"] == 500001]
    assert zeraora
    assert min(o["price_eur"] for o in zeraora) == 0.12
