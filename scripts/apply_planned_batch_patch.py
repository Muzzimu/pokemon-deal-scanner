from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- Feature 3: exact static card-fundamentals cache ---

script = '''from __future__ import annotations

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
'''
(ROOT / "scripts/refresh_card_fundamentals.py").write_text(script, encoding="utf-8")

cache = ROOT / "data/reference/card_fundamentals.csv"
if not cache.exists():
    cache.write_text(
        "id_product,tcgdex_id,name,set_id,set_name,local_id,release_date,rarity,illustrator,category,regulation_mark,standard_legal,expanded_legal,variant_normal,variant_holo,variant_reverse,variant_first_edition,variant_wpromo,source,status,last_checked_utc\n",
        encoding="utf-8",
    )

# Dashboard: exact metadata enriches tracked/owned/detail rows with prefixed fields.
path = ROOT / "dashboard/app.py"
text = path.read_text(encoding="utf-8")
const_anchor = 'PROVIDER_LIMITS_PATH = ROOT / "data" / "reference" / "provider_limits.csv"\n'
if 'CARD_FUNDAMENTALS_PATH' not in text:
    text = text.replace(
        const_anchor,
        const_anchor + 'CARD_FUNDAMENTALS_PATH = ROOT / "data" / "reference" / "card_fundamentals.csv"\n',
        1,
    )
load_anchor = 'provider_limits = read_csv(PROVIDER_LIMITS_PATH)\n'
if 'card_fundamental_rows = read_csv(CARD_FUNDAMENTALS_PATH)' not in text:
    text = text.replace(
        load_anchor,
        load_anchor + 'card_fundamental_rows = read_csv(CARD_FUNDAMENTALS_PATH)\ncard_fundamentals_by_pid = {str(r.get("id_product")): r for r in card_fundamental_rows if r.get("id_product")}\n',
        1,
    )

# Merge static metadata before owned live-market enrichment. Prefix to avoid replacing scanner evidence.
anchor = 'enriched_tracked = []\nfor source in tracked:\n    row = dict(source)\n'
replacement = '''enriched_tracked = []\nfor source in tracked:\n    row = dict(source)\n    fundamentals = card_fundamentals_by_pid.get(str(row.get("id_product")))\n    if fundamentals:\n        for field, value in fundamentals.items():\n            if field in {"id_product", "name"} or value in (None, ""):\n                continue\n            row[f"fund_{field}"] = value\n'''
if anchor in text and 'row[f"fund_{field}"]' not in text:
    text = text.replace(anchor, replacement, 1)

# Also enrich routes/discovery/card-detail universe by exact Cardmarket id.
marker = 'tracked = enriched_tracked\n\nfor key in ("t7", "t7_cards", "t30", "t30_cards"):'
extra = '''tracked = enriched_tracked\nfor collection in (routes, discovery, predictions):\n    for row in collection:\n        fundamentals = card_fundamentals_by_pid.get(str(row.get("id_product")))\n        if not fundamentals:\n            continue\n        for field, value in fundamentals.items():\n            if field in {"id_product", "name"} or value in (None, ""):\n                continue\n            row.setdefault(f"fund_{field}", value)\n\nfor key in ("t7", "t7_cards", "t30", "t30_cards"):'''
if marker in text:
    text = text.replace(marker, extra, 1)

# Compact display helper and show it near the top of owned position.
anchor = 'def render_owned_position(row: dict, routed: bool) -> None:\n'
helper = '''def fundamentals_text(row: dict) -> str | None:\n    parts = []\n    rarity = clean_text(row.get("fund_rarity"))\n    illustrator = clean_text(row.get("fund_illustrator"))\n    release_date = clean_text(row.get("fund_release_date"))\n    regulation = clean_text(row.get("fund_regulation_mark"))\n    standard = clean_text(row.get("fund_standard_legal"))\n    if rarity:\n        parts.append(rarity)\n    if illustrator:\n        parts.append(f"artist {illustrator}")\n    if release_date:\n        parts.append(f"released {release_date}")\n    if regulation:\n        parts.append(f"regulation {regulation}")\n    if standard in {"0", "1"}:\n        parts.append("Standard legal" if standard == "1" else "not Standard legal")\n    return " · ".join(parts) if parts else None\n\n\n'''
if 'def fundamentals_text(' not in text:
    text = text.replace(anchor, helper + anchor, 1)
old = '''    st.markdown(f"**What it means:** {summary}")\n\n    st.markdown("**Your position**")\n'''
new = '''    st.markdown(f"**What it means:** {summary}")\n    static_context = fundamentals_text(row)\n    if static_context:\n        st.caption(f"Static card context: {static_context}")\n\n    st.markdown("**Your position**")\n'''
if old in text:
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# Unit-test the exact-cache contract without network.
test = '''from pathlib import Path\n\n\ndef test_fundamentals_script_uses_exact_tcgdex_ids():\n    text = Path("scripts/refresh_card_fundamentals.py").read_text(encoding="utf-8")\n    assert 'cards/{tcgdex_id}' in text\n    assert 'str(card.get("id") or "") != tcgdex_id' in text\n    assert "fuzzy" not in text.lower()\n\n\ndef test_fundamentals_cache_has_identity_columns():\n    header = Path("data/reference/card_fundamentals.csv").read_text(encoding="utf-8").splitlines()[0]\n    for field in ("id_product", "tcgdex_id", "release_date", "rarity", "illustrator", "status"):\n        assert field in header.split(",")\n'''
(ROOT / "tests/test_card_fundamentals.py").write_text(test, encoding="utf-8")

doc_path = ROOT / "docs/DASHBOARD.md"
doc = doc_path.read_text(encoding="utf-8")
note = '''\n## Static card fundamentals\n\nStatic metadata may enrich the dashboard only through the explicit Cardmarket-product → exact TCGdex ID mapping already used for artwork. Cache release date, rarity/treatment metadata, illustrator, regulation mark, legal flags and variant availability in `data/reference/card_fundamentals.csv`. Never fuzzy-match metadata. This layer is context/research only and does not alter v0.12 fair value, BUY gates or route scoring. Refresh when exact mappings change or manually; it does not need a daily polling cadence.\n\n'''
if "## Static card fundamentals" not in doc:
    doc += note
    doc_path.write_text(doc, encoding="utf-8")

(ROOT / ".patch-message").write_text("Add exact static card fundamentals cache\n", encoding="utf-8")
