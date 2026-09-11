from __future__ import annotations

import csv
import html as html_lib
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus, urljoin

import requests

from deal_scanner.market_observatory import read_watchlist, title_matches


GUMTREE_SCHEMA = """
CREATE TABLE IF NOT EXISTS gumtree_listing_state (
    listing_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price_gbp REAL NOT NULL,
    location TEXT,
    region TEXT NOT NULL,
    id_product INTEGER,
    exact_match INTEGER NOT NULL DEFAULT 0,
    identification_source TEXT,
    language_status TEXT,
    condition_status TEXT,
    source_query TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gumtree_product_region
    ON gumtree_listing_state(id_product, region, last_seen_at);
"""

OUTPUT_FIELDS = [
    "snapshot_date", "listing_id", "url", "title", "description", "price_gbp",
    "location", "region", "id_product", "product_name", "exact_match",
    "identification_source", "language_status", "condition_status", "source_query",
]

ANCHOR_RE = re.compile(
    r"""<a\b[^>]*href=["']([^"']*/p/[^"']+?/\d+(?:\?[^"']*)?)["'][^>]*>(.*?)</a>""",
    re.I | re.S,
)
PRICE_RE = re.compile(r"£\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")
COUNT_RE = re.compile(r"^\d+(?:/\d+)?$")
NON_ENGLISH_HINTS = {
    "japanese", "japanisch", "japonais", "giapponese", "japones",
    "german", "deutsch", "italian", "italiano", "french", "francais",
    "spanish", "espanol", "korean", "chinese", "simplified chinese",
}
NI_MARKERS = {
    "northern ireland", "belfast", "county antrim", "county down", "county armagh",
    "county tyrone", "county fermanagh", "county londonderry", "county derry",
    "newry", "lisburn", "bangor", "newtownabbey", "carrickfergus", "ballymena",
    "larne", "portadown", "craigavon", "lurgan", "coleraine", "cookstown",
    "randalstown", "banbridge", "dunmurry", "newtownards", "armagh",
}


def ensure_gumtree_schema(conn) -> None:
    conn.executescript(GUMTREE_SCHEMA)
    conn.commit()


def _norm(value: str | None) -> str:
    text = str(value or "").lower().replace("é", "e").replace("è", "e")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def infer_language_status(text: str) -> str:
    value = _norm(text)
    if any(hint in value for hint in NON_ENGLISH_HINTS):
        return "NON_ENGLISH"
    if re.search(r"\benglish\b|\ben\b", value):
        return "EN_CONFIRMED"
    return "UNKNOWN"


def infer_condition_status(text: str) -> str:
    value = _norm(text)
    if re.search(r"\bnear mint\b|\bnm\b|\bpack fresh\b", value):
        return "NM_CLAIMED"
    if re.search(r"\blightly played\b|\blp\b|\bplayed\b|\bpoor\b|\bdamaged\b|\bcreased\b", value):
        return "NOT_NM"
    return "UNKNOWN"


def classify_region(location: str | None, source_region: str | None = None) -> str:
    text = _norm(location)
    if str(source_region or "").upper() == "NORTHERN_IRELAND":
        return "NORTHERN_IRELAND"
    return "NORTHERN_IRELAND" if any(x in text for x in NI_MARKERS) else "GREAT_BRITAIN"


def _meaningful(text: str) -> bool:
    value = " ".join(str(text or "").split()).strip()
    return bool(
        value
        and not COUNT_RE.fullmatch(value)
        and not PRICE_RE.fullmatch(value)
        and value.lower() not in {"featured", "delivery only", "one place for all your ads", "post an ad"}
    )


