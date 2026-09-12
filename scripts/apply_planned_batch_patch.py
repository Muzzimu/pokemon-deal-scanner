from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- Feature 2: prospective ask-side depth / concentration diagnostics ---

path = ROOT / "scripts/refresh_owned_market.py"
text = path.read_text(encoding="utf-8")
text = text.replace(
    "from deal_scanner.cardmarket_live import ParseBotCardmarketClient, _extract_listing_rows, _listing_price, _summary\n",
    "from deal_scanner.cardmarket_live import (\n    ParseBotCardmarketClient, _extract_listing_rows, _listing_price, _summary, _seller_key, _quantity\n)\n",
    1,
)
if 'DEPTH_HISTORY_PATH = ROOT / "dashboard" / "data" / "owned_depth_history.csv"' not in text:
    text = text.replace(
        'USAGE_PATH = ROOT / "dashboard" / "data" / "provider_usage.csv"\n',
        'USAGE_PATH = ROOT / "dashboard" / "data" / "provider_usage.csv"\nDEPTH_HISTORY_PATH = ROOT / "dashboard" / "data" / "owned_depth_history.csv"\n',
        1,
    )

start = text.index("def ask_diagnostics(rows: list[dict], sample_size: int) -> dict:\n")
end = text.index("\n\ndef ct_market", start)
replacement = '''def ask_diagnostics(rows: list[dict], sample_size: int) -> dict:\n    """Return floor, robust floor and ask-side structure from already-fetched rows.\n\n    These are diagnostic-only market-structure measures. They do not create a BUY,\n    fair-value override or executable exit.\n    """\n    summary = _summary(rows, sample_size)\n    offers = []\n    for index, row in enumerate(rows):\n        price = _listing_price(row)\n        if price is None or float(price) <= 0:\n            continue\n        offers.append({\n            "price": float(price),\n            "seller": _seller_key(row, index),\n            "quantity": _quantity(row),\n        })\n    offers.sort(key=lambda r: r["price"])\n    prices = [r["price"] for r in offers]\n    n = min(max(1, sample_size), len(prices)) if prices else 0\n    sample = [round(value, 2) for value in prices[:n]]\n    floor = summary.get("floor")\n    robust = summary.get("robust")\n    spread_pct = None\n    if floor not in (None, 0) and robust is not None:\n        spread_pct = round((float(robust) / float(floor) - 1.0) * 100.0, 1)\n\n    def band_stats(multiplier: float) -> tuple[int, int]:\n        if not offers:\n            return 0, 0\n        ceiling = offers[0]["price"] * multiplier\n        selected = [r for r in offers if r["price"] <= ceiling + 1e-9]\n        return sum(int(r["quantity"]) for r in selected), len({r["seller"] for r in selected})\n\n    floor3_units, floor3_sellers = band_stats(1.03)\n    near10_units, near10_sellers = band_stats(1.10)\n    next_distinct_gap_pct = None\n    if offers:\n        base = offers[0]["price"]\n        for row in offers[1:]:\n            if row["price"] > base + 1e-9:\n                next_distinct_gap_pct = round((row["price"] / base - 1.0) * 100.0, 1)\n                break\n\n    seller_units: dict[str, int] = {}\n    for row in offers:\n        seller_units[row["seller"]] = seller_units.get(row["seller"], 0) + int(row["quantity"])\n    total_units = sum(seller_units.values())\n    shares = sorted((units / total_units for units in seller_units.values()), reverse=True) if total_units else []\n    top1 = round(shares[0] * 100.0, 1) if shares else None\n    top3 = round(sum(shares[:3]) * 100.0, 1) if shares else None\n    hhi = round(sum(share * share for share in shares) * 10000.0, 0) if shares else None\n\n    return {\n        **summary,\n        "robust_sample_size": n,\n        "ask_sample_eur": sample,\n        "floor_to_robust_spread_pct": spread_pct,\n        "floor_depth_3pct_units": floor3_units,\n        "floor_depth_3pct_sellers": floor3_sellers,\n        "near_floor_10pct_units": near10_units,\n        "near_floor_10pct_sellers": near10_sellers,\n        "next_distinct_ask_gap_pct": next_distinct_gap_pct,\n        "top1_seller_unit_share_pct": top1,\n        "top3_seller_unit_share_pct": top3,\n        "seller_hhi": hhi,\n    }\n\n\ndef append_depth_history(cards: list[dict], observed_at: str) -> None:\n    fields = [\n        "observed_at_utc", "id_product", "name", "provider", "status",\n        "floor_eur", "robust_floor_eur", "visible_sellers", "visible_units",\n        "floor_depth_3pct_units", "floor_depth_3pct_sellers",\n        "near_floor_10pct_units", "near_floor_10pct_sellers",\n        "next_distinct_ask_gap_pct", "top1_seller_unit_share_pct",\n        "top3_seller_unit_share_pct", "seller_hhi",\n    ]\n    existing = []\n    if DEPTH_HISTORY_PATH.exists():\n        with DEPTH_HISTORY_PATH.open(newline="", encoding="utf-8") as fh:\n            existing = [dict(row) for row in csv.DictReader(fh)]\n    keys = {(observed_at, str(card.get("id_product")), provider) for card in cards for provider in ("cardmarket", "cardtrader")}\n    existing = [\n        row for row in existing\n        if (row.get("observed_at_utc"), str(row.get("id_product")), row.get("provider")) not in keys\n    ]\n    for card in cards:\n        for provider in ("cardmarket", "cardtrader"):\n            source = card.get(provider) or {}\n            row = {\n                "observed_at_utc": observed_at,\n                "id_product": card.get("id_product"),\n                "name": card.get("name"),\n                "provider": provider.upper(),\n                "status": source.get("status"),\n            }\n            for field in fields[5:]:\n                row[field] = source.get(field)\n            existing.append(row)\n    existing.sort(key=lambda r: (r.get("observed_at_utc", ""), str(r.get("id_product", "")), r.get("provider", "")))\n    DEPTH_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)\n    with DEPTH_HISTORY_PATH.open("w", newline="", encoding="utf-8") as fh:\n        writer = csv.DictWriter(fh, fieldnames=fields)\n        writer.writeheader()\n        writer.writerows(existing)\n'''
text = text[:start] + replacement + text[end:]

