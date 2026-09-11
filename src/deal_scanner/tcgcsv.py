from __future__ import annotations

import csv
import json
import math
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import requests


REFERENCE_FIELDS = [
    "id_product", "name", "tcgplayer_product_id",
    "market_price_usd", "most_recent_sale_usd",
    "lowest_listing_price_usd", "lowest_listing_shipping_usd", "executable_floor_usd",
    "market_price_eur", "most_recent_sale_eur",
    "lowest_listing_price_eur", "lowest_listing_shipping_eur", "executable_floor_eur",
    "fx_usd_to_eur",
    "sales_30d", "sales_90d", "avg_daily_sold", "current_quantity", "current_sellers",
    "low_price_usd", "low_price_eur", "listing_count",
    "reference_strength", "checked_at", "source", "notes",
]

TCGCSV_REFERENCE_FIELDS = [
    "snapshot_date", "id_product", "name", "tcgplayer_product_id", "group_id", "group_name",
    "subtype_name", "market_price_usd", "low_price_usd", "mid_price_usd", "high_price_usd",
    "direct_low_price_usd", "mapping_status", "mapping_note",
]

AUDIT_FIELDS = [
    "snapshot_date", "id_product", "name", "tcgplayer_product_id", "group_id", "group_name",
    "cardtrader_blueprints", "version_hint", "status", "subtypes_seen", "notes",
]

TCGCSV_SCHEMA = """
CREATE TABLE IF NOT EXISTS tcgcsv_groups (
    group_id INTEGER PRIMARY KEY,
    name TEXT,
    abbreviation TEXT,
    published_on TEXT,
    modified_on TEXT,
    last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tcgcsv_products (
    tcgplayer_product_id INTEGER PRIMARY KEY,
    group_id INTEGER NOT NULL,
    name TEXT,
    number TEXT,
    rarity TEXT,
    modified_on TEXT,
    last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tcgcsv_price_snapshots (
    snapshot_date TEXT NOT NULL,
    tcgplayer_product_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    subtype_name TEXT NOT NULL,
    low_price_usd REAL,
    mid_price_usd REAL,
    high_price_usd REAL,
    market_price_usd REAL,
    direct_low_price_usd REAL,
    PRIMARY KEY (snapshot_date, tcgplayer_product_id, subtype_name)
);

CREATE INDEX IF NOT EXISTS idx_tcgcsv_products_group
    ON tcgcsv_products(group_id, tcgplayer_product_id);
CREATE INDEX IF NOT EXISTS idx_tcgcsv_prices_product_date
    ON tcgcsv_price_snapshots(tcgplayer_product_id, snapshot_date);
"""


class TCGCSVError(RuntimeError):
    pass


class TCGCSVClient:
    def __init__(self, base_url: str = "https://tcgcsv.com/tcgplayer", *, category_id: int = 3,
                 delay_seconds: float = 0.25, timeout_seconds: int = 30,
                 user_agent: str = "pokemon-deal-scanner/0.12 (+personal research)"):
        self.base_url = base_url.rstrip("/")
        self.category_id = int(category_id)
        self.delay_seconds = max(0.0, float(delay_seconds))
        self.timeout_seconds = int(timeout_seconds)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json",
        })

    def _get_results(self, path: str) -> list[dict]:
        last_exc = None
        for attempt in range(3):
            try:
                response = self.session.get(self.base_url + path, timeout=self.timeout_seconds)
                if response.status_code == 429:
                    wait = float(response.headers.get("Retry-After", max(2.0, self.delay_seconds)))
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("success") is False:
                    raise TCGCSVError(f"Unexpected TCGCSV response for {path}: {payload!r}")
                rows = payload.get("results")
                if not isinstance(rows, list):
                    raise TCGCSVError(f"TCGCSV response for {path} has no results list")
                if self.delay_seconds:
                    time.sleep(self.delay_seconds)
                return [dict(x) for x in rows if isinstance(x, dict)]
            except Exception as exc:  # network/provider error; caller decides whether to degrade gracefully
                last_exc = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise TCGCSVError(f"GET {path} failed: {last_exc}")

    def groups(self) -> list[dict]:
        return self._get_results(f"/{self.category_id}/groups")

    def products(self, group_id: int) -> list[dict]:
        return self._get_results(f"/{self.category_id}/{int(group_id)}/products")

    def prices(self, group_id: int) -> list[dict]:
        return self._get_results(f"/{self.category_id}/{int(group_id)}/prices")


