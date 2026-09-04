from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import requests

BASE_URL = "https://api.cardtrader.com/api/v2"
BLUEPRINT_ID = 218021  # Dragonite V (Pokémon GO 076/078)
OUT = Path("output/pgo076_test.json")
DB = Path("db/pokemon_deal_scanner.sqlite")


def main() -> int:
    token = os.environ.get("CARDTRADER_API_TOKEN")
    if not token:
        raise SystemExit("CARDTRADER_API_TOKEN is missing")

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    r = requests.get(
        f"{BASE_URL}/marketplace/products",
        params={"blueprint_id": BLUEPRINT_ID, "language": "en"},
        headers=headers,
        timeout=60,
    )
    r.raise_for_status()
    payload = r.json()

    if isinstance(payload, dict):
        offers = payload.get(str(BLUEPRINT_ID), [])
    else:
        offers = payload if isinstance(payload, list) else []

    raw_expansion_id = None
    if offers and isinstance(offers[0].get("expansion"), dict):
        raw_expansion_id = offers[0]["expansion"].get("id")

    blueprint = None
    if raw_expansion_id is not None:
        br = requests.get(
            f"{BASE_URL}/blueprints/export",
            params={"expansion_id": raw_expansion_id},
            headers=headers,
            timeout=60,
        )
        br.raise_for_status()
        bp_payload = br.json()
        bp_rows = bp_payload if isinstance(bp_payload, list) else bp_payload.get("array", []) if isinstance(bp_payload, dict) else []
        blueprint = next((x for x in bp_rows if int(x.get("id", -1)) == BLUEPRINT_ID), None)

    normalized = []
    for p in offers:
        props = p.get("properties_hash") or p.get("properties") or {}
        price = p.get("price") or {}
        if isinstance(price, dict):
            cents = price.get("cents")
            currency = price.get("currency")
            price_value = None if cents is None else float(cents) / 100.0
        else:
            currency = None
            try:
                price_value = float(price) / 100.0
            except (TypeError, ValueError):
                price_value = None

        user = p.get("user") or p.get("seller") or {}
        language = (
            props.get("pokemon_language")
            or props.get("language")
            or props.get("mtg_language")
            or p.get("language")
        )
        condition = props.get("condition") or p.get("condition")
        normalized.append({
            "offer_id": p.get("id"),
            "price": price_value,
            "currency": currency,
            "condition": condition,
            "language": language,
            "quantity": p.get("quantity"),
            "seller": user.get("username") or user.get("name"),
            "seller_country": user.get("country_code") or user.get("country"),
            "seller_type": user.get("user_type"),
            "ct_zero": bool(user.get("can_sell_via_hub")),
            "graded": bool(p.get("graded")),
            "on_vacation": bool(p.get("on_vacation")),
            "description": p.get("description"),
        })

    en_nm = [
        x for x in normalized
        if str(x.get("language") or "").lower() in {"en", "english"}
        and str(x.get("condition") or "").lower().replace("_", " ") in {"near mint", "nm"}
        and not x["graded"] and not x["on_vacation"]
    ]
    en_nm.sort(key=lambda x: (x["price"] is None, x["price"] if x["price"] is not None else 10**9))

    cm_ids = []
    if blueprint:
        raw_ids = blueprint.get("card_market_ids") or blueprint.get("cardmarket_ids") or blueprint.get("mkm_ids") or []
        if isinstance(raw_ids, (int, str)):
            raw_ids = [raw_ids]
        for x in raw_ids:
            try:
                cm_ids.append(int(x))
            except (TypeError, ValueError):
                pass

    db_matches = []
    if DB.exists() and cm_ids:
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        q = ",".join("?" for _ in cm_ids)
        rows = conn.execute(
            f"SELECT id_product,name,category_name,expansion_name,number,last_seen_catalog FROM products WHERE id_product IN ({q})",
            cm_ids,
        ).fetchall()
        db_matches = [dict(row) for row in rows]
        conn.close()

    result = {
        "card": "Dragonite V (PGO 076/078)",
        "cardtrader_blueprint_id": BLUEPRINT_ID,
        "cardtrader_expansion_id": raw_expansion_id,
        "blueprint_keys": sorted(blueprint.keys()) if isinstance(blueprint, dict) else [],
        "blueprint_card_market_ids": cm_ids,
        "blueprint_raw": blueprint,
        "cardmarket_db_matches": db_matches,
        "visible_offer_rows": len(normalized),
        "english_nm_rows": len(en_nm),
        "english_nm_floor": en_nm[0]["price"] if en_nm else None,
        "currency": en_nm[0]["currency"] if en_nm else None,
        "english_nm_offers": en_nm[:10],
        "all_visible_offers": normalized[:25],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
