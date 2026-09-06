from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

LISTINGS = [
    {"listing_id": "40758551", "seller": "batch91", "title": "Pokemon Cards"},
    {"listing_id": "40926024", "seller": "batch91", "title": "Pokemon Cards"},
    {"listing_id": "40926025", "seller": "batch91", "title": "Pokemon Cards"},
    {"listing_id": "40758540", "seller": "batch91", "title": "Pokemon Cards"},
    {"listing_id": "36964449", "seller": "PokeDub", "title": "Pokemon Silver Tempest Complete Master set and Promos 1700Euro"},
    {"listing_id": "37253325", "seller": "PokeDub", "title": "Prismatic Evolutions Roaring Moon ex #162"},
    {"listing_id": "36411508", "seller": "PokeDub", "title": "Pokemon Scarlet & Violet Complete master set and all rare promos"},
    {"listing_id": "37724353", "seller": "PokeDub", "title": "Pokemon Black Star Promo Hisuian Decidueye V #SWSH238"},
    {"listing_id": "36200911", "seller": "PokeDub", "title": "Pokemon Prismatic Evolutions Larrys Skill Pokeball #115"},
    {"listing_id": "36200874", "seller": "PokeDub", "title": "Pokemon Prismatic Evolutions Max Rod #116"},
    {"listing_id": "38889838", "seller": "mini4real2k6", "title": "Pokemon Card Bundles"},
    {"listing_id": "36342137", "seller": "mini4real2k6", "title": "Sword & Shield - Vivid Voltage Pokemon cards bulk"},
    {"listing_id": "39273643", "seller": "mini4real2k6", "title": "Bulk Pokemon Energy Cards"},
]

OUT_DIR = Path("output/search_index_probe")
TIMEOUT = 60
GENERIC_TITLES = {"pokemon cards", "pokemon", "cards"}


def extract_prices(text: str) -> list[str]:
    return sorted(set(re.findall(r"€\s*([0-9]+(?:[.,][0-9]{1,2})?)", text or "")))


def query_variants(listing: dict) -> list[tuple[str, str]]:
    title = listing["title"].strip()
    seller = listing["seller"].strip()
    listing_id = listing["listing_id"].strip()
    variants: list[tuple[str, str]] = []
    if title.lower() not in GENERIC_TITLES:
        variants.append(("exact_title_seller", f'"{title}" "{seller}"'))
    variants.append(("id_seller_title", f'"{listing_id}" "{seller}" "{title}"'))
    variants.append(("id_seller", f'"{listing_id}" "{seller}"'))
    return variants


def firecrawl_search(api_key: str, query: str) -> list[dict]:
    r = requests.post(
        "https://api.firecrawl.dev/v2/search",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "limit": 10,
            "sources": ["web"],
            "includeDomains": ["adverts.ie"],
            "country": "IE",
            "timeout": 60000,
        },
        timeout=TIMEOUT + 10,
    )
    r.raise_for_status()
    payload = r.json()
    return ((payload.get("data") or {}).get("web") or []) if isinstance(payload, dict) else []


def normalize_result(item: dict, listing: dict) -> dict:
    url = str(item.get("url") or "")
    title = str(item.get("title") or "")
    description = str(item.get("description") or "")
    combined = f"{title} {description}"
    return {
        "url": url,
        "title": title,
        "description": description,
        "exact_listing_id_in_url": listing["listing_id"] in url,
        "listing_id_in_text": listing["listing_id"] in combined,
        "seller_in_text": listing["seller"].lower() in combined.lower(),
        "prices_seen_eur": extract_prices(combined),
        "offer_accepted_marker": bool(re.search(r"offer\s+accepted", combined, re.I)),
        "still_available_marker": bool(re.search(r"still\s+available", combined, re.I)),
        "sold_marker": bool(re.search(r"\bhas been sold\b|\bitem has been sold\b|\bsold\b", combined, re.I)),
    }


def query_firecrawl(api_key: str, listing: dict) -> dict:
    attempts = []
    all_results: list[dict] = []
    exact: list[dict] = []

    for query_type, query in query_variants(listing):
        web = firecrawl_search(api_key, query)
        normalized = [normalize_result(item, listing) for item in web]
        exact_here = [x for x in normalized if x["exact_listing_id_in_url"] or x["listing_id_in_text"]]
        attempts.append({
            "query_type": query_type,
            "query": query,
            "result_count": len(normalized),
            "exact_match_count": len(exact_here),
            "results": normalized,
        })
        all_results.extend(normalized)
        exact.extend(exact_here)
        if exact_here:
            break

    # Deduplicate exact hits by URL.
    deduped_exact = []
    seen_urls = set()
    for row in exact:
        key = row["url"]
        if key in seen_urls:
            continue
        seen_urls.add(key)
        deduped_exact.append(row)

    return {
        "attempts": attempts,
        "result_count": len(all_results),
        "exact_match_count": len(deduped_exact),
        "exact_matches": deduped_exact,
    }


def main() -> None:
    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("FIRECRAWL_API_KEY is required for this probe")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    rows = []
    for listing in LISTINGS:
        try:
            probe = query_firecrawl(api_key, listing)
            error = None
        except Exception as exc:
            probe = {"attempts": [], "result_count": 0, "exact_match_count": 0, "exact_matches": []}
            error = f"{type(exc).__name__}: {exc}"

        exact = probe["exact_matches"]
        results.append({"listing": listing, "probe": probe, "error": error})
        rows.append({
            "listing_id": listing["listing_id"],
            "seller": listing["seller"],
            "title": listing["title"],
            "queries_attempted": len(probe["attempts"]),
            "query_types": "|".join(a["query_type"] for a in probe["attempts"]),
            "search_results": probe["result_count"],
            "exact_matches": probe["exact_match_count"],
            "hit": bool(exact),
            "matched_urls": "|".join(x["url"] for x in exact),
            "prices_seen_eur": "|".join(sorted({p for x in exact for p in x["prices_seen_eur"]})),
            "offer_accepted_marker": any(x["offer_accepted_marker"] for x in exact),
            "still_available_marker": any(x["still_available_marker"] for x in exact),
            "sold_marker": any(x["sold_marker"] for x in exact),
            "error": error or "",
        })

    payload = {
        "tested_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "firecrawl_v2_search",
        "purpose": "Third-party search-index lookup only; does not request Adverts.ie directly.",
        "results": results,
        "summary": {
            "listings_tested": len(rows),
            "listings_with_exact_search_hit": sum(1 for row in rows if row["hit"]),
            "listings_with_errors": sum(1 for row in rows if row["error"]),
        },
    }
    (OUT_DIR / "search_index_probe.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    with (OUT_DIR / "search_index_probe.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps(payload["summary"], indent=2))
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
