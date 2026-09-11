from __future__ import annotations

import csv
import sqlite3
from datetime import date
from pathlib import Path

from deal_scanner.tcgcsv import (
    choose_subtype,
    ensure_tcgcsv_schema,
    refresh_tcgcsv_reference,
    sync_tcgplayer_ids_from_blueprints,
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE products (
            id_product INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE cardtrader_blueprints (
            blueprint_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            expansion_id INTEGER,
            expansion_name TEXT,
            version TEXT,
            collector_number TEXT,
            card_market_ids_json TEXT,
            updated_at TEXT
        );
        CREATE TABLE cardtrader_blueprint_map (
            blueprint_id INTEGER NOT NULL,
            id_product INTEGER NOT NULL,
            mapped_at TEXT NOT NULL,
            PRIMARY KEY (blueprint_id,id_product)
        );
        """
    )
    return conn


def test_schema_and_cardtrader_exact_tcgplayer_id_bridge():
    conn = _conn()
    conn.execute(
        "INSERT INTO cardtrader_blueprints(blueprint_id,name,version) VALUES(?,?,?)",
        (101, "Dragonite ex", "Ultra Rare | 152/217"),
    )
    ensure_tcgcsv_schema(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(cardtrader_blueprints)")}
    assert "tcgplayer_product_id" in columns

    count = sync_tcgplayer_ids_from_blueprints(conn, [{"id": 101, "tcg_player_id": 999001}])
    assert count == 1
    row = conn.execute(
        "SELECT tcgplayer_product_id FROM cardtrader_blueprints WHERE blueprint_id=101"
    ).fetchone()
    assert row["tcgplayer_product_id"] == 999001


def test_subtype_guard_refuses_unresolved_variant():
    rows = [
        {"productId": 1, "subTypeName": "Holofoil", "marketPrice": 10.0},
        {"productId": 1, "subTypeName": "Reverse Holofoil", "marketPrice": 4.0},
    ]
    selected, status, _ = choose_subtype(rows, "Rare | 10/100")
    assert selected is None
    assert status == "AMBIGUOUS_SUBTYPE"

    selected, status, _ = choose_subtype(rows, "Reverse Holo Rare | 10/100")
    assert selected is not None
    assert selected["subTypeName"] == "Reverse Holofoil"
    assert status == "VERSION_HINT"


class FakeTCGCSVClient:
    def groups(self):
        return [{
            "groupId": 7000,
            "name": "Test Pokemon Set",
            "abbreviation": "TST",
            "publishedOn": "2026-01-01T00:00:00",
            "modifiedOn": "2026-09-11T00:00:00",
        }]

    def products(self, group_id: int):
        assert group_id == 7000
        return [{
            "productId": 900001,
            "name": "Test Dragonite ex",
            "groupId": 7000,
            "modifiedOn": "2026-09-11T00:00:00",
            "extendedData": [
                {"name": "Number", "value": "152"},
                {"name": "Rarity", "value": "Ultra Rare"},
            ],
        }]

    def prices(self, group_id: int):
        assert group_id == 7000
        return [{
            "productId": 900001,
            "lowPrice": 4.25,
            "midPrice": 5.40,
            "highPrice": 12.00,
            "marketPrice": 5.10,
            "directLowPrice": 5.25,
            "subTypeName": "Holofoil",
        }]


def test_refresh_builds_current_reference_without_faking_executable_depth(tmp_path: Path):
    conn = _conn()
    ensure_tcgcsv_schema(conn)
    conn.execute("INSERT INTO products(id_product,name) VALUES(?,?)", (869763, "Mega Dragonite ex"))
    conn.execute(
        """INSERT INTO cardtrader_blueprints(
             blueprint_id,name,version,tcgplayer_product_id
           ) VALUES(?,?,?,?)""",
        (370790, "Mega Dragonite ex", "Ultra Rare | 152/217", 900001),
    )
    conn.execute(
        "INSERT INTO cardtrader_blueprint_map(blueprint_id,id_product,mapped_at) VALUES(?,?,?)",
        (370790, 869763, "2026-09-11"),
    )
    conn.commit()

    routes = tmp_path / "market_routes.csv"
    with routes.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id_product"])
        writer.writeheader()
        writer.writerow({"id_product": 869763})

    reference = tmp_path / "tcgplayer_market_reference.csv"
    details = tmp_path / "tcgcsv_market_reference.csv"
    audit = tmp_path / "tcgcsv_mapping_audit.csv"
    cfg = {
        "tcgcsv": {
            "enabled": True,
            "max_catalog_group_requests_per_run": 250,
            "reference_strength": "MEDIUM",
        }
    }

    status = refresh_tcgcsv_reference(
        conn, cfg, [routes], reference, details, audit,
        today=date(2026, 9, 11), client=FakeTCGCSVClient(),
    )
    assert status["reference_rows"] == 1
    assert status["exact_ct_tcgplayer_mappings"] == 1

    with reference.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["id_product"] == "869763"
    assert row["tcgplayer_product_id"] == "900001"
    assert row["market_price_usd"] == "5.1"
    assert row["low_price_usd"] == "4.25"
    assert row["lowest_listing_price_usd"] == ""
    assert row["executable_floor_usd"] == ""
    assert row["source"] == "TCGCSV"

    snapshot = conn.execute(
        """SELECT market_price_usd,low_price_usd,subtype_name
           FROM tcgcsv_price_snapshots
           WHERE snapshot_date='2026-09-11' AND tcgplayer_product_id=900001"""
    ).fetchone()
    assert snapshot["market_price_usd"] == 5.10
    assert snapshot["low_price_usd"] == 4.25
    assert snapshot["subtype_name"] == "Holofoil"
