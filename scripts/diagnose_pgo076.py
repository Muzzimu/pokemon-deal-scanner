from __future__ import annotations

import json
import os
from pathlib import Path

import requests

BASE_URL = "https://api.cardtrader.com/api/v2"
BLUEPRINT_ID = 218021  # Dragonite V (Pokémon GO 076/078)
OUT = Path("output/pgo076_test.json")


def main() -> int:
    token = os.environ.get("CARDTRADER_API_TOKEN")
    if not token:
        raise SystemExit("CARDTRADER_API_TOKEN is missing")

    r = requests.get(
        f"{BASE_URL}/marketplace/products",
        params={"blueprint_id": BLUEPRINT_ID, "language": "en"},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    payload = r.json()

    if isinstance(payload, dict):
        offers = payload.get(str(BLUEPRINT_ID), [])
    else:
        offers = payload if isinstance(payload, list) else []

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

    result = {
        "card": "Dragonite V (PGO 076/078)",
        "cardtrader_blueprint_id": BLUEPRINT_ID,
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
