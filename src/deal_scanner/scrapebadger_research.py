from __future__ import annotations

import csv
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests

from deal_scanner.market_observatory import title_matches


SCRAPEBADGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS scrapebadger_ebay_completed_snapshots (
    snapshot_date TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    domain TEXT NOT NULL,
    id_product INTEGER NOT NULL,
    query_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    reported_price REAL,
    currency TEXT,
    shipping_cost REAL,
    sold_date TEXT,
    sold_date_at TEXT,
    buying_format TEXT,
    is_auction INTEGER,
    bids INTEGER,
    condition TEXT,
    location TEXT,
    seller_name TEXT,
    identity_status TEXT NOT NULL,
    sold_state_confidence TEXT NOT NULL,
    price_confidence TEXT NOT NULL,
    source_lineage_key TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_date, domain, id_product, item_id)
);

CREATE INDEX IF NOT EXISTS idx_sb_ebay_completed_product
    ON scrapebadger_ebay_completed_snapshots(id_product, sold_date_at, domain);
CREATE INDEX IF NOT EXISTS idx_sb_ebay_completed_lineage
    ON scrapebadger_ebay_completed_snapshots(source_lineage_key);

CREATE TABLE IF NOT EXISTS scrapebadger_vinted_listing_snapshots (
    snapshot_date TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    market TEXT NOT NULL,
    query_id TEXT NOT NULL,
    id_product INTEGER,
    query_kind TEXT NOT NULL,
    item_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    ask_price REAL,
    currency TEXT,
    service_fee REAL,
    total_item_price REAL,
    vinted_condition TEXT,
    catalog_id INTEGER,
    brand_id INTEGER,
    seller_id TEXT,
    seller_country_code TEXT,
    favourite_count INTEGER,
    view_count INTEGER,
    can_buy INTEGER,
    is_reserved INTEGER,
    is_closed INTEGER,
    is_hidden INTEGER,
    listing_state TEXT NOT NULL,
    identity_status TEXT NOT NULL,
    detail_checked INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_date, market, query_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_sb_vinted_item
    ON scrapebadger_vinted_listing_snapshots(item_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_sb_vinted_product
    ON scrapebadger_vinted_listing_snapshots(id_product, snapshot_date);
"""


EBAY_COMPLETED_FIELDS = [
    "snapshot_date", "observed_at", "provider", "domain", "id_product", "query_id",
    "item_id", "title", "url", "reported_price", "currency", "shipping_cost",
    "sold_date", "sold_date_at", "buying_format", "is_auction", "bids", "condition",
    "location", "seller_name", "identity_status", "sold_state_confidence",
    "price_confidence", "source_lineage_key",
]

VINTED_FIELDS = [
    "snapshot_date", "observed_at", "provider", "market", "query_id", "id_product",
    "query_kind", "item_id", "title", "url", "ask_price", "currency", "service_fee",
    "total_item_price", "vinted_condition", "catalog_id", "brand_id", "seller_id",
    "seller_country_code", "favourite_count", "view_count", "can_buy", "is_reserved",
    "is_closed", "is_hidden", "listing_state", "identity_status", "detail_checked",
]


class ScrapeBadgerClient:
    """Minimal research client with conservative 429 handling.

    ScrapeBadger's official SDKs retry rate-limit responses with exponential backoff.
    The project uses the same principle here while keeping the dependency surface to
    `requests`. Research-source failures remain isolated from production valuation.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 30.0,
        max_retries: int = 6,
        retry_delay: float = 2.0,
        min_interval_seconds: float = 1.1,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get("SCRAPEBADGER_API_KEY", "")
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))
        self.retry_delay = max(0.1, float(retry_delay))
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.session = requests.Session()
        self._last_request_started = 0.0
        self.rate_limit_retries = 0

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _respect_min_interval(self) -> None:
        if not self._last_request_started or self.min_interval_seconds <= 0:
            return
        wait = self.min_interval_seconds - (time.monotonic() - self._last_request_started)
        if wait > 0:
            time.sleep(wait)

    def _rate_limit_wait(self, response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(1.0, float(retry_after))
            except ValueError:
                pass

        reset = response.headers.get("X-RateLimit-Reset") or response.headers.get("RateLimit-Reset")
        if reset:
            try:
                numeric = float(reset)
                # APIs commonly encode either epoch seconds or seconds-from-now.
                if numeric > time.time() - 60:
                    return max(1.0, numeric - time.time() + 1.0)
                return max(1.0, numeric)
            except ValueError:
                pass

        return min(65.0, self.retry_delay * (2 ** attempt))

    def _get(self, url: str, params: dict | None = None) -> dict:
        if not self.configured:
            raise RuntimeError("SCRAPEBADGER_API_KEY is not configured")

        response: requests.Response | None = None
        for attempt in range(self.max_retries + 1):
            self._respect_min_interval()
            self._last_request_started = time.monotonic()
            response = self.session.get(
                url,
                params=params or {},
                headers={"x-api-key": self.api_key},
                timeout=self.timeout,
            )
            if response.status_code != 429:
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise RuntimeError("ScrapeBadger returned a non-object JSON payload")
                return payload

            if attempt >= self.max_retries:
                break
            self.rate_limit_retries += 1
            time.sleep(self._rate_limit_wait(response, attempt))

        assert response is not None
        response.raise_for_status()
        raise RuntimeError("unreachable")

    def account_info(self) -> dict:
        """Zero-credit account metadata useful for rate-limit diagnostics."""
        return self._get("https://scrapebadger.com/v1/account/me")

    def ebay_completed(
        self,
        query: str,
        *,
        domain: str = "com",
        page: int = 1,
        per_page: int = 60,
        sort_by: str = "newly_listed",
    ) -> dict:
        return self._get(
            "https://scrapebadger.com/v1/ebay/completed",
            {
                "query": query,
                "domain": domain,
                "page": int(page),
                "per_page": int(per_page),
                "sort_by": sort_by,
            },
        )

    def vinted_search(
        self,
        query: str,
        *,
        market: str = "ie",
        page: int = 1,
        per_page: int = 20,
        catalog_ids: str | None = None,
        order: str = "newest_first",
    ) -> dict:
        params: dict[str, object] = {
            "query": query,
            "market": market,
            "page": int(page),
            "per_page": int(per_page),
            "order": order,
        }
        if catalog_ids:
            params["catalog_ids"] = str(catalog_ids)
        return self._get("https://scrapebadger.com/v1/vinted/search", params)

    def vinted_item(self, item_id: str | int, *, market: str = "ie") -> dict:
        return self._get(
            f"https://scrapebadger.com/v1/vinted/items/{item_id}",
            {"market": market},
        )


def ensure_scrapebadger_schema(conn) -> None:
    conn.executescript(SCRAPEBADGER_SCHEMA)
    conn.commit()


def utc_now() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return now.date().isoformat(), now.isoformat()


def _float(value) -> float | None:
    if isinstance(value, dict):
        value = value.get("value") if "value" in value else value.get("amount")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool_int(value) -> int | None:
    if value is None:
        return None
    return int(bool(value))


def safe_account_summary(payload: dict) -> dict:
    """Keep only non-secret service-limit fields from `/v1/account/me`."""
    if not isinstance(payload, dict):
        return {}
    allowed = {
        "tier", "plan", "subscription", "rate_limit", "rate_limit_per_minute",
        "credits", "credits_remaining", "credit_balance", "credits_balance",
    }
    summary = {}
    for key, value in payload.items():
        key_l = str(key).lower()
        if key_l in allowed and isinstance(value, (str, int, float, bool, type(None))):
            summary[key_l] = value
    return summary


def read_watchlist(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f) if row.get("query_id") and row.get("search_query")]