def _num(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _int(value) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return bool(row)


def ensure_tcgcsv_schema(conn) -> None:
    """Create TCGCSV storage and add a non-destructive CT->TCGplayer id bridge column."""
    conn.executescript(TCGCSV_SCHEMA)
    if _table_exists(conn, "cardtrader_blueprints"):
        columns = {str(r[1]) for r in conn.execute("PRAGMA table_info(cardtrader_blueprints)").fetchall()}
        if "tcgplayer_product_id" not in columns:
            conn.execute("ALTER TABLE cardtrader_blueprints ADD COLUMN tcgplayer_product_id INTEGER")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ct_blueprints_tcgplayer ON cardtrader_blueprints(tcgplayer_product_id)"
        )
    conn.commit()


def sync_tcgplayer_ids_from_blueprints(conn, blueprints: list[dict]) -> int:
    """Persist CardTrader's explicit tcg_player_id; never infer ids from names/numbers."""
    ensure_tcgcsv_schema(conn)
    values: list[tuple[int, int]] = []
    for bp in blueprints:
        blueprint_id = _int(bp.get("id"))
        tcg_id = _int(
            bp.get("tcg_player_id")
            or bp.get("tcgplayer_product_id")
            or bp.get("tcgplayer_id")
            or bp.get("tcgPlayerId")
        )
        if blueprint_id is not None and tcg_id is not None:
            values.append((tcg_id, blueprint_id))
    if values:
        conn.executemany(
            "UPDATE cardtrader_blueprints SET tcgplayer_product_id=? WHERE blueprint_id=?",
            values,
        )
        conn.commit()
    return len(values)


def _extended(product: dict, key: str) -> str:
    wanted = key.strip().lower().replace(" ", "")
    data = product.get("extendedData") or product.get("extended_data") or []
    if not isinstance(data, list):
        return ""
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("displayName") or "").lower().replace(" ", "")
        if name == wanted:
            return str(item.get("value") or "")
    return ""


def _upsert_groups(conn, groups: list[dict], seen: str) -> None:
    values = []
    for group in groups:
        gid = _int(group.get("groupId"))
        if gid is None:
            continue
        values.append((
            gid,
            str(group.get("name") or ""),
            str(group.get("abbreviation") or ""),
            str(group.get("publishedOn") or ""),
            str(group.get("modifiedOn") or ""),
            seen,
        ))
    conn.executemany(
        """INSERT INTO tcgcsv_groups(group_id,name,abbreviation,published_on,modified_on,last_seen)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(group_id) DO UPDATE SET
             name=excluded.name, abbreviation=excluded.abbreviation,
             published_on=excluded.published_on, modified_on=excluded.modified_on,
             last_seen=excluded.last_seen""",
        values,
    )
    conn.commit()


def _upsert_products(conn, group_id: int, products: list[dict], seen: str) -> int:
    values = []
    for product in products:
        pid = _int(product.get("productId"))
        if pid is None:
            continue
        values.append((
            pid,
            int(group_id),
            str(product.get("name") or product.get("cleanName") or ""),
            _extended(product, "Number"),
            _extended(product, "Rarity"),
            str(product.get("modifiedOn") or ""),
            seen,
        ))
    conn.executemany(
        """INSERT INTO tcgcsv_products(
             tcgplayer_product_id,group_id,name,number,rarity,modified_on,last_seen
           ) VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(tcgplayer_product_id) DO UPDATE SET
             group_id=excluded.group_id, name=excluded.name, number=excluded.number,
             rarity=excluded.rarity, modified_on=excluded.modified_on, last_seen=excluded.last_seen""",
        values,
    )
    conn.commit()
    return len(values)


