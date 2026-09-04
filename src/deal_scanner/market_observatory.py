from __future__ import annotations

import csv
import json
import math
import os
import re
import statistics
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import requests


EBAY_SCHEMA = """
CREATE TABLE IF NOT EXISTS ebay_listing_state (
    id_product INTEGER NOT NULL,
    marketplace TEXT NOT NULL,
    item_id TEXT NOT NULL,
    region TEXT NOT NULL,
    title TEXT NOT NULL,
    price_value REAL NOT NULL,
    currency TEXT NOT NULL,
    item_location_country TEXT,
    seller_username TEXT,
    seller_account_type TEXT,
    condition_id TEXT,
    buying_options_json TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    missing_since_at TEXT,
    gone_at TEXT,
    inferred_quick_sale INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (id_product, marketplace, item_id)
);

CREATE TABLE IF NOT EXISTS ebay_reference_history (
    snapshot_date TEXT NOT NULL,
    id_product INTEGER NOT NULL,
    region TEXT NOT NULL,
    currency TEXT NOT NULL,
    ask_median REAL,
    ask_sample INTEGER NOT NULL,
    confirmed_sale_median REAL,
    confirmed_sales INTEGER NOT NULL,
    inferred_sale_median REAL,
    inferred_sales INTEGER NOT NULL,
    chosen_reference REAL,
    reference_type TEXT NOT NULL,
    strength TEXT NOT NULL,
    PRIMARY KEY (snapshot_date, id_product, region, currency)
);

CREATE INDEX IF NOT EXISTS idx_ebay_listing_product_region
    ON ebay_listing_state(id_product, region, currency);
CREATE INDEX IF NOT EXISTS idx_ebay_listing_gone
    ON ebay_listing_state(gone_at, inferred_quick_sale);
CREATE INDEX IF NOT EXISTS idx_ebay_reference_product_region
    ON ebay_reference_history(id_product, region, currency, snapshot_date);
"""

REFERENCE_FIELDS = [
    "snapshot_date", "id_product", "name", "region", "currency",
    "ask_median", "ask_sample", "confirmed_sale_median", "confirmed_sales",
    "inferred_sale_median", "inferred_sales", "chosen_reference",
    "smoothed_reference", "reference_type", "strength", "source_label",
]

RESALE_FIELDS = [
    "id_product", "name", "seller", "sourcing_decision",
    "risk_adjusted_landed_eur", "reference_region", "reference_type",
    "reference_strength", "expected_resale_eur", "gross_spread_eur",
    "gross_roi_pct", "resale_decision", "reference_snapshot_date",
]

DEFAULT_EXCLUDED = {
    "psa", "bgs", "cgc", "ace graded", "graded", "slab", "proxy", "orica",
    "custom card", "metal card", "digital", "code card", "lot of", "bundle of",
}

NON_ENGLISH_HINTS = {
    "japanese", "japanisch", "japonais", "giapponese", "japones",
    "german", "deutsch", "tedesco", "allemand",
    "italian", "italiano", "italien", "french", "francais", "français",
    "spanish", "espanol", "español", "korean", "chinese",
}

# A marketplace site is not the same thing as the physical location of an item.
# For Ireland/EU/UK evidence, query the marketplace AND force the actual item
# location to that country.  Global context intentionally has no country filter.
MARKETPLACE_COUNTRY = {
    "EBAY_IE": "IE",
    "EBAY_DE": "DE",
    "EBAY_FR": "FR",
    "EBAY_IT": "IT",
    "EBAY_ES": "ES",
    "EBAY_NL": "NL",
    "EBAY_BE": "BE",
    "EBAY_AT": "AT",
    "EBAY_GB": "GB",
}


def ensure_ebay_schema(conn) -> None:
    conn.executescript(EBAY_SCHEMA)
    conn.commit()


def _norm(text: str | None) -> str:
    value = str(text or "").lower().replace("é", "e").replace("è", "e").replace("á", "a").replace("í", "i")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(value: str | None) -> list[str]:
    return [_norm(x) for x in str(value or "").split("|") if _norm(x)]