def write_csv(path: Path, rows: Iterable[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def classify_ebay_price_confidence(item: dict) -> str:
    buying_format = str(item.get("buying_format") or "").strip().lower()
    if bool(item.get("is_auction")) or buying_format == "auction":
        return "HIGH_AUCTION_FINAL"
    if "best offer" in buying_format:
        return "PRICE_UNCERTAIN_BEST_OFFER"
    if buying_format in {"buy it now", "fixed price", "fixed_price"}:
        return "HIGH_FIXED_PRICE_NO_BEST_OFFER_EVIDENCE"
    return "PRICE_UNCERTAIN_OTHER"


def normalize_ebay_completed(
    item: dict,
    *,
    snapshot_date: str,
    observed_at: str,
    domain: str,
    watch: dict,
) -> dict | None:
    item_id = str(item.get("item_id") or "").strip()
    title = str(item.get("title") or "").strip()
    if not item_id or not title:
        return None

    price = item.get("price") or {}
    shipping = item.get("shipping_cost") or {}
    id_product = _int(watch.get("id_product"))
    if id_product is None:
        return None

    exact_match = title_matches(title, watch)
    return {
        "snapshot_date": snapshot_date,
        "observed_at": observed_at,
        "provider": "SCRAPEBADGER",
        "domain": domain,
        "id_product": id_product,
        "query_id": str(watch.get("query_id") or id_product),
        "item_id": item_id,
        "title": title,
        "url": item.get("url"),
        "reported_price": _float(price),
        "currency": price.get("currency") or item.get("currency"),
        "shipping_cost": _float(shipping),
        "sold_date": item.get("sold_date"),
        "sold_date_at": item.get("sold_date_at"),
        "buying_format": item.get("buying_format"),
        "is_auction": _bool_int(item.get("is_auction")),
        "bids": _int(item.get("bids")),
        "condition": item.get("condition"),
        "location": item.get("location"),
        "seller_name": item.get("seller_name"),
        "identity_status": "EXACT_TITLE_MATCH" if exact_match else "REVIEW_OR_REJECT",
        "sold_state_confidence": "PROVIDER_COMPLETED_STATE",
        "price_confidence": classify_ebay_price_confidence(item),
        "source_lineage_key": f"EBAY:{domain}:{item_id}",
        "raw_json": json.dumps(item, sort_keys=True, ensure_ascii=False),
    }


def persist_ebay_completed(conn, rows: Iterable[dict]) -> int:
    ensure_scrapebadger_schema(conn)
    inserted = 0
    for row in rows:
        before = conn.total_changes
        conn.execute(
            """
            INSERT OR IGNORE INTO scrapebadger_ebay_completed_snapshots(
              snapshot_date,observed_at,provider,domain,id_product,query_id,item_id,title,url,
              reported_price,currency,shipping_cost,sold_date,sold_date_at,buying_format,is_auction,
              bids,condition,location,seller_name,identity_status,sold_state_confidence,price_confidence,
              source_lineage_key,raw_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            tuple(row.get(name) for name in [
                "snapshot_date", "observed_at", "provider", "domain", "id_product", "query_id",
                "item_id", "title", "url", "reported_price", "currency", "shipping_cost",
                "sold_date", "sold_date_at", "buying_format", "is_auction", "bids", "condition",
                "location", "seller_name", "identity_status", "sold_state_confidence",
                "price_confidence", "source_lineage_key", "raw_json",
            ]),
        )
        inserted += conn.total_changes - before
    conn.commit()
    return inserted


def vinted_listing_state(item: dict, *, detail_checked: bool) -> str:
    """Conservative state classifier.

    `is_closed` is intentionally labelled CLOSED_UNPRICED rather than SOLD. During
    the pilot we validate whether provider closed-state semantics are reliable. A
    search disappearance or non-buyable item is never silently promoted to a sale.
    """
    if bool(item.get("is_hidden")):
        return "HIDDEN"
    if bool(item.get("is_reserved")):
        return "RESERVED"
    if bool(item.get("is_closed")):
        return "CLOSED_UNPRICED"
    if bool(item.get("can_buy")):
        return "ACTIVE_VERIFIED"
    if detail_checked:
        return "DETAIL_STATE_UNKNOWN"
    return "SEARCH_VISIBLE_UNVERIFIED"


def vinted_identity_status(item: dict, watch: dict, *, detail_checked: bool) -> str:
    kind = str(watch.get("query_kind") or "exact").strip().lower()
    if kind in {"lot", "bundle", "collection"}:
        return "LOT_OR_BUNDLE"

    title = str(item.get("title") or "")
    description = str(item.get("description") or "") if detail_checked else ""
    combined = f"{title} {description}".strip()
    if not title_matches(combined, watch):
        return "REVIEW_OR_REJECT"

    language = str(watch.get("language") or "en").lower()
    explicit_english = any(token in combined.lower() for token in (" english", " anglais", " eng ", " en "))
    if language in {"en", "english"} and detail_checked and explicit_english:
        return "EXACT_TEXT_MATCH_LANGUAGE_EXPLICIT"
    if detail_checked:
        return "LIKELY_MATCH_LANGUAGE_UNVERIFIED"
    return "SEARCH_MATCH_DETAIL_REQUIRED"


def normalize_vinted_item(
    item: dict,
    *,
    snapshot_date: str,
    observed_at: str,
    market: str,
    watch: dict,
    detail_checked: bool,
) -> dict | None:
    item_id = str(item.get("id") or "").strip()
    title = str(item.get("title") or "").strip()
    if not item_id or not title:
        return None

    price = item.get("price") or {}
    user = item.get("user") or item.get("seller") or {}
    id_product = _int(watch.get("id_product"))
    condition = item.get("status") or item.get("status_title")

    return {
        "snapshot_date": snapshot_date,
        "observed_at": observed_at,
        "provider": "SCRAPEBADGER",
        "market": market,
        "query_id": str(watch.get("query_id") or ""),
        "id_product": id_product,
        "query_kind": str(watch.get("query_kind") or "exact"),
        "item_id": item_id,
        "title": title,
        "url": item.get("url"),
        "ask_price": _float(price),
        "currency": price.get("currency_code") or item.get("currency"),
        "service_fee": _float(item.get("service_fee")),
        "total_item_price": _float(item.get("total_item_price")),
        "vinted_condition": condition,
        "catalog_id": _int(item.get("catalog_id")),
        "brand_id": _int(item.get("brand_id")),
        "seller_id": str(user.get("id")) if user.get("id") is not None else None,
        "seller_country_code": item.get("seller_country_code"),
        "favourite_count": _int(item.get("favourite_count")),
        "view_count": _int(item.get("view_count")),
        "can_buy": _bool_int(item.get("can_buy")),
        "is_reserved": _bool_int(item.get("is_reserved")),
        "is_closed": _bool_int(item.get("is_closed")),
        "is_hidden": _bool_int(item.get("is_hidden")),
        "listing_state": vinted_listing_state(item, detail_checked=detail_checked),
        "identity_status": vinted_identity_status(item, watch, detail_checked=detail_checked),
        "detail_checked": int(detail_checked),
        "raw_json": json.dumps(item, sort_keys=True, ensure_ascii=False),
    }


def persist_vinted(conn, rows: Iterable[dict]) -> int:
    ensure_scrapebadger_schema(conn)
    inserted = 0
    names = [
        "snapshot_date", "observed_at", "provider", "market", "query_id", "id_product",
        "query_kind", "item_id", "title", "url", "ask_price", "currency", "service_fee",
        "total_item_price", "vinted_condition", "catalog_id", "brand_id", "seller_id",
        "seller_country_code", "favourite_count", "view_count", "can_buy", "is_reserved",
        "is_closed", "is_hidden", "listing_state", "identity_status", "detail_checked", "raw_json",
    ]
    for row in rows:
        before = conn.total_changes
        conn.execute(
            f"""
            INSERT OR REPLACE INTO scrapebadger_vinted_listing_snapshots(
              {','.join(names)}
            ) VALUES({','.join('?' for _ in names)})
            """,
            tuple(row.get(name) for name in names),
        )
        inserted += conn.total_changes - before
    conn.commit()
    return inserted


def merge_vinted_detail(search_item: dict, detail_payload: dict) -> dict:
    detail_item = detail_payload.get("item") if isinstance(detail_payload, dict) else None
    if not isinstance(detail_item, dict):
        return dict(search_item)
    merged = dict(search_item)
    merged.update(detail_item)
    return merged