def parse_search_html(page_html: str, base_url: str = "https://www.gumtree.com") -> list[dict]:
    """Parse listing anchors without relying on unstable Gumtree CSS classes.

    Tags inside each result anchor, including void image tags, become newlines so
    the parser does not depend on balanced nested HTML.
    """
    rows: list[dict] = []
    seen: set[str] = set()
    for href, body in ANCHOR_RE.findall(page_html or ""):
        parts = href.split("?", 1)[0].rstrip("/").split("/")
        listing_id = parts[-1] if parts and parts[-1].isdigit() else ""
        if not listing_id or listing_id in seen:
            continue
        text = re.sub(r"<[^>]+>", "\n", body)
        chunks = [" ".join(html_lib.unescape(x).split()).strip() for x in text.splitlines()]
        chunks = [x for x in chunks if x]
        blob = " ".join(chunks)
        price_match = PRICE_RE.search(blob)
        if not price_match:
            continue
        meaningful = [x for x in chunks if _meaningful(x)]
        if not meaningful:
            continue
        price_index = next((i for i, x in enumerate(chunks) if PRICE_RE.search(x)), len(chunks))
        before_price = [x for x in chunks[:price_index] if _meaningful(x)]
        title = meaningful[0]
        location = before_price[-1] if len(before_price) >= 2 else ""
        description = " ".join(before_price[1:-1] if len(before_price) >= 3 else before_price[1:])
        seen.add(listing_id)
        rows.append({
            "listing_id": listing_id,
            "url": urljoin(base_url, href),
            "title": title,
            "description": description,
            "price_gbp": float(price_match.group(1).replace(",", "")),
            "location": location,
        })
    return rows