def _upsert_prices(conn, group_id: int, rows: list[dict], snapshot_date: str,
                   restrict_to: set[int] | None = None) -> int:
    values = []
    for row in rows:
        pid = _int(row.get("productId"))
        if pid is None or (restrict_to is not None and pid not in restrict_to):
            continue
        subtype = str(row.get("subTypeName") or "UNKNOWN").strip() or "UNKNOWN"
        values.append((
            snapshot_date, pid, int(group_id), subtype,
            _num(row.get("lowPrice")), _num(row.get("midPrice")), _num(row.get("highPrice")),
            _num(row.get("marketPrice")), _num(row.get("directLowPrice")),
        ))
    conn.executemany(
        """INSERT INTO tcgcsv_price_snapshots(
             snapshot_date,tcgplayer_product_id,group_id,subtype_name,
             low_price_usd,mid_price_usd,high_price_usd,market_price_usd,direct_low_price_usd
           ) VALUES(?,?,?,?,?,?,?,?,?)
           ON CONFLICT(snapshot_date,tcgplayer_product_id,subtype_name) DO UPDATE SET
             group_id=excluded.group_id, low_price_usd=excluded.low_price_usd,
             mid_price_usd=excluded.mid_price_usd, high_price_usd=excluded.high_price_usd,
             market_price_usd=excluded.market_price_usd, direct_low_price_usd=excluded.direct_low_price_usd""",
        values,
    )
    conn.commit()
    return len(values)


def _target_cardmarket_ids(conn, current_paths: list[Path], today: date, tracking_days: int) -> set[int]:
    targets: set[int] = set()
    for path in current_paths:
        for row in _read_csv(path):
            pid = _int(row.get("id_product"))
            if pid is not None:
                targets.add(pid)
    # Keep collecting marks for cards whose old forecasts have not yet reached the
    # longest holding horizon, even if they leave today's candidate universe.
    if _table_exists(conn, "model_predictions"):
        cutoff = (today - timedelta(days=max(1, int(tracking_days)))).isoformat()
        for row in conn.execute(
            "SELECT DISTINCT id_product FROM model_predictions WHERE snapshot_date>=?", (cutoff,)
        ).fetchall():
            targets.add(int(row[0]))
    return targets


def _exact_ct_tcgplayer_mapping(conn, target_ids: set[int]) -> tuple[dict[int, dict], dict[int, str]]:
    if not target_ids or not _table_exists(conn, "cardtrader_blueprints"):
        return {}, {}
    rows = conn.execute(
        """SELECT m.id_product,m.blueprint_id,b.tcgplayer_product_id,b.version,
                  (SELECT COUNT(DISTINCT x.id_product)
                     FROM cardtrader_blueprint_map x WHERE x.blueprint_id=m.blueprint_id) AS cm_map_count
           FROM cardtrader_blueprint_map m
           JOIN cardtrader_blueprints b ON b.blueprint_id=m.blueprint_id
           WHERE b.tcgplayer_product_id IS NOT NULL"""
    ).fetchall()
    grouped: dict[int, list[dict]] = defaultdict(list)
    rejected: dict[int, str] = {}
    for row in rows:
        cm_id = int(row["id_product"])
        if cm_id not in target_ids:
            continue
        if int(row["cm_map_count"] or 0) != 1:
            rejected[cm_id] = "CardTrader blueprint maps to multiple Cardmarket products"
            continue
        grouped[cm_id].append(dict(row))

    out: dict[int, dict] = {}
    for cm_id, matches in grouped.items():
        tcg_ids = {int(r["tcgplayer_product_id"]) for r in matches if r["tcgplayer_product_id"] is not None}
        if len(tcg_ids) != 1:
            rejected[cm_id] = "Cardmarket product maps to multiple TCGplayer product ids"
            continue
        tcg_id = next(iter(tcg_ids))
        versions = sorted({str(r.get("version") or "") for r in matches if str(r.get("version") or "")})
        blueprints = sorted({int(r["blueprint_id"]) for r in matches})
        out[cm_id] = {
            "tcgplayer_product_id": tcg_id,
            "version_hint": " | ".join(versions),
            "blueprints": blueprints,
        }
    return out, rejected


