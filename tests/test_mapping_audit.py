from __future__ import annotations

import csv
from pathlib import Path

from deal_scanner.db import connect, insert_cardtrader_offers, upsert_cardtrader_blueprints, upsert_products
from deal_scanner.mapping_audit import apply_cardtrader_mapping_guard, build_mapping_audit


def _setup(tmp_path: Path):
    conn = connect(tmp_path / "mapping.sqlite")
    upsert_products(conn, [
        {"idProduct": 101, "name": "Pikachu ex", "expansionName": "Set A", "number": "076/078"},
        {"idProduct": 102, "name": "Pikachu ex", "expansionName": "Set B", "number": "076/078"},
        {"idProduct": 103, "name": "Dragonite V", "expansionName": "Pokemon GO", "number": "076/078"},
    ], "2026-09-11")
    upsert_cardtrader_blueprints(conn, [
        {"id": 5001, "name": "Dragonite V", "collector_number": "076/078", "card_market_ids": [103]},
        {"id": 5002, "name": "Pikachu ex", "collector_number": "076/078", "card_market_ids": [101, 102]},
    ], expansion_id=900, expansion_name="Demo", updated_at="2026-09-11T00:00:00Z")
    insert_cardtrader_offers(conn, [
        {"offer_id": 1, "blueprint_id": 5001, "id_product": 103, "seller_id": 1, "quantity": 1,
         "price_eur": 10.0, "language": "en", "condition": "Near Mint", "graded": False,
         "on_vacation": False, "ct_zero": True},
        # Simulate the pre-guard ambiguity problem: an offer has already been attached
        # to one arbitrary member of a multi-ID blueprint mapping.
        {"offer_id": 2, "blueprint_id": 5002, "id_product": 102, "seller_id": 2, "quantity": 1,
         "price_eur": 20.0, "language": "en", "condition": "Near Mint", "graded": False,
         "on_vacation": False, "ct_zero": True},
    ], "2026-09-11")
    return conn


def test_ambiguous_multi_mapping_is_blocked(tmp_path):
    conn = _setup(tmp_path)
    audit_path = tmp_path / "audit.csv"
    status = apply_cardtrader_mapping_guard(conn, "2026-09-11", None, audit_path)

    rows = {int(r["blueprint_id"]): r for r in build_mapping_audit(conn)}
    assert rows[5001]["mapping_status"] == "EXACT"
    assert int(rows[5001]["resolved_id_product"]) == 103
    assert rows[5002]["mapping_status"] == "AMBIGUOUS_MULTI"
    assert rows[5002]["resolved_id_product"] == ""

    offer = conn.execute(
        "SELECT id_product FROM cardtrader_offer_snapshots WHERE snapshot_date=? AND offer_id=2",
        ("2026-09-11",),
    ).fetchone()
    assert offer["id_product"] is None
    assert status["offers_blocked_from_ambiguous_mapping"] == 1
    assert status["snapshot_blueprints_guarded"] == 2
    assert audit_path.exists()


def test_verified_override_resolves_multi_mapping(tmp_path):
    conn = _setup(tmp_path)
    overrides = tmp_path / "overrides.csv"
    with overrides.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["blueprint_id", "id_product", "status", "reason", "checked_at"])
        w.writeheader()
        w.writerow({
            "blueprint_id": 5002,
            "id_product": 101,
            "status": "VERIFIED_MULTI",
            "reason": "manual exact-printing review",
            "checked_at": "2026-09-11",
        })

    audit_path = tmp_path / "audit.csv"
    status = apply_cardtrader_mapping_guard(conn, "2026-09-11", overrides, audit_path)
    rows = {int(r["blueprint_id"]): r for r in build_mapping_audit(conn, overrides)}

    assert rows[5002]["mapping_status"] == "VERIFIED_MULTI"
    assert int(rows[5002]["resolved_id_product"]) == 101
    offer = conn.execute(
        "SELECT id_product FROM cardtrader_offer_snapshots WHERE snapshot_date=? AND offer_id=2",
        ("2026-09-11",),
    ).fetchone()
    assert int(offer["id_product"]) == 101
    assert status["offers_reassigned_to_resolved_mapping"] == 1


def test_conflicting_override_is_blocked(tmp_path):
    conn = _setup(tmp_path)
    overrides = tmp_path / "overrides.csv"
    overrides.write_text(
        "blueprint_id,id_product,status,reason,checked_at\n5002,103,VERIFIED,bad override,2026-09-11\n",
        encoding="utf-8",
    )
    rows = {int(r["blueprint_id"]): r for r in build_mapping_audit(conn, overrides)}
    assert rows[5002]["mapping_status"] == "MAPPING_CONFLICT"
    assert rows[5002]["resolved_id_product"] == ""


def test_guard_only_changes_requested_snapshot(tmp_path):
    conn = _setup(tmp_path)
    insert_cardtrader_offers(conn, [
        {"offer_id": 2, "blueprint_id": 5002, "id_product": 102, "seller_id": 2, "quantity": 1,
         "price_eur": 19.0, "language": "en", "condition": "Near Mint", "graded": False,
         "on_vacation": False, "ct_zero": True},
    ], "2026-09-10")

    apply_cardtrader_mapping_guard(conn, "2026-09-11", None, tmp_path / "audit.csv")

    current = conn.execute(
        "SELECT id_product FROM cardtrader_offer_snapshots WHERE snapshot_date=? AND offer_id=2",
        ("2026-09-11",),
    ).fetchone()
    prior = conn.execute(
        "SELECT id_product FROM cardtrader_offer_snapshots WHERE snapshot_date=? AND offer_id=2",
        ("2026-09-10",),
    ).fetchone()
    assert current["id_product"] is None
    assert int(prior["id_product"]) == 102