# Add new diagnostics to OK source payloads after the existing finish_verified field.
needle = '                "finish_verified": True,\n'
extra = '''                "floor_depth_3pct_units": diag["floor_depth_3pct_units"],\n                "floor_depth_3pct_sellers": diag["floor_depth_3pct_sellers"],\n                "near_floor_10pct_units": diag["near_floor_10pct_units"],\n                "near_floor_10pct_sellers": diag["near_floor_10pct_sellers"],\n                "next_distinct_ask_gap_pct": diag["next_distinct_ask_gap_pct"],\n                "top1_seller_unit_share_pct": diag["top1_seller_unit_share_pct"],\n                "top3_seller_unit_share_pct": diag["top3_seller_unit_share_pct"],\n                "seller_hhi": diag["seller_hhi"],\n'''
# Both CardTrader and Cardmarket OK blocks have the same anchor.
if text.count('"floor_depth_3pct_units": diag["floor_depth_3pct_units"]') < 2:
    text = text.replace(needle, extra + needle, 2)

old = '''    OUTPUT_PATH.write_text(\n        json.dumps({\n            "schema_version": 2,\n'''
new = '''    append_depth_history(cards, now)\n    OUTPUT_PATH.write_text(\n        json.dumps({\n            "schema_version": 3,\n'''
if old in text:
    text = text.replace(old, new, 1)
text = text.replace(
    '            "robust_ask_note": "robust_floor_eur is the median of the cheapest comparable asks already fetched; diagnostic only",\n',
    '            "robust_ask_note": "robust_floor_eur is the median of the cheapest comparable asks already fetched; diagnostic only",\n            "depth_note": "ask-side depth/concentration fields are prospective diagnostics only and do not alter BUY/FV logic",\n',
    1,
)
path.write_text(text, encoding="utf-8")

# Seed history file if it does not exist.
history = ROOT / "dashboard/data/owned_depth_history.csv"
if not history.exists():
    history.write_text(
        "observed_at_utc,id_product,name,provider,status,floor_eur,robust_floor_eur,visible_sellers,visible_units,floor_depth_3pct_units,floor_depth_3pct_sellers,near_floor_10pct_units,near_floor_10pct_sellers,next_distinct_ask_gap_pct,top1_seller_unit_share_pct,top3_seller_unit_share_pct,seller_hhi\n",
        encoding="utf-8",
    )

