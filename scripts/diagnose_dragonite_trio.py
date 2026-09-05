from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import requests

BASE_URL = "https://api.cardtrader.com/api/v2"
DB = Path("db/pokemon_deal_scanner.sqlite")
OUT = Path("output/dragonite_trio_test.json")

CARDS = {
    869763: "Mega Dragonite ex (ASC 152)",
    665676: "Dragonite VSTAR (PGO 050)",
    725239: "Dragonite ex (OBF 159)",
}


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
    }


def main() -> int:
    token = os.environ.get("CARDTRADER_API_TOKEN")
    if not token:
        raise SystemExit("CARDTRADER_API_TOKEN is missing")
    if not DB.exists():
        raise SystemExit(f"Database not found: {DB}")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    results = []

    for cm_id, label in CARDS.items():
        product = conn.execute(
            "SELECT id_product,name,expansion_name,number FROM products WHERE id_product=?",
            (cm_id,),
        ).fetchone()
        mappings = conn.execute(
            """
            SELECT m.blueprint_id,b.expansion_id,b.expansion_name,b.version,b.collector_number
            FROM cardtrader_blueprint_map m
            JOIN cardtrader_blueprints b ON b.blueprint_id=m.blueprint_id
            WHERE m.id_product=?
            ORDER BY m.blueprint_id
            """,
            (cm_id,),
        ).fetchall()

        blueprint_results = []
        for m in mappings:
            blueprint_id = int(m["blueprint_id"])
            r = requests.get(
                f"{BASE_URL}/marketplace/products",
                params={"blueprint_id": blueprint_id, "language": "en"},
                headers=headers,
                timeout=60,
            )
            r.raise_for_status()
            payload = r.json()
            offers = payload.get(str(blueprint_id), []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
            normalized = [_normalize_offer(p) for p in offers]
            en_nm = [
                x for x in normalized
                if str(x.get("language") or "").lower() in {"en", "english"}
                and str(x.get("condition") or "").lower().replace("_", " ") in {"near mint", "nm"}
                and not x["graded"] and not x["on_vacation"] and x["price"] is not None
            ]
            en_nm.sort(key=lambda x: x["price"])
            cheapest3 = en_nm[:3]
            if len(cheapest3) == 3:
                robust3 = sorted(x["price"] for x in cheapest3)[1]
            elif cheapest3:
                robust3 = cheapest3[len(cheapest3)//2]["price"]
            else:
                robust3 = None
            blueprint_results.append({
                "blueprint_id": blueprint_id,
                "expansion_id": m["expansion_id"],
                "expansion_name": m["expansion_name"],
                "version": m["version"],
                "collector_number": m["collector_number"],
                "visible_offer_rows": len(normalized),
                "english_nm_rows": len(en_nm),
                "english_nm_floor": en_nm[0]["price"] if en_nm else None,
                "english_nm_median_cheapest3": robust3,
                "english_nm_offers": en_nm[:10],
            })

        results.append({
            "cardmarket_id": cm_id,
            "label": label,
            "product": dict(product) if product else None,
            "mapping_count": len(mappings),
            "cardtrader": blueprint_results,
        })

    conn.close()
    payload = {"cards": results}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