class GumtreeClient:
    def __init__(self, cfg: dict):
        gcfg = cfg.get("gumtree", {})
        self.base_url = str(gcfg.get("base_url", "https://www.gumtree.com")).rstrip("/")
        self.timeout = float(gcfg.get("timeout_seconds", 20))
        self.user_agent = str(gcfg.get(
            "user_agent",
            "Mozilla/5.0 (compatible; PokemonDealScanner/0.7; +https://github.com/Muzzimu/pokemon-deal-scanner)",
        ))
        self.session = requests.Session()

    def fetch_search_url(self, url: str) -> list[dict]:
        response = self.session.get(
            url,
            headers={"User-Agent": self.user_agent, "Accept-Language": "en-GB,en;q=0.9"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return parse_search_html(response.text, self.base_url)

    def search_url(self, query: str, location: str) -> str:
        return (
            f"{self.base_url}/search?search_category=for-sale"
            f"&search_location={quote_plus(location)}&q={quote_plus(query)}"
            "&hitRecallAllCateFlag=true&sort=date"
        )


def _product_name(conn, id_product: int | None) -> str:
    if not id_product:
        return ""
    row = conn.execute("SELECT name FROM products WHERE id_product=?", (int(id_product),)).fetchone()
    return str(row["name"]) if row else ""


def _identify_from_watchlist(row: dict, watch_rows: list[dict]) -> tuple[int | None, str]:
    text = " ".join([row.get("title") or "", row.get("description") or ""]).strip()
    matches = []
    for watch in watch_rows:
        try:
            pid = int(watch.get("id_product") or 0)
        except (TypeError, ValueError):
            continue
        if pid > 0 and title_matches(text, watch):
            matches.append(pid)
    return (matches[0], "watchlist_exact_tokens") if len(set(matches)) == 1 else (None, "")


def _persist_listing(conn, row: dict, snapshot_date: str) -> None:
    conn.execute(
        """
        INSERT INTO gumtree_listing_state(
          listing_id,url,title,description,price_gbp,location,region,id_product,
          exact_match,identification_source,language_status,condition_status,
          source_query,first_seen_at,last_seen_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(listing_id) DO UPDATE SET
          url=excluded.url,title=excluded.title,description=excluded.description,
          price_gbp=excluded.price_gbp,location=excluded.location,region=excluded.region,
          id_product=COALESCE(excluded.id_product,gumtree_listing_state.id_product),
          exact_match=MAX(gumtree_listing_state.exact_match,excluded.exact_match),
          identification_source=CASE WHEN excluded.exact_match=1
            THEN excluded.identification_source ELSE gumtree_listing_state.identification_source END,
          language_status=excluded.language_status,condition_status=excluded.condition_status,
          source_query=excluded.source_query,last_seen_at=excluded.last_seen_at
        """,
        (
            row["listing_id"], row["url"], row["title"], row.get("description") or "",
            row["price_gbp"], row.get("location") or "", row["region"], row.get("id_product"),
            int(bool(row.get("exact_match"))), row.get("identification_source") or "",
            row.get("language_status") or "UNKNOWN", row.get("condition_status") or "UNKNOWN",
            row.get("source_query") or "", snapshot_date, snapshot_date,
        ),
    )


def scan_gumtree(conn, cfg: dict, watchlist_path: Path, output_path: Path, *, today: date | None = None) -> dict:
    ensure_gumtree_schema(conn)
    today = today or date.today()
    today_s = today.isoformat()
    gcfg = cfg.get("gumtree", {})
    watch_rows = read_watchlist(watchlist_path, int(gcfg.get("max_watch_products", 25)))
    client = GumtreeClient(cfg)
    max_price = float(gcfg.get("max_listing_price_gbp", 5000))
    enabled = bool(gcfg.get("enabled", True))
    collected: dict[str, dict] = {}
    searches = failures = rejected_price = 0
    errors: list[str] = []

    def consume(raw_rows: list[dict], source_query: str, source_region: str) -> None:
        nonlocal rejected_price
        for raw in raw_rows:
            price = float(raw.get("price_gbp") or 0)
            if price <= 0 or price > max_price:
                rejected_price += 1
                continue
            row = dict(raw)
            row["source_query"] = source_query
            row["region"] = classify_region(row.get("location"), source_region)
            blob = " ".join([row.get("title") or "", row.get("description") or ""])
            row["language_status"] = infer_language_status(blob)
            row["condition_status"] = infer_condition_status(blob)
            pid, source = _identify_from_watchlist(row, watch_rows)
            row["id_product"], row["exact_match"], row["identification_source"] = pid, int(pid is not None), source
            prior = collected.get(row["listing_id"])
            if prior and prior.get("exact_match") and not row.get("exact_match"):
                continue
            collected[row["listing_id"]] = row

    if enabled:
        for source in gcfg.get("discovery_sources", []):
            url = str(source.get("url") or "")
            if not url:
                continue
            try:
                consume(client.fetch_search_url(url), str(source.get("query") or "pokemon cards"), str(source.get("region") or ""))
                searches += 1
            except Exception as exc:
                failures += 1
                errors.append(f"discovery {source.get('region')}: {type(exc).__name__}: {exc}")

        exact_locations = gcfg.get("exact_search_locations") or {
            "NORTHERN_IRELAND": "northern-ireland", "GREAT_BRITAIN": "uk",
        }
        for watch in watch_rows:
            query = str(watch.get("search_query") or "").strip()
            if not query:
                continue
            for region, location in exact_locations.items():
                try:
                    consume(client.fetch_search_url(client.search_url(query, str(location))), query, str(region))
                    searches += 1
                except Exception as exc:
                    failures += 1
                    errors.append(f"exact {region} {query}: {type(exc).__name__}: {exc}")

    rows = []
    for row in collected.values():
        _persist_listing(conn, row, today_s)
        rows.append({"snapshot_date": today_s, **row, "product_name": _product_name(conn, row.get("id_product"))})
    conn.commit()
    rows.sort(key=lambda r: (0 if r.get("region") == "NORTHERN_IRELAND" else 1, r.get("price_gbp") or 999999))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "enabled": enabled,
        "searches_attempted": searches + failures,
        "searches_succeeded": searches,
        "search_failures": failures,
        "listing_rows": len(rows),
        "exact_match_rows": sum(1 for r in rows if r.get("exact_match")),
        "northern_ireland_rows": sum(1 for r in rows if r.get("region") == "NORTHERN_IRELAND"),
        "rejected_placeholder_or_extreme_prices": rejected_price,
        "errors": errors[:10],
        "note": (
            "Gumtree is a discovery/acquisition source. Failed fetches never imply a sale, "
            "and ambiguous listings never receive an exact-card price signal."
        ),
    }
