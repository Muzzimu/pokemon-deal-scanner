from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS products (
    id_product INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category_name TEXT,
    expansion_name TEXT,
    number TEXT,
    rarity TEXT,
    date_added TEXT,
    last_seen_catalog TEXT
);

CREATE TABLE IF NOT EXISTS price_snapshots (
    snapshot_date TEXT NOT NULL,
    id_product INTEGER NOT NULL,
    low REAL,
    trend REAL,
    avg1 REAL,
    avg7 REAL,
    avg30 REAL,
    foil_sell REAL,
    foil_low REAL,
    foil_trend REAL,
    foil_avg1 REAL,
    foil_avg7 REAL,
    foil_avg30 REAL,
    source_created_at TEXT,
    PRIMARY KEY (snapshot_date, id_product),
    FOREIGN KEY (id_product) REFERENCES products(id_product)
);

CREATE TABLE IF NOT EXISTS cardmarket_en_nm_overrides (
    id_product INTEGER PRIMARY KEY,
    en_nm_floor_eur REAL NOT NULL,
    checked_at TEXT NOT NULL,
    source TEXT,
    notes TEXT,
    FOREIGN KEY (id_product) REFERENCES products(id_product)
);

CREATE TABLE IF NOT EXISTS cardtrader_blueprints (
    blueprint_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    expansion_id INTEGER,
    expansion_name TEXT,
    version TEXT,
    collector_number TEXT,
    card_market_ids_json TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS cardtrader_blueprint_map (
    blueprint_id INTEGER NOT NULL,
    id_product INTEGER NOT NULL,
    mapped_at TEXT NOT NULL,
    PRIMARY KEY (blueprint_id, id_product),
    FOREIGN KEY (id_product) REFERENCES products(id_product)
);

CREATE TABLE IF NOT EXISTS cardtrader_offer_snapshots (
    snapshot_date TEXT NOT NULL,
    blueprint_id INTEGER NOT NULL,
    offer_id INTEGER NOT NULL,
    id_product INTEGER,
    seller_id INTEGER,
    seller_username TEXT,
    seller_country TEXT,
    quantity INTEGER,
    price_eur REAL,
    language TEXT,
    condition TEXT,
    graded INTEGER,
    on_vacation INTEGER,
    ct_zero INTEGER,
    PRIMARY KEY (snapshot_date, offer_id)
);

CREATE TABLE IF NOT EXISTS source_sync_state (
    source TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_price_snapshots_product_date
    ON price_snapshots(id_product, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_ct_map_product
    ON cardtrader_blueprint_map(id_product);
CREATE INDEX IF NOT EXISTS idx_ct_offers_product_date
    ON cardtrader_offer_snapshots(id_product, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_ct_offers_seller_date
    ON cardtrader_offer_snapshots(seller_id, snapshot_date);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def _pick(row: dict, *keys, default=None):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def upsert_products(conn: sqlite3.Connection, rows: Iterable[dict], seen_date: str) -> int:
    values = []
    for row in rows:
        pid = _pick(row, "idProduct", "id_product", "id")
        name = _pick(row, "name", "productName", "product_name")
        if pid is None or not name:
            continue
        values.append((
            int(pid), str(name),
            _pick(row, "categoryName", "category_name"),
            _pick(row, "expansionName", "expansion_name", "setName", "set_name"),
            str(_pick(row, "number", "collectorNumber", "collector_number", default="") or ""),
            _pick(row, "rarity"), _pick(row, "dateAdded", "date_added"), seen_date,
        ))
    conn.executemany(
        """
        INSERT INTO products(id_product,name,category_name,expansion_name,number,rarity,date_added,last_seen_catalog)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(id_product) DO UPDATE SET
          name=excluded.name, category_name=excluded.category_name,
          expansion_name=excluded.expansion_name, number=excluded.number,
          rarity=COALESCE(excluded.rarity, products.rarity),
          date_added=COALESCE(excluded.date_added, products.date_added),
          last_seen_catalog=excluded.last_seen_catalog
        """, values
    )
    conn.commit()
    return len(values)


def insert_price_snapshot(conn: sqlite3.Connection, rows: Iterable[dict], snapshot_date: str,
                          source_created_at: str | None) -> int:
    values = []
    for row in rows:
        pid = _pick(row, "idProduct", "id_product", "id")
        if pid is None:
            continue
        def num(*keys):
            x = _pick(row, *keys)
            try:
                return None if x in (None, "") else float(x)
            except (TypeError, ValueError):
                return None
        values.append((
            snapshot_date, int(pid), num("low"), num("trend"), num("avg1"), num("avg7"), num("avg30"),
            num("foilSell", "foil_sell"), num("foilLow", "foil_low"), num("foilTrend", "foil_trend"),
            num("foilAvg1", "foil_avg1"), num("foilAvg7", "foil_avg7"), num("foilAvg30", "foil_avg30"),
            source_created_at,
        ))
    conn.executemany(
        """
        INSERT INTO price_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(snapshot_date,id_product) DO UPDATE SET
          low=excluded.low, trend=excluded.trend, avg1=excluded.avg1, avg7=excluded.avg7, avg30=excluded.avg30,
          foil_sell=excluded.foil_sell, foil_low=excluded.foil_low, foil_trend=excluded.foil_trend,
          foil_avg1=excluded.foil_avg1, foil_avg7=excluded.foil_avg7, foil_avg30=excluded.foil_avg30,
          source_created_at=excluded.source_created_at
        """, values
    )
    conn.commit()
    return len(values)


def load_en_nm_overrides(conn: sqlite3.Connection, csv_path: Path) -> int:
    import csv
    if not csv_path.exists():
        return 0
    values = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("id_product") or not row.get("en_nm_floor_eur"):
                continue
            values.append((
                int(row["id_product"]), float(row["en_nm_floor_eur"]),
                row.get("checked_at") or "", row.get("source") or "manual",
                row.get("notes") or "",
            ))
    conn.executemany(
        """
        INSERT INTO cardmarket_en_nm_overrides(id_product,en_nm_floor_eur,checked_at,source,notes)
        VALUES(?,?,?,?,?)
        ON CONFLICT(id_product) DO UPDATE SET
          en_nm_floor_eur=excluded.en_nm_floor_eur, checked_at=excluded.checked_at,
          source=excluded.source, notes=excluded.notes
        """, values
    )
    conn.commit()
    return len(values)


def latest_snapshot_date(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(snapshot_date) AS d FROM price_snapshots").fetchone()
    return row["d"] if row and row["d"] else None


def set_sync_state(conn: sqlite3.Connection, source: str, value: str, updated_at: str) -> None:
    conn.execute(
        """INSERT INTO source_sync_state(source,value,updated_at) VALUES(?,?,?)
           ON CONFLICT(source) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
        (source, value, updated_at),
    )
    conn.commit()


def get_sync_state(conn: sqlite3.Connection, source: str) -> str | None:
    row = conn.execute("SELECT value FROM source_sync_state WHERE source=?", (source,)).fetchone()
    return row["value"] if row else None


def upsert_cardtrader_blueprints(conn: sqlite3.Connection, blueprints: Iterable[dict], *,
                                 expansion_id: int | None, expansion_name: str | None,
                                 updated_at: str) -> tuple[int, int]:
    import json
    bp_values = []
    map_values = []
    for bp in blueprints:
        bid = bp.get("id")
        name = bp.get("name")
        if bid is None or not name:
            continue
        version = bp.get("version")
        collector = bp.get("collector_number") or bp.get("number") or bp.get("collectorNumber")
        cm_ids = bp.get("card_market_ids") or bp.get("cardmarket_ids") or []
        if isinstance(cm_ids, int):
            cm_ids = [cm_ids]
        if not isinstance(cm_ids, list):
            cm_ids = []
        bp_values.append((
            int(bid), str(name), expansion_id, expansion_name,
            None if version is None else str(version),
            None if collector is None else str(collector),
            json.dumps(cm_ids), updated_at,
        ))
        for pid in cm_ids:
            try:
                pid = int(pid)
            except (TypeError, ValueError):
                continue
            map_values.append((int(bid), pid, updated_at))
    conn.executemany(
        """
        INSERT INTO cardtrader_blueprints(blueprint_id,name,expansion_id,expansion_name,version,collector_number,card_market_ids_json,updated_at)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(blueprint_id) DO UPDATE SET
          name=excluded.name, expansion_id=excluded.expansion_id, expansion_name=excluded.expansion_name,
          version=excluded.version, collector_number=excluded.collector_number,
          card_market_ids_json=excluded.card_market_ids_json, updated_at=excluded.updated_at
        """, bp_values
    )
    valid_ids = {r["id_product"] for r in conn.execute("SELECT id_product FROM products")}
    filtered = [r for r in map_values if r[1] in valid_ids]
    conn.executemany(
        """INSERT INTO cardtrader_blueprint_map(blueprint_id,id_product,mapped_at) VALUES(?,?,?)
           ON CONFLICT(blueprint_id,id_product) DO UPDATE SET mapped_at=excluded.mapped_at""",
        filtered,
    )
    conn.commit()
    return len(bp_values), len(filtered)


def cardtrader_mapping_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) AS n FROM cardtrader_blueprint_map").fetchone()["n"])


def expansion_ids_for_products(conn: sqlite3.Connection, product_ids: list[int]) -> list[int]:
    if not product_ids:
        return []
    q = ",".join("?" for _ in product_ids)
    rows = conn.execute(
        f"""SELECT DISTINCT b.expansion_id
             FROM cardtrader_blueprint_map m
             JOIN cardtrader_blueprints b ON b.blueprint_id=m.blueprint_id
             WHERE m.id_product IN ({q}) AND b.expansion_id IS NOT NULL""", product_ids
    ).fetchall()
    return sorted({int(r["expansion_id"]) for r in rows})


def product_ids_for_expansion(conn: sqlite3.Connection, expansion_id: int) -> set[int]:
    rows = conn.execute(
        """SELECT DISTINCT m.id_product
           FROM cardtrader_blueprint_map m
           JOIN cardtrader_blueprints b ON b.blueprint_id=m.blueprint_id
           WHERE b.expansion_id=?""", (expansion_id,)
    ).fetchall()
    return {int(r["id_product"]) for r in rows}


def blueprint_product_map_for_expansion(conn: sqlite3.Connection, expansion_id: int) -> dict[int, list[int]]:
    rows = conn.execute(
        """SELECT m.blueprint_id,m.id_product
           FROM cardtrader_blueprint_map m
           JOIN cardtrader_blueprints b ON b.blueprint_id=m.blueprint_id
           WHERE b.expansion_id=?""", (expansion_id,)
    ).fetchall()
    out: dict[int, list[int]] = {}
    for r in rows:
        out.setdefault(int(r["blueprint_id"]), []).append(int(r["id_product"]))
    return out


def insert_cardtrader_offers(conn: sqlite3.Connection, offers: Iterable[dict], snapshot_date: str) -> int:
    values = []
    for o in offers:
        offer_id = o.get("offer_id") or o.get("id")
        blueprint_id = o.get("blueprint_id")
        if offer_id is None or blueprint_id is None:
            continue
        values.append((
            snapshot_date, int(blueprint_id), int(offer_id), o.get("id_product"),
            o.get("seller_id"), o.get("seller_username"), o.get("seller_country"),
            int(o.get("quantity") or 1), o.get("price_eur"), o.get("language"), o.get("condition"),
            int(bool(o.get("graded"))), int(bool(o.get("on_vacation"))), int(bool(o.get("ct_zero"))),
        ))
    conn.executemany(
        """
        INSERT INTO cardtrader_offer_snapshots(
          snapshot_date,blueprint_id,offer_id,id_product,seller_id,seller_username,seller_country,
          quantity,price_eur,language,condition,graded,on_vacation,ct_zero
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(snapshot_date,offer_id) DO UPDATE SET
          id_product=excluded.id_product, seller_id=excluded.seller_id,
          seller_username=excluded.seller_username, seller_country=excluded.seller_country,
          quantity=excluded.quantity, price_eur=excluded.price_eur,
          language=excluded.language, condition=excluded.condition,
          graded=excluded.graded, on_vacation=excluded.on_vacation, ct_zero=excluded.ct_zero
        """, values
    )
    conn.commit()
    return len(values)


def latest_cardtrader_snapshot_date(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(snapshot_date) AS d FROM cardtrader_offer_snapshots").fetchone()
    return row["d"] if row and row["d"] else None


def cardtrader_en_nm_summary(conn: sqlite3.Connection, snapshot_date: str) -> dict[int, dict]:
    rows = conn.execute(
        """
        SELECT id_product,
               MIN(price_eur) AS floor_eur,
               COUNT(*) AS visible_offer_rows,
               SUM(quantity) AS visible_units,
               COUNT(DISTINCT seller_id) AS visible_sellers,
               SUM(CASE WHEN ct_zero=1 THEN quantity ELSE 0 END) AS zero_units
        FROM cardtrader_offer_snapshots
        WHERE snapshot_date=?
          AND id_product IS NOT NULL
          AND language='en'
          AND lower(condition) IN ('near mint','near_mint','nm')
          AND graded=0 AND on_vacation=0
        GROUP BY id_product
        """, (snapshot_date,)
    ).fetchall()
    return {
        int(r["id_product"]): {
            "floor_eur": r["floor_eur"],
            "visible_offer_rows": r["visible_offer_rows"],
            "visible_units": r["visible_units"],
            "visible_sellers": r["visible_sellers"],
            "zero_units": r["zero_units"] or 0,
        } for r in rows
    }


def latest_rows_with_history(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    latest = latest_snapshot_date(conn)
    if not latest:
        return []
    return conn.execute(
        """
        WITH hist AS (
          SELECT id_product,
                 MIN(low) AS hist_low,
                 AVG(low) AS hist_avg_low,
                 AVG(low*low) AS hist_avg_sq,
                 COUNT(*) AS hist_days
          FROM price_snapshots
          WHERE snapshot_date >= date(?, '-29 day')
          GROUP BY id_product
        ), ct_latest AS (
          SELECT MAX(snapshot_date) AS d FROM cardtrader_offer_snapshots
        ), ct AS (
          SELECT id_product,
                 MIN(price_eur) AS ct_en_nm_floor,
                 SUM(quantity) AS ct_visible_units,
                 COUNT(DISTINCT seller_id) AS ct_visible_sellers,
                 SUM(CASE WHEN ct_zero=1 THEN quantity ELSE 0 END) AS ct_zero_units
          FROM cardtrader_offer_snapshots, ct_latest
          WHERE snapshot_date=ct_latest.d
            AND id_product IS NOT NULL
            AND language='en'
            AND lower(condition) IN ('near mint','near_mint','nm')
            AND graded=0 AND on_vacation=0
          GROUP BY id_product
        )
        SELECT p.*, s.snapshot_date, s.low, s.trend, s.avg1, s.avg7, s.avg30,
               h.hist_low, h.hist_avg_low, h.hist_avg_sq, h.hist_days,
               o.en_nm_floor_eur AS cm_en_nm_floor, o.checked_at AS cm_en_nm_checked_at,
               ct.ct_en_nm_floor, ct.ct_visible_units, ct.ct_visible_sellers, ct.ct_zero_units
        FROM price_snapshots s
        JOIN products p ON p.id_product=s.id_product
        LEFT JOIN hist h ON h.id_product=s.id_product
        LEFT JOIN cardmarket_en_nm_overrides o ON o.id_product=s.id_product
        LEFT JOIN ct ON ct.id_product=s.id_product
        WHERE s.snapshot_date=?
        """, (latest, latest)
    ).fetchall()


def product_ids_for_candidate_query(conn: sqlite3.Connection, *, max_generic_low: float,
                                    names: list[str], max_rows: int) -> list[int]:
    latest = latest_snapshot_date(conn)
    if not latest:
        return []
    clauses = ["(s.low IS NOT NULL AND s.low <= ?)"]
    params: list = [max_generic_low]
    for name in names:
        clauses.append("lower(p.name) LIKE ?")
        params.append(f"%{name.lower()}%")
    params.extend([latest, max_rows])
    rows = conn.execute(
        f"""
        SELECT DISTINCT p.id_product,
               CASE WHEN s.low IS NULL THEN 999999 ELSE s.low END AS sort_low
        FROM products p
        JOIN price_snapshots s ON s.id_product=p.id_product
        WHERE ({' OR '.join(clauses)}) AND s.snapshot_date=?
        ORDER BY sort_low ASC
        LIMIT ?
        """, params
    ).fetchall()
    return [int(r["id_product"]) for r in rows]
