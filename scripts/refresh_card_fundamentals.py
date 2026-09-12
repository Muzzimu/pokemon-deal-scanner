from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = ROOT / "dashboard" / "data" / "card_images.json"
OUTPUT_PATH = ROOT / "data" / "reference" / "card_fundamentals.csv"
BASE_URL = "https://api.tcgdex.net/v2/en"
FIELDS = [
    "id_product", "tcgdex_id", "name", "set_id", "set_name", "local_id",
    "release_date", "rarity", "illustrator", "category", "regulation_mark",
    "standard_legal", "expanded_legal", "variant_normal", "variant_holo",
    "variant_reverse", "variant_first_edition", "variant_wpromo", "source",
    "status", "last_checked_utc",
]


def clean(value):
    return "" if value is None else str(value)


def bool_text(value):
    if value is None:
        return ""
    return "1" if bool(value) else "0"


def load_existing() -> dict[str, dict]:
    if not OUTPUT_PATH.exists():
        return {}
    with OUTPUT_PATH.open(newline="", encoding="utf-8") as fh:
        return {str(row.get("id_product")): dict(row) for row in csv.DictReader(fh) if row.get("id_product")}


def fetch_json(session: requests.Session, path: str) -> dict:
    response = session.get(f"{BASE_URL}/{path.lstrip('/')}", timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("TCGdex payload is not an object")
    return payload


def main() -> int:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    cards = mapping.get("cards") or {}
    previous = load_existing()
    checked = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    session = requests.Session()
    session.headers.update({"User-Agent": "pokemon-deal-scanner/0.12 static-metadata"})
    set_cache: dict[str, dict] = {}
    rows: list[dict] = []

    for id_product, reference in sorted(cards.items(), key=lambda item: int(item[0])):
        tcgdex_id = str(reference.get("tcgdex_id") or "").strip()
        if not tcgdex_id:
            continue
        try:
            card = fetch_json(session, f"cards/{tcgdex_id}")
            if str(card.get("id") or "") != tcgdex_id:
                raise ValueError(f"exact id mismatch: expected {tcgdex_id}, received {card.get('id')}")
            set_obj = card.get("set") if isinstance(card.get("set"), dict) else {}
            set_id = str(set_obj.get("id") or "")
            set_detail = {}
            if set_id:
                if set_id not in set_cache:
                    set_cache[set_id] = fetch_json(session, f"sets/{set_id}")
                set_detail = set_cache[set_id]
            variants = card.get("variants") if isinstance(card.get("variants"), dict) else {}
            legal = card.get("legal") if isinstance(card.get("legal"), dict) else {}
            verified_name = str(reference.get("verified_name") or "").strip()
            returned_name = str(card.get("name") or "").strip()
            status = "OK" if not verified_name or returned_name.casefold() == verified_name.casefold() else "NAME_REVIEW"
            rows.append({
                "id_product": id_product,
                "tcgdex_id": tcgdex_id,
                "name": returned_name,
                "set_id": set_id,
                "set_name": set_detail.get("name") or set_obj.get("name") or reference.get("set_name"),
                "local_id": card.get("localId") or reference.get("number"),
                "release_date": set_detail.get("releaseDate") or set_obj.get("releaseDate"),
                "rarity": card.get("rarity"),
                "illustrator": card.get("illustrator"),
                "category": card.get("category"),
                "regulation_mark": card.get("regulationMark"),
                "standard_legal": bool_text(legal.get("standard")),
                "expanded_legal": bool_text(legal.get("expanded")),
                "variant_normal": bool_text(variants.get("normal")),
                "variant_holo": bool_text(variants.get("holo")),
                "variant_reverse": bool_text(variants.get("reverse")),
                "variant_first_edition": bool_text(variants.get("firstEdition")),
                "variant_wpromo": bool_text(variants.get("wPromo")),
                "source": "TCGDEX_V2_EXACT",
                "status": status,
                "last_checked_utc": checked,
            })
        except Exception as exc:
            old = dict(previous.get(str(id_product)) or {})
            if old:
                old["status"] = f"STALE_AFTER_{type(exc).__name__.upper()}"
                old["last_checked_utc"] = checked
                rows.append(old)
            else:
                rows.append({
                    "id_product": id_product,
                    "tcgdex_id": tcgdex_id,
                    "name": reference.get("verified_name"),
                    "set_name": reference.get("set_name"),
                    "local_id": reference.get("number"),
                    "source": "TCGDEX_V2_EXACT",
                    "status": f"ERROR_{type(exc).__name__.upper()}",
                    "last_checked_utc": checked,
                })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows([{field: clean(row.get(field)) for field in FIELDS} for row in rows])
    ok = sum(str(row.get("status")) in {"OK", "NAME_REVIEW"} for row in rows)
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} with {len(rows)} exact mappings ({ok} fresh)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