# Dashboard: show current ask structure under the live pricing table.
path = ROOT / "dashboard/app.py"
text = path.read_text(encoding="utf-8")
anchor = '''def owned_result_summary(row: dict, landed: float | None) -> tuple[str, float | None, float | None]:\n'''
helper = '''def owned_structure_text(row: dict, source_name: str, label: str) -> str | None:\n    source = row.get(source_name) or {}\n    if not isinstance(source, dict) or str(source.get("status") or "").upper() != "OK":\n        return None\n    u3, s3 = as_int(source.get("floor_depth_3pct_units")), as_int(source.get("floor_depth_3pct_sellers"))\n    u10, s10 = as_int(source.get("near_floor_10pct_units")), as_int(source.get("near_floor_10pct_sellers"))\n    gap = as_float(source.get("next_distinct_ask_gap_pct"))\n    top1 = as_float(source.get("top1_seller_unit_share_pct"))\n    parts = []\n    if u3 is not None or s3 is not None:\n        parts.append(f"+3% floor {u3 if u3 is not None else '—'}u/{s3 if s3 is not None else '—'}s")\n    if u10 is not None or s10 is not None:\n        parts.append(f"+10% {u10 if u10 is not None else '—'}u/{s10 if s10 is not None else '—'}s")\n    if gap is not None:\n        parts.append(f"next distinct ask +{gap:.1f}%")\n    if top1 is not None:\n        parts.append(f"top seller {top1:.0f}% of units")\n    return f"{label}: " + " · ".join(parts) if parts else None\n\n\n'''
if 'def owned_structure_text(' not in text:
    text = text.replace(anchor, helper + anchor, 1)
old = '''    if samples:\n        st.caption(" · ".join(samples))\n'''
new = '''    if samples:\n        st.caption(" · ".join(samples))\n    structures = [\n        value for value in (\n            owned_structure_text(row, "cardmarket", "CM structure"),\n            owned_structure_text(row, "cardtrader", "CT structure"),\n        ) if value\n    ]\n    if structures:\n        st.caption(" | ".join(structures))\n'''
if old in text and 'CM structure' not in text:
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# Tests for deterministic depth diagnostics.
test = '''from scripts.refresh_owned_market import ask_diagnostics\n\n\ndef test_ask_diagnostics_structure():\n    rows = [\n        {"price_eur": 10.00, "seller_id": 1, "quantity": 2},\n        {"price_eur": 10.20, "seller_id": 2, "quantity": 1},\n        {"price_eur": 10.90, "seller_id": 1, "quantity": 2},\n        {"price_eur": 12.00, "seller_id": 3, "quantity": 5},\n    ]\n    out = ask_diagnostics(rows, 3)\n    assert out["floor_eur"] if "floor_eur" in out else out["floor"] == 10.0\n    assert out["floor_depth_3pct_units"] == 3\n    assert out["floor_depth_3pct_sellers"] == 2\n    assert out["near_floor_10pct_units"] == 5\n    assert out["near_floor_10pct_sellers"] == 2\n    assert out["next_distinct_ask_gap_pct"] == 2.0\n    assert out["top1_seller_unit_share_pct"] == 50.0\n'''
(ROOT / "tests/test_owned_depth_diagnostics.py").write_text(test, encoding="utf-8")

# Roadmap note: data collection starts prospectively, still diagnostic-only.
doc_path = ROOT / "docs/DASHBOARD.md"
doc = doc_path.read_text(encoding="utf-8")
note = '''\n## Ask-side structure diagnostics\n\nOwned-card CM/CT refreshes preserve ask-side structure from the same already-fetched exact EN/NM/finish-matched rows: depth within +3% and +10% of floor, next distinct ask gap, seller concentration and HHI. The append-only `dashboard/data/owned_depth_history.csv` starts prospective history that cannot be reconstructed reliably later. These fields are display/research diagnostics only; they do not change v0.12 BUY/FV/route logic.\n\n'''
if "## Ask-side structure diagnostics" not in doc:
    doc += note
    doc_path.write_text(doc, encoding="utf-8")

(ROOT / ".patch-message").write_text("Add prospective ask-side depth diagnostics\n", encoding="utf-8")