def title_matches(title: str, watch: dict, default_excluded: Iterable[str] | None = None) -> bool:
    """Conservative raw-card matcher for an exact watched card.

    The watchlist supplies required tokens such as Pokemon name, collector number,
    and set name. We deliberately abstain on graded, custom, code-card, lot and
    obvious non-English listings rather than trying to rescue ambiguous matches.
    """
    text = _norm(title)
    required = _tokens(watch.get("required_tokens"))
    excluded = set(_tokens(watch.get("excluded_tokens")))
    excluded.update(_norm(x) for x in (default_excluded or DEFAULT_EXCLUDED))
    if any(token not in text for token in required):
        return False
    if any(token and token in text for token in excluded):
        return False

    language = _norm(watch.get("language") or "en")
    if language in {"en", "english"} and "english" not in text:
        if any(hint in text for hint in NON_ENGLISH_HINTS):
            return False
    return True


def expected_location_country(marketplace: str) -> str | None:
    return MARKETPLACE_COUNTRY.get(str(marketplace).upper())


def item_location_matches(item: dict, expected_country: str | None) -> bool:
    """Hard guard against treating a foreign-located item as local/EU evidence."""
    if expected_country is None:
        return True
    actual = str(item.get("item_location_country") or "").upper()
    return actual == expected_country.upper()


def _median(values: Iterable[float]) -> float | None:
    nums = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return None if not nums else round(float(statistics.median(nums)), 2)


def region_for_marketplace(marketplace: str, cfg: dict) -> str:
    for region, markets in cfg.get("ebay", {}).get("marketplaces", {}).items():
        if marketplace in markets:
            return str(region).upper()
    return "GLOBAL"


def read_watchlist(path: Path, max_rows: int | None = None) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        rows = [dict(r) for r in csv.DictReader(f) if r.get("id_product") and r.get("search_query")]
    if max_rows is not None:
        rows = rows[: max(0, int(max_rows))]
    return rows


def read_sold_evidence(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f) if r.get("id_product") and r.get("sale_date") and r.get("price_value")]


def choose_reference(asks: list[float], confirmed: list[float], inferred: list[float]) -> dict:
    """Choose a resale reference without pretending asks are sales.

    Confirmed sold evidence is preferred. Inferred quick-sales require a small
    sample. Active asks are only a weak fallback and remain explicitly labelled.
    """
    ask_median = _median(asks)
    sold_median = _median(confirmed)
    inferred_median = _median(inferred)

    if len(confirmed) >= 3:
        chosen, ref_type, strength = sold_median, "CONFIRMED_SALES", "STRONG"
    elif confirmed:
        chosen, ref_type, strength = sold_median, "CONFIRMED_SALES", "MEDIUM"
    elif len(inferred) >= 3:
        chosen, ref_type, strength = inferred_median, "INFERRED_QUICK_SALES", "MEDIUM"
    elif len(asks) >= 5:
        chosen, ref_type, strength = ask_median, "ACTIVE_ASKS", "WEAK"
    elif asks:
        chosen, ref_type, strength = ask_median, "ACTIVE_ASKS", "VERY_WEAK"
    else:
        chosen, ref_type, strength = None, "NONE", "NONE"

    return {
        "ask_median": ask_median,
        "ask_sample": len(asks),
        "confirmed_sale_median": sold_median,
        "confirmed_sales": len(confirmed),
        "inferred_sale_median": inferred_median,
        "inferred_sales": len(inferred),
        "chosen_reference": chosen,
        "reference_type": ref_type,
        "strength": strength,
    }


