from __future__ import annotations

import csv
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests


LISTINGS = [
    {
        "listing_id": "40758551",
        "title": "Pokemon Cards",
        "urls": [
            "http://www.adverts.ie/40758551",
            "https://www.adverts.ie/40758551",
            "https://www.adverts.ie/other-toys-games/pokemon-cards/40758551",
        ],
    },
    {
        "listing_id": "40926024",
        "title": "Pokemon Cards",
        "urls": [
            "https://www.adverts.ie/other-toys-games/pokemon-cards/40926024",
            "https://www.adverts.ie/40926024",
        ],
    },
    {
        "listing_id": "40926025",
        "title": "Pokemon Cards",
        "urls": [
            "https://www.adverts.ie/other-toys-games/pokemon-cards/40926025",
            "https://www.adverts.ie/40926025",
        ],
    },
]

OUT_DIR = Path("output/archive_probe")
USER_AGENT = "pokemon-deal-scanner archive research probe/0.1"
TIMEOUT = 25


def get_json(url: str, params: dict | None = None):
    r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def wayback_lookup(url: str) -> list[dict]:
    endpoint = "https://web.archive.org/cdx/search/cdx"
    params = {
        "url": url,
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "digest",
        "limit": "50",
    }
    # requests does not expand list values when a plain dict is inspected by some
    # intermediaries, so use tuples explicitly for repeated filter parameters.
    query = [
        ("url", url), ("output", "json"),
        ("fl", "timestamp,original,statuscode,mimetype,digest"),
        ("filter", "statuscode:200"), ("filter", "mimetype:text/html"),
        ("collapse", "digest"), ("limit", "50"),
    ]
    r = requests.get(endpoint, params=query, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not data or len(data) < 2:
        return []
    fields = data[0]
    return [dict(zip(fields, row)) for row in data[1:]]


def strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?>.*?</style>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return re.sub(r"\s+", " ", raw).strip()


def wayback_content_probe(capture: dict) -> dict:
    ts = str(capture.get("timestamp") or "")
    original = str(capture.get("original") or "")
    if not ts or not original:
        return {}
    replay = f"https://web.archive.org/web/{ts}id_/{original}"
    try:
        r = requests.get(replay, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        r.raise_for_status()
        raw = r.text
        title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
        page_title = strip_html(title_match.group(1)) if title_match else ""
        text = strip_html(raw)
        eur = sorted({m.group(1).replace(",", ".") for m in re.finditer(r"€\s*([0-9]+(?:[.,][0-9]{1,2})?)", text)})
        sold_marker = bool(re.search(r"\bSOLD\b|\bSold\b", text))
        return {
            "replay_url": replay,
            "http_status": r.status_code,
            "page_title": page_title,
            "eur_prices_seen": eur[:20],
            "sold_marker_seen": sold_marker,
            "listing_id_seen": str(re.search(r"\b(40758551|40926024|40926025)\b", text).group(1)) if re.search(r"\b(40758551|40926024|40926025)\b", text) else "",
            "text_sample": text[:1200],
        }
    except Exception as exc:  # archive services can be intermittently unavailable
        return {"replay_url": replay, "error": f"{type(exc).__name__}: {exc}"}


def commoncrawl_indexes(limit: int = 6) -> list[dict]:
    data = get_json("https://index.commoncrawl.org/collinfo.json")
    return data[:limit]


def commoncrawl_lookup(index_api: str, url: str) -> list[dict]:
    r = requests.get(
        index_api,
        params={"url": url, "output": "json"},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    if r.status_code == 404:
        return []
    r.raise_for_status()
    rows = []
    for line in r.text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def dedupe_records(records: list[dict], keys: tuple[str, ...]) -> list[dict]:
    seen = set()
    out = []
    for row in records:
        key = tuple(str(row.get(k) or "") for k in keys)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tested_at = datetime.now(timezone.utc).isoformat()
    cc_indexes = []
    cc_index_error = None
    try:
        cc_indexes = commoncrawl_indexes()
    except Exception as exc:
        cc_index_error = f"{type(exc).__name__}: {exc}"

    results = []
    flat_rows = []

    for listing in LISTINGS:
        wayback = []
        wayback_errors = []
        for url in listing["urls"]:
            try:
                hits = wayback_lookup(url)
                for hit in hits:
                    hit["queried_url"] = url
                    wayback.append(hit)
            except Exception as exc:
                wayback_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        wayback = dedupe_records(wayback, ("timestamp", "original", "digest"))
        wayback.sort(key=lambda x: str(x.get("timestamp") or ""))

        content_probe = {}
        if wayback:
            # Test the newest unique capture, because sold-state evidence is most
            # likely to appear in a late snapshot.
            content_probe = wayback_content_probe(wayback[-1])

        cc_hits = []
        cc_errors = []
        for idx in cc_indexes:
            api = idx.get("cdx-api")
            idx_id = idx.get("id")
            if not api:
                continue
            for url in listing["urls"]:
                try:
                    hits = commoncrawl_lookup(api, url)
                    for hit in hits:
                        hit["queried_url"] = url
                        hit["index_id"] = idx_id
                        cc_hits.append(hit)
                except Exception as exc:
                    cc_errors.append({"index_id": idx_id, "url": url, "error": f"{type(exc).__name__}: {exc}"})
        cc_hits = dedupe_records(cc_hits, ("index_id", "timestamp", "url", "digest"))
        cc_hits.sort(key=lambda x: (str(x.get("timestamp") or ""), str(x.get("index_id") or "")))

        result = {
            "listing_id": listing["listing_id"],
            "title": listing["title"],
            "urls_tested": listing["urls"],
            "wayback": {
                "capture_count": len(wayback),
                "first_capture": wayback[0].get("timestamp") if wayback else None,
                "last_capture": wayback[-1].get("timestamp") if wayback else None,
                "captures": wayback,
                "errors": wayback_errors,
                "latest_content_probe": content_probe,
            },
            "commoncrawl": {
                "indexes_checked": [x.get("id") for x in cc_indexes],
                "capture_count": len(cc_hits),
                "first_capture": cc_hits[0].get("timestamp") if cc_hits else None,
                "last_capture": cc_hits[-1].get("timestamp") if cc_hits else None,
                "captures": cc_hits,
                "errors": cc_errors,
            },
            "archive_hit": bool(wayback or cc_hits),
        }
        results.append(result)

        flat_rows.append({
            "listing_id": listing["listing_id"],
            "wayback_captures": len(wayback),
            "wayback_first": wayback[0].get("timestamp") if wayback else "",
            "wayback_last": wayback[-1].get("timestamp") if wayback else "",
            "wayback_latest_title": content_probe.get("page_title", ""),
            "wayback_latest_sold_marker": content_probe.get("sold_marker_seen", ""),
            "wayback_latest_prices": "|".join(content_probe.get("eur_prices_seen", [])),
            "commoncrawl_captures": len(cc_hits),
            "commoncrawl_first": cc_hits[0].get("timestamp") if cc_hits else "",
            "commoncrawl_last": cc_hits[-1].get("timestamp") if cc_hits else "",
            "archive_hit": bool(wayback or cc_hits),
        })

    payload = {
        "tested_at_utc": tested_at,
        "purpose": "Known-URL third-party archive hit-rate test; does not request Adverts.ie directly.",
        "commoncrawl_index_error": cc_index_error,
        "listings": results,
        "summary": {
            "listings_tested": len(results),
            "listings_with_any_archive_hit": sum(1 for r in results if r["archive_hit"]),
            "listings_with_wayback_hit": sum(1 for r in results if r["wayback"]["capture_count"] > 0),
            "listings_with_commoncrawl_hit": sum(1 for r in results if r["commoncrawl"]["capture_count"] > 0),
        },
    }

    (OUT_DIR / "archive_probe.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    with (OUT_DIR / "archive_probe.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat_rows[0].keys()))
        writer.writeheader()
        writer.writerows(flat_rows)

    print(json.dumps(payload["summary"], indent=2))
    for row in flat_rows:
        print(row)


if __name__ == "__main__":
    main()
