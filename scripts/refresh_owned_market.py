from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_scanner.cardmarket_live import ParseBotCardmarketClient, _extract_listing_rows, _listing_price
from deal_scanner.cardtrader import CardTraderClient, normalize_marketplace
from deal_scanner.config import load_config, resolve_path
from deal_scanner.db import blueprint_product_map_for_expansion, expansion_ids_for_products

OWNED_PATH = ROOT / "data" / "reference" / "owned_resale_cards.csv"
OUTPUT_PATH = ROOT / "dashboard" / "data" / "owned_market.json"


def read_owned() -> list[dict]:
    with OWNED_PATH.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def as_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "reverse", "reverse holo", "reverse_holo"}:
        return True
    if text in {"0", "false", "no", "n", "normal", "non-reverse", "non_reverse", "standard"}:
        return False
    return None


def nested_reverse_value(value):
    if isinstance(value, dict):
        for key, child in value.items():
            key_norm = str(key).lower().replace(" ", "_")
            if key_norm in {"pokemon_reverse", "reverse", "reverse_holo", "is_reverse", "is_reverse_holo"}:
                parsed = as_bool(child.get("value") if isinstance(child, dict) else child)
                if parsed is not None:
                    return parsed
        for child in value.values():
            parsed = nested_reverse_value(child)
            if parsed is not None:
                return parsed
    elif isinstance(value, list):
        for child in value:
            parsed = nested_reverse_value(child)
            if parsed is not None:
                return parsed
    return None


def ct_reverse_by_offer(payload) -> dict[int, bool | None]:
    result: dict[int, bool | None] = {}
    groups = []
    if isinstance(payload, dict):
        groups = [v for v in payload.values() if isinstance(v, list)]
    elif isinstance(payload, list):
        groups = [payload]
    for group in groups:
        for row in group:
            if not isinstance(row, dict):
                continue
            raw_id = row.get("id") or row.get("product_id") or row.get("productId")
            try:
                offer_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            result[offer_id] = nested_reverse_value(row.get("properties_hash") or row.get("properties") or row)
    return result


def matches_finish(requirement: str, reverse_value: bool | None) -> tuple[bool, bool]:
    """Return (comparable, finish_verified). UNIQUE_PRODUCT is exact by product identity."""
    req = (requirement or "").strip().upper()
    if req == "UNIQUE_PRODUCT":
        return True, True
    if req == "NON_REVERSE":
        return reverse_value is False, reverse_value is not None
    if req == "REVERSE":
        return reverse_value is True, reverse_value is not None
    return False, False


def ct_market(conn: sqlite3.Connection, cfg: dict, owned: list[dict]) -> dict[str, dict]:
    token = os.environ.get(str(cfg.get("cardtrader", {}).get("token_env") or "CARDTRADER_API_TOKEN"))
    if not token:
        return {str(r["id_product"]): {"status": "MISSING_CARDTRADER_TOKEN"} for r in owned}
    owned_ids = [int(r["id_product"]) for r in owned]
    owned_by_pid = {int(r["id_product"]): r for r in owned}
    client = CardTraderClient(
        cfg["sources"]["cardtrader_base_url"],
        token,
        other_delay=float(cfg["cardtrader"].get("other_delay_seconds", 0.08)),
        marketplace_delay=float(cfg["cardtrader"].get("marketplace_delay_seconds", 1.05)),
        timeout=int(cfg["cardtrader"].get("timeout_seconds", 60)),
    )
    offers_by_pid: dict[int, list[dict]] = {pid: [] for pid in owned_ids}
    finish_unknown_by_pid: dict[int, int] = {pid: 0 for pid in owned_ids}
    errors: dict[int, str] = {}
    for expansion_id in expansion_ids_for_products(conn, owned_ids):
        try:
            bpmap = blueprint_product_map_for_expansion(conn, expansion_id)
            payload = client.marketplace(expansion_id, language="en")
            reverse_map = ct_reverse_by_offer(payload)
            for offer in normalize_marketplace(payload, bpmap):
                pid = offer.get("id_product")
                if pid not in owned_by_pid:
                    continue
                cond = str(offer.get("condition") or "").strip().lower().replace("_", " ")
                lang = str(offer.get("language") or "").strip().lower()
                if lang not in {"en", "english"} or cond not in {"nm", "near mint"}:
                    continue
                if offer.get("graded") or offer.get("on_vacation") or offer.get("price_eur") in (None, 0):
                    continue
                reverse_value = reverse_map.get(int(offer["offer_id"]))
                comparable, finish_verified = matches_finish(owned_by_pid[pid].get("finish_requirement", ""), reverse_value)
                if not finish_verified and owned_by_pid[pid].get("finish_requirement") != "UNIQUE_PRODUCT":
                    finish_unknown_by_pid[pid] += 1
                if comparable:
                    offers_by_pid[pid].append(offer)
        except Exception as exc:
            for pid in owned_ids:
                errors.setdefault(pid, str(exc))

    result: dict[str, dict] = {}
    for pid in owned_ids:
        offers = sorted(offers_by_pid[pid], key=lambda x: float(x["price_eur"]))
        if offers:
            result[str(pid)] = {
                "status": "OK",
                "floor_eur": round(float(offers[0]["price_eur"]), 2),
                "visible_sellers": len({o.get("seller_id") for o in offers if o.get("seller_id") is not None}),
                "visible_units": sum(int(o.get("quantity") or 1) for o in offers),
                "finish_verified": True,
            }
        elif finish_unknown_by_pid[pid]:
            result[str(pid)] = {
                "status": "VERIFY_FINISH",
                "floor_eur": None,
                "visible_sellers": 0,
                "visible_units": 0,
                "finish_verified": False,
            }
        else:
            result[str(pid)] = {
                "status": "NO_COMPARABLE_EN_NM_ASK" if pid not in errors else "DEGRADED",
                "floor_eur": None,
                "visible_sellers": 0,
                "visible_units": 0,
                "finish_verified": owned_by_pid[pid].get("finish_requirement") == "UNIQUE_PRODUCT",
                "error": errors.get(pid),
            }
    return result