class EbayBrowseClient:
    def __init__(self, cfg: dict):
        ecfg = cfg.get("ebay", {})
        self.app_id = os.environ.get(ecfg.get("app_id_env", "EBAY_APP_ID"), "")
        self.cert_id = os.environ.get(ecfg.get("cert_id_env", "EBAY_CERT_ID"), "")
        self.oauth_url = ecfg.get("oauth_url", "https://api.ebay.com/identity/v1/oauth2/token")
        self.search_url = ecfg.get("search_url", "https://api.ebay.com/buy/browse/v1/item_summary/search")
        self.limit = int(ecfg.get("search_limit", 50))
        self.delay = float(ecfg.get("search_delay_seconds", 0.12))
        self.timeout = float(ecfg.get("timeout_seconds", 20))
        self.session = requests.Session()
        self._token: str | None = None
        self._expires_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.cert_id)

    def _get_token(self) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        if not self.configured:
            raise RuntimeError("eBay credentials are not configured")
        response = self.session.post(
            self.oauth_url,
            auth=(self.app_id, self.cert_id),
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        self._token = str(data["access_token"])
        self._expires_at = time.time() + int(data.get("expires_in") or 0)
        return self._token

    def search(self, query: str, marketplace: str, *, item_location_country: str | None = None) -> list[dict]:
        token = self._get_token()
        params = {"q": query, "limit": self.limit}
        if item_location_country:
            params["filter"] = f"itemLocationCountry:{item_location_country.upper()}"
        response = self.session.get(
            self.search_url,
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": marketplace,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        rows = []
        for item in payload.get("itemSummaries") or []:
            price = item.get("price") or {}
            try:
                price_value = float(price.get("value"))
            except (TypeError, ValueError):
                continue
            item_id = item.get("itemId")
            title = item.get("title")
            currency = price.get("currency")
            if not item_id or not title or not currency:
                continue
            seller = item.get("seller") or {}
            loc = item.get("itemLocation") or {}
            rows.append({
                "item_id": str(item_id),
                "title": str(title),
                "price_value": price_value,
                "currency": str(currency),
                "item_location_country": loc.get("country"),
                "seller_username": seller.get("username"),
                "seller_account_type": seller.get("sellerAccountType"),
                "condition_id": item.get("conditionId"),
                "buying_options": list(item.get("buyingOptions") or []),
            })
        if self.delay > 0:
            time.sleep(self.delay)
        return rows


def _date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def reconcile_listing_state(
    conn,
    *,
    id_product: int,
    marketplace: str,
    region: str,
    listings: list[dict],
    seen_date: str,
    confirm_missing_days: int,
    quick_sale_max_days: int,
) -> dict:
    """Upsert today's visible listings and confirm disappearance only after two scans.

    A single absence is not called a sale: it may simply have moved outside the
    Browse API's result window. The first miss records `missing_since_at`; a later
    successful scan must still miss the listing before it is marked gone.
    """
    seen_ids: set[str] = set()
    for item in listings:
        item_id = str(item["item_id"])
        seen_ids.add(item_id)
        conn.execute(
            """
            INSERT INTO ebay_listing_state(
              id_product,marketplace,item_id,region,title,price_value,currency,
              item_location_country,seller_username,seller_account_type,condition_id,
              buying_options_json,first_seen_at,last_seen_at,missing_since_at,gone_at,inferred_quick_sale
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
            ON CONFLICT(id_product,marketplace,item_id) DO UPDATE SET
              region=excluded.region,title=excluded.title,price_value=excluded.price_value,
              currency=excluded.currency,item_location_country=excluded.item_location_country,
              seller_username=excluded.seller_username,seller_account_type=excluded.seller_account_type,
              condition_id=excluded.condition_id,buying_options_json=excluded.buying_options_json,
              last_seen_at=excluded.last_seen_at,missing_since_at=NULL,gone_at=NULL,inferred_quick_sale=0
            """,
            (
                id_product, marketplace, item_id, region, item["title"], item["price_value"], item["currency"],
                item.get("item_location_country"), item.get("seller_username"), item.get("seller_account_type"),
                item.get("condition_id"), json.dumps(item.get("buying_options") or []), seen_date, seen_date, None, None,
            ),
        )

    prior = conn.execute(
        """SELECT item_id,first_seen_at,missing_since_at
           FROM ebay_listing_state
           WHERE id_product=? AND marketplace=? AND gone_at IS NULL""",
        (id_product, marketplace),
    ).fetchall()
    first_misses = confirmed_gone = quick_sales = 0
    today = _date(seen_date)
    for row in prior:
        if row["item_id"] in seen_ids:
            continue
        missing_since = row["missing_since_at"]
        if not missing_since:
            conn.execute(
                "UPDATE ebay_listing_state SET missing_since_at=? WHERE id_product=? AND marketplace=? AND item_id=?",
                (seen_date, id_product, marketplace, row["item_id"]),
            )
            first_misses += 1
            continue
        if (today - _date(missing_since)).days < max(1, int(confirm_missing_days)):
            continue
        life_days = max(0, (_date(missing_since) - _date(row["first_seen_at"])).days)
        quick = int(life_days <= int(quick_sale_max_days))
        conn.execute(
            """UPDATE ebay_listing_state
               SET gone_at=?, inferred_quick_sale=?
               WHERE id_product=? AND marketplace=? AND item_id=?""",
            (missing_since, quick, id_product, marketplace, row["item_id"]),
        )
        confirmed_gone += 1
        quick_sales += quick
    conn.commit()
    return {
        "seen": len(seen_ids),
        "first_misses": first_misses,
        "confirmed_gone": confirmed_gone,
        "inferred_quick_sales": quick_sales,
    }


def _manual_sales_for(
    rows: list[dict], *, id_product: int, region: str, currency: str,
    cfg: dict, today: date,
) -> list[float]:
    window = int(cfg.get("ebay", {}).get("sold_window_days", 30))
    cutoff = today - timedelta(days=window)
    out = []
    for row in rows:
        try:
            if int(row.get("id_product") or 0) != id_product:
                continue
            sold_day = _date(row["sale_date"])
            if sold_day < cutoff or sold_day > today:
                continue
            row_region = str(row.get("region") or region_for_marketplace(str(row.get("marketplace") or ""), cfg)).upper()
            if row_region != region or str(row.get("currency") or "").upper() != currency:
                continue
            out.append(float(row["price_value"]))
        except (TypeError, ValueError, KeyError):
            continue
    return out


def _product_name(conn, id_product: int) -> str:
    row = conn.execute("SELECT name FROM products WHERE id_product=?", (id_product,)).fetchone()
    return str(row["name"]) if row else f"Product {id_product}"


def _source_label(ref_type: str) -> str:
    return {
        "CONFIRMED_SALES": "eBay sold evidence",
        "INFERRED_QUICK_SALES": "eBay inferred quick-sale evidence",
        "ACTIVE_ASKS": "eBay active asking prices",
        "NONE": "no eBay reference",
    }.get(ref_type, "eBay reference")


def _save_reference(conn, today_s: str, id_product: int, region: str, currency: str, ref: dict) -> None:
    conn.execute(
        """
        INSERT INTO ebay_reference_history(
          snapshot_date,id_product,region,currency,ask_median,ask_sample,
          confirmed_sale_median,confirmed_sales,inferred_sale_median,inferred_sales,
          chosen_reference,reference_type,strength
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(snapshot_date,id_product,region,currency) DO UPDATE SET
          ask_median=excluded.ask_median,ask_sample=excluded.ask_sample,
          confirmed_sale_median=excluded.confirmed_sale_median,confirmed_sales=excluded.confirmed_sales,
          inferred_sale_median=excluded.inferred_sale_median,inferred_sales=excluded.inferred_sales,
          chosen_reference=excluded.chosen_reference,reference_type=excluded.reference_type,
          strength=excluded.strength
        """,
        (
            today_s, id_product, region, currency, ref["ask_median"], ref["ask_sample"],
            ref["confirmed_sale_median"], ref["confirmed_sales"], ref["inferred_sale_median"],
            ref["inferred_sales"], ref["chosen_reference"], ref["reference_type"], ref["strength"],
        ),
    )
    conn.commit()


def _smoothed_reference(conn, id_product: int, region: str, currency: str, days: int) -> float | None:
    rows = conn.execute(
        """SELECT chosen_reference FROM ebay_reference_history
           WHERE id_product=? AND region=? AND currency=? AND chosen_reference IS NOT NULL
           ORDER BY snapshot_date DESC LIMIT ?""",
        (id_product, region, currency, max(1, int(days))),
    ).fetchall()
    return _median([r["chosen_reference"] for r in rows])


def build_market_references(conn, cfg: dict, watch_rows: list[dict], sold_rows: list[dict], today: date) -> list[dict]:
    ensure_ebay_schema(conn)
    today_s = today.isoformat()
    sold_window = int(cfg.get("ebay", {}).get("sold_window_days", 30))
    sold_cutoff = today - timedelta(days=sold_window)
    smooth_days = int(cfg.get("ebay", {}).get("display_window_days", 14))
    output: list[dict] = []

    for watch in watch_rows:
        try:
            pid = int(watch["id_product"])
        except (TypeError, ValueError, KeyError):
            continue
        name = _product_name(conn, pid)
        for region, markets in cfg.get("ebay", {}).get("marketplaces", {}).items():
            region = str(region).upper()
            # A region can contain marketplaces with different currencies in theory;
            # group references by the actual currency seen instead of converting silently.
            currencies = {
                str(r["currency"]).upper()
                for r in conn.execute(
                    """SELECT DISTINCT currency FROM ebay_listing_state
                       WHERE id_product=? AND region=?""", (pid, region)
                ).fetchall()
            }
            for sold in sold_rows:
                try:
                    if int(sold.get("id_product") or 0) != pid:
                        continue
                    sold_region = str(sold.get("region") or region_for_marketplace(str(sold.get("marketplace") or ""), cfg)).upper()
                    if sold_region == region and sold.get("currency"):
                        currencies.add(str(sold["currency"]).upper())
                except (TypeError, ValueError):
                    continue
            if not currencies:
                # Expected native currencies make empty regions visible in diagnostics.
                if region in {"IRELAND", "EU"}:
                    currencies = {"EUR"}
                elif region == "UK":
                    currencies = {"GBP"}
                elif region == "GLOBAL":
                    currencies = {"USD"}

            for currency in sorted(currencies):
                ask_rows = conn.execute(
                    """SELECT price_value FROM ebay_listing_state
                       WHERE id_product=? AND region=? AND currency=? AND gone_at IS NULL
                         AND last_seen_at=?""",
                    (pid, region, currency, today_s),
                ).fetchall()
                asks = [float(r["price_value"]) for r in ask_rows]
                inferred_rows = conn.execute(
                    """SELECT price_value,gone_at FROM ebay_listing_state
                       WHERE id_product=? AND region=? AND currency=?
                         AND inferred_quick_sale=1 AND gone_at IS NOT NULL""",
                    (pid, region, currency),
                ).fetchall()
                inferred = [
                    float(r["price_value"]) for r in inferred_rows
                    if _date(r["gone_at"]) >= sold_cutoff
                ]
                confirmed = _manual_sales_for(
                    sold_rows, id_product=pid, region=region, currency=currency, cfg=cfg, today=today
                )
                ref = choose_reference(asks, confirmed, inferred)
                _save_reference(conn, today_s, pid, region, currency, ref)
                smoothed = _smoothed_reference(conn, pid, region, currency, smooth_days)
                output.append({
                    "snapshot_date": today_s,
                    "id_product": pid,
                    "name": name,
                    "region": region,
                    "currency": currency,
                    **ref,
                    "smoothed_reference": smoothed,
                    "source_label": _source_label(ref["reference_type"]),
                })
    return output


def write_market_reference(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REFERENCE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_ebay_observatory(conn, cfg: dict, watchlist_path: Path, sold_path: Path, output_path: Path) -> dict:
    ensure_ebay_schema(conn)
    ecfg = cfg.get("ebay", {})
    watch_rows = read_watchlist(watchlist_path, int(ecfg.get("max_watch_products", 20)))
    sold_rows = read_sold_evidence(sold_path)
    client = EbayBrowseClient(cfg)
    enabled = bool(ecfg.get("enabled", True)) and client.configured
    today = date.today()
    today_s = today.isoformat()
    accepted = queries = failures = inferred = location_rejected = 0
    default_excluded = ecfg.get("default_excluded_tokens") or list(DEFAULT_EXCLUDED)

    if enabled:
        confirm_missing = int(ecfg.get("confirm_missing_days", 1))
        quick_days = int(ecfg.get("quick_sale_max_days", 3))
        for watch in watch_rows:
            try:
                pid = int(watch["id_product"])
            except (TypeError, ValueError, KeyError):
                continue
            for region, marketplaces in ecfg.get("marketplaces", {}).items():
                for marketplace in marketplaces:
                    marketplace = str(marketplace)
                    region_name = str(region).upper()
                    location_country = None if region_name == "GLOBAL" else expected_location_country(marketplace)
                    try:
                        raw = client.search(
                            str(watch["search_query"]), marketplace,
                            item_location_country=location_country,
                        )
                        queries += 1
                    except Exception:
                        failures += 1
                        # Never infer a disappearance from a failed API call.
                        continue
                    geo_matched = [r for r in raw if item_location_matches(r, location_country)]
                    location_rejected += len(raw) - len(geo_matched)
                    matched = [r for r in geo_matched if title_matches(r["title"], watch, default_excluded)]
                    accepted += len(matched)
                    result = reconcile_listing_state(
                        conn,
                        id_product=pid,
                        marketplace=marketplace,
                        region=region_name,
                        listings=matched,
                        seen_date=today_s,
                        confirm_missing_days=confirm_missing,
                        quick_sale_max_days=quick_days,
                    )
                    inferred += result["inferred_quick_sales"]

    refs = build_market_references(conn, cfg, watch_rows, sold_rows, today)
    write_market_reference(output_path, refs)
    return {
        "enabled": enabled,
        "configured": client.configured,
        "watch_products": len(watch_rows),
        "api_queries": queries,
        "api_failures": failures,
        "accepted_listing_rows": accepted,
        "item_location_rejected_rows": location_rejected,
        "new_inferred_quick_sales": inferred,
        "manual_sold_evidence_rows": len(sold_rows),
        "reference_rows": len(refs),
        "strong_reference_rows": sum(1 for r in refs if r["strength"] == "STRONG"),
        "medium_reference_rows": sum(1 for r in refs if r["strength"] == "MEDIUM"),
        "note": "Ireland/EU/UK evidence is filtered by actual item location, not merely the eBay site. Regions/currencies stay separate; no silent FX mixing.",
    }


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _as_float(value) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def generate_resale_candidates(sourcing_path: Path, reference_path: Path, output_path: Path, cfg: dict) -> int:
    sourcing = _read_csv(sourcing_path)
    refs = _read_csv(reference_path)
    by_product: dict[int, list[dict]] = {}
    for ref in refs:
        try:
            pid = int(ref.get("id_product") or 0)
        except (TypeError, ValueError):
            continue
        # Automatic Ireland resale decisions use only local/continental-EU EUR
        # evidence. UK/Global stay visible as context but never drive a EUR buy.
        region = str(ref.get("region") or "").upper()
        if region not in {"IRELAND", "EU"}:
            continue
        if str(ref.get("currency") or "").upper() != "EUR":
            continue
        if ref.get("chosen_reference") in (None, ""):
            continue
        by_product.setdefault(pid, []).append(ref)

    region_order = {"IRELAND": 0, "EU": 1}
    strength_order = {"STRONG": 0, "MEDIUM": 1, "WEAK": 2, "VERY_WEAK": 3, "NONE": 9}
    min_spread = float(cfg.get("resale", {}).get("minimum_gross_spread_eur", 2.0))
    min_roi = float(cfg.get("resale", {}).get("minimum_gross_roi_pct", 25.0))
    rows = []
    for src in sourcing:
        if src.get("decision") in {"INELIGIBLE", "WAIT", "VERIFY_LANDED"}:
            continue
        landed = _as_float(src.get("risk_adjusted_landed_eur"))
        if landed is None or landed <= 0:
            continue
        try:
            pid = int(src.get("id_product") or 0)
        except (TypeError, ValueError):
            continue
        candidates = by_product.get(pid, [])
        if not candidates:
            continue
        candidates.sort(key=lambda r: (
            region_order.get(str(r.get("region") or "").upper(), 9),
            strength_order.get(str(r.get("strength") or "NONE").upper(), 9),
        ))
        ref = candidates[0]
        expected = _as_float(ref.get("smoothed_reference")) or _as_float(ref.get("chosen_reference"))
        if expected is None:
            continue
        spread = round(expected - landed, 2)
        roi = round(spread / landed * 100.0, 1)
        strength = str(ref.get("strength") or "NONE").upper()
        ref_type = str(ref.get("reference_type") or "NONE")
        if strength in {"STRONG", "MEDIUM"} and spread >= min_spread and roi >= min_roi:
            decision = "RESELL_TEST"
        elif strength in {"WEAK", "VERY_WEAK"} and spread >= min_spread and roi >= max(40.0, min_roi):
            decision = "WATCH_ONLY"
        else:
            decision = "THIN"
        rows.append({
            "id_product": pid,
            "name": src.get("name") or "",
            "seller": src.get("seller") or "",
            "sourcing_decision": src.get("decision") or "",
            "risk_adjusted_landed_eur": round(landed, 2),
            "reference_region": ref.get("region") or "",
            "reference_type": ref_type,
            "reference_strength": strength,
            "expected_resale_eur": round(expected, 2),
            "gross_spread_eur": spread,
            "gross_roi_pct": roi,
            "resale_decision": decision,
            "reference_snapshot_date": ref.get("snapshot_date") or "",
        })
    rows.sort(key=lambda r: (-r["gross_roi_pct"], -r["gross_spread_eur"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESALE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
