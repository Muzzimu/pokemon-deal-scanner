from __future__ import annotations

import csv
import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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
USER_AGENT = "pokemon-deal-scanner archive research probe/0.2"
TIMEOUT = (8, 18)


def session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": USER_AGENT})
    return s


HTTP = session()


def get_json(url: str, params: dict | None = None):
    r = HTTP.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def wayback_availability(url: str) -> dict:
    """Cheap Wayback check; independent of the heavier CDX endpoint."""
    data = get_json("https://archive.org/wayback/available", params={"url": url})
    closest = (data.get("archived_snapshots") or {}).get("closest") or {}
    return {
        "available": bool(closest.get("available")),
        "timestamp": closest.get("timestamp"),
        "status": closest.get("status"),
        "snapshot_url": closest.get("url"),
        "queried_url": url,
    }


def wayback_lookup(url: str) -> list[dict]:
    endpoint = "https://web.archive.org/cdx/search/cdx"
    query = [
        ("url", url), ("output", "json"),
        ("fl", "timestamp,original,statuscode,mimetype,digest"),
        ("filter", "statuscode:200"), ("filter", "mimetype:text/html"),
        ("collapse", "digest"), ("limit", "50"),
    ]
    r = HTTP.get(endpoint, params=query, timeout=TIMEOUT)
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


def archived_content_probe(replay_url: str) -> dict:
    if not replay_url:
        return {}
    try:
        r = HTTP.get(replay_url, timeout=TIMEOUT)
        r.raise_for_status()
        raw = r.text
        title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
        page_title = strip_html(title_match.group(1)) if title_match else ""
        text = strip_html(raw)
        eur = sorted({m.group(1).replace(",", ".") for m in re.finditer(r"€\s*([0-9]+(?:[.,][0-9]{1,2})?)", text)})
        sold_marker = bool(re.search(r"\bSOLD\b|\bSold\b", text))
        id_match = re.search(r"\b(40758551|40926024|40926025)\b", text)
        return {
            "replay_url": replay_url,
            "http_status": r.status_code,
            "page_title": page_title,
            "eur_prices_seen": eur[:20],
            "sold_marker_seen": sold_marker,
            "listing_id_seen": id_match.group(1) if id_match else "",
            "text_sample": text[:1200],
        }
    except Exception as exc:
        return {"replay_url": replay_url, "error": f"{type(exc).__name__}: {exc}"}


def commoncrawl_indexes(limit: int = 3) -> list[dict]:
    data = get_json("https://index.commoncrawl.org/collinfo.json")
    return data[:limit]


def commoncrawl_lookup(index_api: str, url: str) -> list[dict]:
    r = HTTP.get(index_api, params={"url": url, "output": "json"}, timeout=TIMEOUT)
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