def cm_market(cfg: dict, owned: list[dict]) -> dict[str, dict]:
    live_cfg = cfg.get("cardmarket_live", {})
    api_key = os.environ.get(str(live_cfg.get("api_key_env") or "PARSE_API_KEY"))
    if not api_key:
        return {str(r["id_product"]): {"status": "MISSING_CARDMARKET_LIVE_KEY"} for r in owned}

    # Preserve provider pacing but avoid an unnecessary sleep after the final request.
    local_cfg = deepcopy(cfg)
    delay = float(local_cfg.get("cardmarket_live", {}).get("request_delay_seconds", 12.5))
    local_cfg.setdefault("cardmarket_live", {})["request_delay_seconds"] = 0
    client = ParseBotCardmarketClient(local_cfg, api_key)
    result: dict[str, dict] = {}

    for index, card in enumerate(owned):
        pid = int(card["id_product"])
        try:
            payload = client.listings(pid)
            rows = _extract_listing_rows(payload)
            prices = []
            finish_unknown = 0
            for row in rows:
                price = _listing_price(row)
                if price is None or price <= 0:
                    continue
                reverse_value = nested_reverse_value(row)
                comparable, finish_verified = matches_finish(card.get("finish_requirement", ""), reverse_value)
                if not finish_verified and card.get("finish_requirement") != "UNIQUE_PRODUCT":
                    finish_unknown += 1
                if comparable:
                    prices.append(float(price))
            if prices:
                prices.sort()
                result[str(pid)] = {
                    "status": "OK",
                    "floor_eur": round(prices[0], 2),
                    "visible_offer_rows": len(prices),
                    "finish_verified": True,
                }
            elif finish_unknown:
                result[str(pid)] = {
                    "status": "VERIFY_FINISH",
                    "floor_eur": None,
                    "visible_offer_rows": 0,
                    "finish_verified": False,
                }
            else:
                result[str(pid)] = {
                    "status": "NO_COMPARABLE_EN_NM_ASK",
                    "floor_eur": None,
                    "visible_offer_rows": 0,
                    "finish_verified": card.get("finish_requirement") == "UNIQUE_PRODUCT",
                }
        except Exception as exc:
            result[str(pid)] = {
                "status": "DEGRADED",
                "floor_eur": None,
                "visible_offer_rows": 0,
                "finish_verified": False,
                "error": str(exc),
            }
        if delay > 0 and index < len(owned) - 1:
            time.sleep(delay)
    return result


def main() -> int:
    cfg = load_config(ROOT / "config.yaml")
    db_path = resolve_path(cfg, cfg["paths"]["database"])
    if not db_path.exists():
        raise FileNotFoundError(f"Scanner DB not found: {db_path}")
    owned = read_owned()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ct = ct_market(conn, cfg, owned)
    conn.close()
    cm = cm_market(cfg, owned)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    cards = []
    for card in owned:
        pid = str(card["id_product"])
        cards.append({
            **card,
            "item_paid_eur": float(card["item_paid_eur"]),
            "allocated_shipping_eur": float(card["allocated_shipping_eur"]),
            "landed_cost_eur": float(card["landed_cost_eur"]),
            "cardmarket": cm.get(pid, {"status": "NOT_QUERIED"}),
            "cardtrader": ct.get(pid, {"status": "NOT_QUERIED"}),
        })
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({
            "schema_version": 1,
            "generated_at_utc": now,
            "purpose": "owned-card decision support; asks are competition references, not realised exits",
            "cards": cards,
        }, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} with {len(cards)} owned cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
