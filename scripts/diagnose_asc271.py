from __future__ import annotations

import json
import os
from statistics import median

import requests

BASE_URL = "https://api.cardtrader.com/api/v2"
EXPANSION_ID = 4400  # Ascended Heroes
TARGET_VERSION = "271/217"


def _rows(payload):
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("array", "data", "results", "blueprints"):
            if isinstance(payload.get(key), list):
                return [x for x in payload[key] if isinstance(x, dict)]
    return []


def _normalize_offer(p: dict) -> dict:
    props = p.get("properties_hash") or p.get("properties") or {}
    price = p.get("price") or {}
    if isinstance(price, dict):
        cents = price.get("cents")
        currency = price.get("currency")
        value = None if cents is None else float(cents) / 100.0
    else:
        currency = None
        try:
            value = float(price) / 100.0
        except (TypeError, ValueError):
            value = None
    user = p.get("user") or p.get("seller") or {}
    return {
        "offer_id": p.get("id"),
        "price": value,
        "currency": currency,
        "condition": props.get("condition") or p.get("condition"),
        "language": props.get("pokemon_language") or props.get("language") or p.get("language"),
        "quantity": p.get("quantity"),
        "seller": user.get("username") or user.get("name"),
        "seller_country": user.get("country_code") or user.get("country"),
        "seller_type": user.get("user_type"),
        "ct_zero": bool(user.get("can_sell_via_hub")),
        "graded": bool(p.get("graded")),
        "on_vacation": bool(p.get("on_vacation")),
        "first_edition": props.get("first_edition"),
    }


def main() -> int:
    token = os.environ.get("CARDTRADER_API_TOKEN")
    if not token:
        raise SystemExit("CARDTRADER_API_TOKEN is missing")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    r = requests.get(
        f"{BASE_URL}/blueprints/export",
        params={"expansion_id": EXPANSION_ID},
        headers=headers,
        timeout=60,
    )
    r.raise_for_status()
    blueprints = _rows(r.json())
    matches = []
    for bp in blueprints:
        name = str(bp.get("name") or "")
        version = str(bp.get("version") or "")
        fixed = bp.get("fixed_properties") or {}
        collector = str(fixed.get("collector_number") or bp.get("collector_number") or "")
        if "dragonite" in name.lower() and (TARGET_VERSION in version or collector == "271"):
            matches.append(bp)

    results = []
    for bp in matches:
        bid = int(bp["id"])
        r = requests.get(
            f"{BASE_URL}/marketplace/products",
            params={"blueprint_id": bid, "language": "en"},
            headers=headers,
            timeout=60,
        )
        r.raise_for_status()
        payload = r.json()
        offers = payload.get(str(bid), []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
        normalized = [_normalize_offer(p) for p in offers]
        en_nm = [
            x for x in normalized
            if str(x.get("language") or "").lower() in {"en", "english"}
            and str(x.get("condition") or "").lower().replace("_", " ") in {"near mint", "nm"}
            and not x["graded"] and not x["on_vacation"] and x["price"] is not None
        ]
        en_nm.sort(key=lambda x: x["price"])
        cheapest3 = en_nm[:3]
        results.append({
            "blueprint_id": bid,
            "name": bp.get("name"),
            "version": bp.get("version"),
            "card_market_ids": bp.get("card_market_ids"),
            "fixed_properties": bp.get("fixed_properties"),
            "visible_offer_rows": len(normalized),
            "english_nm_rows": len(en_nm),
            "english_nm_floor": en_nm[0]["price"] if en_nm else None,
            "english_nm_median_cheapest3": median([x["price"] for x in cheapest3]) if cheapest3 else None,
            "english_nm_offers": en_nm[:15],
        })

    out = {
        "target": "Mega Dragonite ex (ASC 271/217)",
        "expansion_id": EXPANSION_ID,
        "blueprint_matches": len(matches),
        "results": results,
    }
    os.makedirs("output", exist_ok=True)
    with open("output/asc271_test.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