def _known_groups(conn, tcg_ids: set[int]) -> dict[int, dict]:
    if not tcg_ids:
        return {}
    out: dict[int, dict] = {}
    ids = sorted(tcg_ids)
    for start in range(0, len(ids), 800):
        chunk = ids[start:start + 800]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""SELECT p.tcgplayer_product_id,p.group_id,p.name,g.name AS group_name
                FROM tcgcsv_products p LEFT JOIN tcgcsv_groups g ON g.group_id=p.group_id
                WHERE p.tcgplayer_product_id IN ({placeholders})""",
            chunk,
        ).fetchall()
        for row in rows:
            out[int(row["tcgplayer_product_id"])] = dict(row)
    return out


def _discover_missing_products(conn, client: TCGCSVClient, missing_ids: set[int], today: date,
                               max_group_requests: int) -> dict:
    status = {"groups_endpoint": 0, "product_group_requests": 0, "products_cached": 0, "unresolved": 0}
    if not missing_ids:
        return status
    groups = client.groups()
    status["groups_endpoint"] = 1
    _upsert_groups(conn, groups, today.isoformat())

    # Recent sets first: most new scanner targets are modern cards. If an older card
    # remains unresolved we continue until the configured request cap is reached.
    ordered = sorted(groups, key=lambda g: str(g.get("publishedOn") or ""), reverse=True)
    unresolved = set(missing_ids)
    for group in ordered[:max(1, int(max_group_requests))]:
        gid = _int(group.get("groupId"))
        if gid is None:
            continue
        products = client.products(gid)
        status["product_group_requests"] += 1
        status["products_cached"] += _upsert_products(conn, gid, products, today.isoformat())
        seen = {_int(p.get("productId")) for p in products}
        unresolved -= {x for x in seen if x is not None}
        if not unresolved:
            break
    status["unresolved"] = len(unresolved)
    return status


def choose_subtype(price_rows: list[dict], version_hint: str = "") -> tuple[dict | None, str, str]:
    """Choose a TCGCSV subtype only when it is unambiguous or explicitly hinted.

    TCGCSV does not expose SKU condition/language. Multiple subtype rows can represent
    Normal/Holofoil/Reverse Holofoil versions of the same TCGplayer product, so guessing
    would violate the scanner's exact-printing guardrail.
    """
    rows = [dict(r) for r in price_rows]
    if not rows:
        return None, "NO_PRICE", ""
    if len(rows) == 1:
        return rows[0], "UNAMBIGUOUS", "single TCGCSV subtype"

    hint = str(version_hint or "").lower()
    desired = None
    if "reverse holo" in hint or "reverse-holo" in hint:
        desired = "reverse holofoil"
    elif "holo" in hint and "reverse" not in hint:
        desired = "holofoil"
    elif "non-holo" in hint or "non holo" in hint or "normal" in hint:
        desired = "normal"

    if desired:
        matches = [r for r in rows if str(r.get("subTypeName") or "").strip().lower() == desired]
        if len(matches) == 1:
            return matches[0], "VERSION_HINT", f"CardTrader version explicitly implies {desired}"
    return None, "AMBIGUOUS_SUBTYPE", "multiple TCGCSV subtypes and no exact variant discriminator"


def _card_names(conn, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    out: dict[int, str] = {}
    values = sorted(ids)
    for start in range(0, len(values), 800):
        chunk = values[start:start + 800]
        placeholders = ",".join("?" for _ in chunk)
        for row in conn.execute(
            f"SELECT id_product,name FROM products WHERE id_product IN ({placeholders})", chunk
        ).fetchall():
            out[int(row["id_product"])] = str(row["name"] or "")
    return out


def _reference_row(cm_id: int, name: str, tcg_id: int, price: dict, today: date,
                   strength: str, mapping_note: str) -> dict:
    subtype = str(price.get("subTypeName") or "")
    return {
        "id_product": cm_id,
        "name": name,
        "tcgplayer_product_id": tcg_id,
        "market_price_usd": price.get("marketPrice") if price.get("marketPrice") is not None else "",
        "most_recent_sale_usd": "",
        # TCGCSV lowPrice is condition-agnostic and excludes shipping. It therefore
        # belongs in the legacy/context field, not the executable-floor fields.
        "lowest_listing_price_usd": "",
        "lowest_listing_shipping_usd": "",
        "executable_floor_usd": "",
        "market_price_eur": "",
        "most_recent_sale_eur": "",
        "lowest_listing_price_eur": "",
        "lowest_listing_shipping_eur": "",
        "executable_floor_eur": "",
        "fx_usd_to_eur": "",
        "sales_30d": "",
        "sales_90d": "",
        "avg_daily_sold": "",
        "current_quantity": "",
        "current_sellers": "",
        "low_price_usd": price.get("lowPrice") if price.get("lowPrice") is not None else "",
        "low_price_eur": "",
        "listing_count": "",
        "reference_strength": str(strength or "MEDIUM").upper(),
        "checked_at": today.isoformat(),
        "source": "TCGCSV",
        "notes": (
            f"TCGCSV daily cached TCGplayer Market Price; subtype={subtype}; "
            "SKU condition/language, seller depth, shipping and realised-sale timestamp unavailable; "
            f"{mapping_note}"
        ),
    }


def publish_tcgcsv_model_observations(conn, cfg: dict, today: date) -> int:
    """Publish today's TCGCSV Market Price as a US proxy for walk-forward outcomes."""
    if not _table_exists(conn, "model_market_observations"):
        return 0
    fx = float(cfg.get("fx", {}).get("fallback_usd_to_eur", 0.86))
    rows = conn.execute(
        """SELECT DISTINCT m.id_product,s.market_price_usd
           FROM tcgcsv_price_snapshots s
           JOIN cardtrader_blueprints b ON b.tcgplayer_product_id=s.tcgplayer_product_id
           JOIN cardtrader_blueprint_map m ON m.blueprint_id=b.blueprint_id
           WHERE s.snapshot_date=? AND s.market_price_usd IS NOT NULL
             AND (SELECT COUNT(DISTINCT x.id_product) FROM cardtrader_blueprint_map x
                  WHERE x.blueprint_id=b.blueprint_id)=1""",
        (today.isoformat(),),
    ).fetchall()
    # Avoid publishing multiple variant rows for a CM product. Only publish when all
    # today's rows resolve to one distinct market value after the reference guard.
    grouped: dict[int, set[float]] = defaultdict(set)
    for row in rows:
        grouped[int(row["id_product"])].add(round(float(row["market_price_usd"]), 8))
    inserted = 0
    for cm_id, values in grouped.items():
        if len(values) != 1:
            continue
        eur = next(iter(values)) * fx
        cur = conn.execute(
            """INSERT OR IGNORE INTO model_market_observations(
                 observed_date,id_product,scope,source,value_eur,evidence_quality,sample_count,meta_json
               ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                today.isoformat(), cm_id, "US", "TCGCSV_MARKET_PRICE_PROXY", round(eur, 4),
                "PROXY", 1, json.dumps({"fx_source": "config_fallback", "source": "TCGCSV"}),
            ),
        )
        inserted += max(0, cur.rowcount)
    conn.commit()
    return inserted


def refresh_tcgcsv_reference(conn, cfg: dict, current_paths: list[Path], reference_path: Path,
                              output_reference_path: Path, audit_path: Path, *, today: date,
                              client: TCGCSVClient | None = None) -> dict:
    """Refresh exact-id TCGCSV/TCGplayer market-price references for tracked cards."""
    tcfg = cfg.get("tcgcsv", {})
    if not bool(tcfg.get("enabled", True)):
        return {"enabled": False, "reason": "disabled in config"}

    ensure_tcgcsv_schema(conn)
    tracking_days = int(tcfg.get("tracking_days", 190))
    target_ids = _target_cardmarket_ids(conn, current_paths, today, tracking_days)
    names = _card_names(conn, target_ids)
    exact_map, rejected_map = _exact_ct_tcgplayer_mapping(conn, target_ids)
    tcg_ids = {int(v["tcgplayer_product_id"]) for v in exact_map.values()}

    if not target_ids:
        _write_csv(output_reference_path, [], TCGCSV_REFERENCE_FIELDS)
        _write_csv(audit_path, [], AUDIT_FIELDS)
        return {"enabled": True, "targets": 0, "reference_rows": 0, "reason": "no tracked cards"}

    if client is None:
        client = TCGCSVClient(
            str(tcfg.get("base_url") or "https://tcgcsv.com/tcgplayer"),
            category_id=int(tcfg.get("category_id", 3)),
            delay_seconds=float(tcfg.get("request_delay_seconds", 0.25)),
            timeout_seconds=int(tcfg.get("timeout_seconds", 30)),
            user_agent=str(tcfg.get("user_agent") or "pokemon-deal-scanner/0.12 (+personal research)"),
        )

    known = _known_groups(conn, tcg_ids)
    missing = tcg_ids - set(known)
    discovery_status = {"groups_endpoint": 0, "product_group_requests": 0, "products_cached": 0, "unresolved": len(missing)}
    provider_error = ""
    if missing:
        try:
            discovery_status = _discover_missing_products(
                conn, client, missing, today,
                int(tcfg.get("max_catalog_group_requests_per_run", 250)),
            )
            known = _known_groups(conn, tcg_ids)
        except Exception as exc:
            provider_error = f"catalog discovery failed: {exc}"

    price_rows_by_product: dict[int, list[dict]] = defaultdict(list)
    price_group_requests = 0
    price_rows_stored = 0
    group_errors: list[str] = []
    groups_needed = sorted({int(v["group_id"]) for v in known.values() if v.get("group_id") is not None})
    if not provider_error:
        for group_id in groups_needed:
            group_targets = {pid for pid, meta in known.items() if int(meta["group_id"]) == group_id}
            try:
                rows = client.prices(group_id)
                price_group_requests += 1
                price_rows_stored += _upsert_prices(
                    conn, group_id, rows, today.isoformat(), restrict_to=group_targets
                )
                for row in rows:
                    pid = _int(row.get("productId"))
                    if pid in group_targets:
                        price_rows_by_product[int(pid)].append(dict(row))
            except Exception as exc:
                group_errors.append(f"{group_id}: {exc}")

    # If the API call failed for a group but today's rows already exist (e.g. retry of
    # the same scanner date), recover them from SQLite instead of discarding data.
    for tcg_id in tcg_ids:
        if price_rows_by_product.get(tcg_id):
            continue
        rows = conn.execute(
            """SELECT tcgplayer_product_id AS productId,subtype_name AS subTypeName,
                      low_price_usd AS lowPrice,mid_price_usd AS midPrice,
                      high_price_usd AS highPrice,market_price_usd AS marketPrice,
                      direct_low_price_usd AS directLowPrice
               FROM tcgcsv_price_snapshots
               WHERE snapshot_date=? AND tcgplayer_product_id=?""",
            (today.isoformat(), tcg_id),
        ).fetchall()
        price_rows_by_product[tcg_id] = [dict(r) for r in rows]

    references: list[dict] = []
    detail_rows: list[dict] = []
    audit_rows: list[dict] = []
    for cm_id in sorted(target_ids):
        mapping = exact_map.get(cm_id)
        if mapping is None:
            note = rejected_map.get(cm_id, "No exact CardTrader tcg_player_id mapping cached")
            audit_rows.append({
                "snapshot_date": today.isoformat(), "id_product": cm_id, "name": names.get(cm_id, ""),
                "status": "NO_EXACT_TCGPLAYER_MAP", "notes": note,
            })
            continue
        tcg_id = int(mapping["tcgplayer_product_id"])
        product_meta = known.get(tcg_id)
        if product_meta is None:
            audit_rows.append({
                "snapshot_date": today.isoformat(), "id_product": cm_id, "name": names.get(cm_id, ""),
                "tcgplayer_product_id": tcg_id,
                "cardtrader_blueprints": ";".join(map(str, mapping["blueprints"])),
                "version_hint": mapping["version_hint"], "status": "TCGCSV_PRODUCT_NOT_FOUND",
                "notes": provider_error or "TCGplayer product id was not located in scanned Pokemon groups",
            })
            continue
        price_rows = price_rows_by_product.get(tcg_id, [])
        selected, selection_status, selection_note = choose_subtype(price_rows, mapping["version_hint"])
        subtypes = ";".join(sorted({str(r.get("subTypeName") or "") for r in price_rows}))
        base_audit = {
            "snapshot_date": today.isoformat(), "id_product": cm_id, "name": names.get(cm_id, ""),
            "tcgplayer_product_id": tcg_id, "group_id": product_meta.get("group_id"),
            "group_name": product_meta.get("group_name") or "",
            "cardtrader_blueprints": ";".join(map(str, mapping["blueprints"])),
            "version_hint": mapping["version_hint"], "subtypes_seen": subtypes,
        }
        if selected is None:
            audit_rows.append({**base_audit, "status": selection_status, "notes": selection_note})
            continue
        market_price = _num(selected.get("marketPrice"))
        if market_price is None or market_price <= 0:
            audit_rows.append({**base_audit, "status": "NO_MARKET_PRICE", "notes": "selected subtype has null/invalid Market Price"})
            continue

        references.append(_reference_row(
            cm_id, names.get(cm_id, ""), tcg_id, selected, today,
            str(tcfg.get("reference_strength") or "MEDIUM"), selection_note,
        ))
        detail_rows.append({
            "snapshot_date": today.isoformat(), "id_product": cm_id, "name": names.get(cm_id, ""),
            "tcgplayer_product_id": tcg_id, "group_id": product_meta.get("group_id"),
            "group_name": product_meta.get("group_name") or "",
            "subtype_name": selected.get("subTypeName") or "",
            "market_price_usd": selected.get("marketPrice") if selected.get("marketPrice") is not None else "",
            "low_price_usd": selected.get("lowPrice") if selected.get("lowPrice") is not None else "",
            "mid_price_usd": selected.get("midPrice") if selected.get("midPrice") is not None else "",
            "high_price_usd": selected.get("highPrice") if selected.get("highPrice") is not None else "",
            "direct_low_price_usd": selected.get("directLowPrice") if selected.get("directLowPrice") is not None else "",
            "mapping_status": selection_status, "mapping_note": selection_note,
        })
        audit_rows.append({**base_audit, "status": "REFERENCE_READY", "notes": selection_note})

    # The normalized TCGplayer reference is deliberately current-universe only.
    # Historical TCGCSV prices are durable in SQLite, so stale rows do not leak into
    # today's US fair value just because a card used to be tracked.
    _write_csv(reference_path, references, REFERENCE_FIELDS)
    _write_csv(output_reference_path, detail_rows, TCGCSV_REFERENCE_FIELDS)
    _write_csv(audit_path, audit_rows, AUDIT_FIELDS)

    return {
        "enabled": True,
        "source": "TCGCSV",
        "targets": len(target_ids),
        "exact_ct_tcgplayer_mappings": len(exact_map),
        "mapping_rejections": len(rejected_map),
        "tcgplayer_ids": len(tcg_ids),
        "catalog_discovery": discovery_status,
        "price_group_requests": price_group_requests,
        "price_rows_stored": price_rows_stored,
        "reference_rows": len(references),
        "ambiguous_or_unusable": len(audit_rows) - len(references),
        "provider_error": provider_error,
        "group_errors": group_errors[:10],
        "reference_output": str(reference_path),
        "audit_output": str(audit_path),
    }