def arquivo_lookup(url: str) -> list[dict]:
    """Exact-URL Memento TimeMap lookup in the independent Arquivo.pt archive."""
    endpoint = "https://arquivo.pt/wayback/timemap/json/" + quote(url, safe=":/?=&%")
    r = HTTP.get(endpoint, timeout=TIMEOUT)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    rows = []
    # Arquivo.pt documents this as NDJSON. Be tolerant of a JSON object/array too.
    text = r.text.strip()
    if not text:
        return []
    try:
        parsed = r.json()
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict):
            # Some Memento implementations wrap captures under mementos/list.
            candidates = parsed.get("mementos") or parsed.get("list") or []
            if isinstance(candidates, list):
                return [x for x in candidates if isinstance(x, dict)]
            return [parsed]
    except (ValueError, json.JSONDecodeError):
        pass
    for line in text.splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
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

    try:
        cc_indexes = commoncrawl_indexes()
        cc_index_error = None
    except Exception as exc:
        cc_indexes = []
        cc_index_error = f"{type(exc).__name__}: {exc}"

    results = []
    flat_rows = []

    for listing in LISTINGS:
        availability = []
        availability_errors = []
        wayback = []
        wayback_errors = []
        arquivo = []
        arquivo_errors = []

        for url in listing["urls"]:
            try:
                availability.append(wayback_availability(url))
            except Exception as exc:
                availability_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
            try:
                hits = wayback_lookup(url)
                for hit in hits:
                    hit["queried_url"] = url
                    wayback.append(hit)
            except Exception as exc:
                wayback_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
            try:
                hits = arquivo_lookup(url)
                for hit in hits:
                    hit["queried_url"] = url
                    arquivo.append(hit)
            except Exception as exc:
                arquivo_errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})

        wayback = dedupe_records(wayback, ("timestamp", "original", "digest"))
        wayback.sort(key=lambda x: str(x.get("timestamp") or ""))
        arquivo = dedupe_records(arquivo, ("timestamp", "url", "uri"))

        # If CDX is flaky but Availability finds a snapshot, still attempt content.
        replay_url = ""
        available_rows = [x for x in availability if x.get("available") and x.get("snapshot_url")]
        if available_rows:
            replay_url = str(available_rows[-1]["snapshot_url"])
        elif wayback:
            ts = wayback[-1].get("timestamp")
            original = wayback[-1].get("original")
            replay_url = f"https://web.archive.org/web/{ts}id_/{original}" if ts and original else ""
        content_probe = archived_content_probe(replay_url) if replay_url else {}

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

        wb_available = any(x.get("available") for x in availability)
        archive_hit = bool(wb_available or wayback or cc_hits or arquivo)
        result = {
            "listing_id": listing["listing_id"],
            "title": listing["title"],
            "urls_tested": listing["urls"],
            "wayback_availability": {"checks": availability, "errors": availability_errors},
            "wayback": {
                "capture_count": len(wayback),
                "first_capture": wayback[0].get("timestamp") if wayback else None,
                "last_capture": wayback[-1].get("timestamp") if wayback else None,
                "captures": wayback,
                "errors": wayback_errors,
                "content_probe": content_probe,
            },
            "commoncrawl": {
                "indexes_checked": [x.get("id") for x in cc_indexes],
                "capture_count": len(cc_hits),
                "captures": cc_hits,
                "errors": cc_errors,
            },
            "arquivo_pt": {
                "capture_count": len(arquivo),
                "captures": arquivo,
                "errors": arquivo_errors,
            },
            "archive_hit": archive_hit,
        }
        results.append(result)

        flat_rows.append({
            "listing_id": listing["listing_id"],
            "wayback_available": wb_available,
            "wayback_captures": len(wayback),
            "wayback_latest_title": content_probe.get("page_title", ""),
            "wayback_latest_sold_marker": content_probe.get("sold_marker_seen", ""),
            "wayback_latest_prices": "|".join(content_probe.get("eur_prices_seen", [])),
            "commoncrawl_captures": len(cc_hits),
            "arquivo_pt_captures": len(arquivo),
            "archive_hit": archive_hit,
            "wayback_errors": len(availability_errors) + len(wayback_errors),
            "commoncrawl_errors": len(cc_errors),
            "arquivo_pt_errors": len(arquivo_errors),
        })

    payload = {
        "tested_at_utc": tested_at,
        "purpose": "Known-URL third-party archive test; does not request Adverts.ie directly.",
        "commoncrawl_index_error": cc_index_error,
        "listings": results,
        "summary": {
            "listings_tested": len(results),
            "listings_with_any_archive_hit": sum(1 for r in results if r["archive_hit"]),
            "listings_wayback_available": sum(1 for r in results if any(x.get("available") for x in r["wayback_availability"]["checks"])),
            "listings_with_wayback_cdx_hit": sum(1 for r in results if r["wayback"]["capture_count"] > 0),
            "listings_with_commoncrawl_hit": sum(1 for r in results if r["commoncrawl"]["capture_count"] > 0),
            "listings_with_arquivo_pt_hit": sum(1 for r in results if r["arquivo_pt"]["capture_count"] > 0),
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
