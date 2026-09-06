from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LISTING_IDS = ["40758551", "40926024", "40926025"]
OUT_DIR = Path("output/archive_probe_touch")
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
    s.headers.update({"User-Agent": "pokemon-deal-scanner archive touch probe/0.1"})
    return s


HTTP = session()


def urls_for(listing_id: str) -> list[str]:
    path = f"/other-toys-games/pokemon-cards/{listing_id}"
    return [
        f"https://touch.adverts.ie{path}",
        f"http://touch.adverts.ie{path}",
        f"https://touch.adverts.ie/{listing_id}",
        f"http://touch.adverts.ie/{listing_id}",
        f"https://adverts.ie{path}",
        f"http://adverts.ie{path}",
    ]


def get_json(url: str, params: dict | None = None):
    r = HTTP.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def wayback_available(url: str) -> dict:
    data = get_json("https://archive.org/wayback/available", {"url": url})
    closest = (data.get("archived_snapshots") or {}).get("closest") or {}
    return {
        "available": bool(closest.get("available")),
        "timestamp": closest.get("timestamp"),
        "snapshot_url": closest.get("url"),
    }


def wayback_cdx(url: str) -> list[dict]:
    params = [
        ("url", url),
        ("output", "json"),
        ("fl", "timestamp,original,statuscode,mimetype,digest"),
        ("filter", "statuscode:200"),
        ("collapse", "digest"),
        ("limit", "20"),
    ]
    r = HTTP.get("https://web.archive.org/cdx/search/cdx", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if not data or len(data) < 2:
        return []
    fields = data[0]
    return [dict(zip(fields, row)) for row in data[1:]]


def commoncrawl_indexes(limit: int = 4) -> list[dict]:
    return get_json("https://index.commoncrawl.org/collinfo.json")[:limit]


def commoncrawl(url: str, indexes: list[dict]) -> list[dict]:
    hits = []
    for idx in indexes:
        api = idx.get("cdx-api")
        if not api:
            continue
        r = HTTP.get(api, params={"url": url, "output": "json"}, timeout=TIMEOUT)
        if r.status_code == 404:
            continue
        r.raise_for_status()
        for line in r.text.splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            row["index_id"] = idx.get("id")
            hits.append(row)
    return hits


def arquivo(url: str) -> list[dict]:
    endpoint = "https://arquivo.pt/wayback/timemap/json/" + quote(url, safe=":/?=&%")
    r = HTTP.get(endpoint, timeout=TIMEOUT)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    try:
        parsed = r.json()
    except ValueError:
        return []
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    if isinstance(parsed, dict):
        candidates = parsed.get("mementos") or parsed.get("list") or []
        if isinstance(candidates, list):
            return [x for x in candidates if isinstance(x, dict)]
        return [parsed]
    return []


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        cc_indexes = commoncrawl_indexes()
        cc_index_error = None
    except Exception as exc:
        cc_indexes = []
        cc_index_error = f"{type(exc).__name__}: {exc}"

    results = []
    for listing_id in LISTING_IDS:
        per_url = []
        for url in urls_for(listing_id):
            row = {"url": url}
            try:
                row["wayback_availability"] = wayback_available(url)
            except Exception as exc:
                row["wayback_availability_error"] = f"{type(exc).__name__}: {exc}"
            try:
                row["wayback_cdx"] = wayback_cdx(url)
            except Exception as exc:
                row["wayback_cdx_error"] = f"{type(exc).__name__}: {exc}"
            try:
                row["commoncrawl"] = commoncrawl(url, cc_indexes)
            except Exception as exc:
                row["commoncrawl_error"] = f"{type(exc).__name__}: {exc}"
            try:
                row["arquivo_pt"] = arquivo(url)
            except Exception as exc:
                row["arquivo_pt_error"] = f"{type(exc).__name__}: {exc}"
            row["hit"] = bool(
                (row.get("wayback_availability") or {}).get("available")
                or row.get("wayback_cdx")
                or row.get("commoncrawl")
                or row.get("arquivo_pt")
            )
            per_url.append(row)
        results.append({
            "listing_id": listing_id,
            "variants_tested": len(per_url),
            "variants_with_hit": sum(1 for x in per_url if x["hit"]),
            "rows": per_url,
        })

    payload = {
        "tested_at_utc": datetime.now(timezone.utc).isoformat(),
        "commoncrawl_indexes": [x.get("id") for x in cc_indexes],
        "commoncrawl_index_error": cc_index_error,
        "listings": results,
        "summary": {
            "listings_tested": len(results),
            "listings_with_any_hit": sum(1 for r in results if r["variants_with_hit"] > 0),
            "url_variants_tested": sum(r["variants_tested"] for r in results),
            "url_variants_with_hit": sum(r["variants_with_hit"] for r in results),
        },
    }
    (OUT_DIR / "touch_archive_probe.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    for result in results:
        print({k: result[k] for k in ("listing_id", "variants_tested", "variants_with_hit")})
        for row in result["rows"]:
            if row["hit"]:
                print("HIT", row["url"])


if __name__ == "__main__":
    main()
