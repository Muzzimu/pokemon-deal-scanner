from __future__ import annotations

import csv
import json
from pathlib import Path


AUDIT_FIELDS = [
    "blueprint_id",
    "name",
    "expansion_id",
    "expansion_name",
    "version",
    "collector_number",
    "raw_cardmarket_ids",
    "valid_cardmarket_ids",
    "valid_mapping_count",
    "collector_match_ids",
    "collector_match_count",
    "name_match_ids",
    "name_match_count",
    "override_id_product",
    "override_status",
    "mapping_status",
    "resolved_id_product",
    "mapped_product_names",
    "mapped_product_expansions",
    "mapped_product_numbers",
    "notes",
]


def _normalize_text(value) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _normalize_number(value) -> str:
    text = str(value or "").strip().lower().replace(" ", "")
    if not text:
        return ""
    # Keep slash-separated collector structure, but normalize leading zeros on
    # each numeric component where possible (076/078 -> 76/78).
    parts = text.split("/")
    out = []
    for part in parts:
        if part.isdigit():
            out.append(str(int(part)))
        else:
            out.append(part)
    return "/".join(out)


def _load_overrides(path: Path | None) -> dict[int, dict]:
    if path is None or not path.exists():
        return {}
    out: dict[int, dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                bid = int(row.get("blueprint_id") or 0)
                pid = int(row.get("id_product") or 0)
            except (TypeError, ValueError):
                continue
            status = str(row.get("status") or "").strip().upper()
            if bid <= 0 or pid <= 0 or status not in {"VERIFIED", "VERIFIED_MULTI", "EXACT_OVERRIDE"}:
                continue
            out[bid] = {
                "id_product": pid,
                "status": status,
                "reason": str(row.get("reason") or "").strip(),
                "checked_at": str(row.get("checked_at") or "").strip(),
            }
    return out


def _product_map(conn) -> dict[int, dict]:
    rows = conn.execute(
        "SELECT id_product,name,expansion_name,number FROM products"
    ).fetchall()
    return {
        int(r["id_product"]): {
            "name": r["name"] or "",
            "expansion_name": r["expansion_name"] or "",
            "number": r["number"] or "",
        }
        for r in rows
    }


def build_mapping_audit(conn, overrides_path: Path | None = None) -> list[dict]:
    """Classify current CardTrader -> Cardmarket blueprint mappings.

    The canonical mapping evidence is the *current* ``card_market_ids_json`` stored
    on the blueprint, not every historical row left in ``cardtrader_blueprint_map``.
    This prevents an old mapping from silently surviving a later CardTrader mapping
    change.

    Multi-ID mappings are intentionally ambiguous unless a human-reviewed override
    selects one of the currently advertised Cardmarket IDs.
    """
    products = _product_map(conn)
    overrides = _load_overrides(overrides_path)
    rows = conn.execute(
        """SELECT blueprint_id,name,expansion_id,expansion_name,version,
                  collector_number,card_market_ids_json
           FROM cardtrader_blueprints"""
    ).fetchall()

    audit: list[dict] = []
    for r in rows:
        bid = int(r["blueprint_id"])
        try:
            raw_ids = json.loads(r["card_market_ids_json"] or "[]")
        except (TypeError, json.JSONDecodeError):
            raw_ids = []
        if isinstance(raw_ids, int):
            raw_ids = [raw_ids]
        if not isinstance(raw_ids, list):
            raw_ids = []

        cleaned_raw: list[int] = []
        for value in raw_ids:
            try:
                pid = int(value)
            except (TypeError, ValueError):
                continue
            if pid not in cleaned_raw:
                cleaned_raw.append(pid)
        valid_ids = [pid for pid in cleaned_raw if pid in products]

        ct_number = _normalize_number(r["collector_number"])
        ct_name = _normalize_text(r["name"])
        collector_matches = [
            pid for pid in valid_ids
            if ct_number and _normalize_number(products[pid]["number"]) == ct_number
        ]
        name_matches = [
            pid for pid in valid_ids
            if ct_name and _normalize_text(products[pid]["name"]) == ct_name
        ]

        override = overrides.get(bid)
        override_pid = int(override["id_product"]) if override else None
        override_status = override["status"] if override else ""
        notes: list[str] = []
        resolved = None

        if len(valid_ids) == 0:
            status = "UNMAPPED"
            if cleaned_raw:
                notes.append("CardTrader IDs are absent from the current Cardmarket catalogue")
        elif len(valid_ids) == 1:
            sole = valid_ids[0]
            if override and override_pid != sole:
                status = "MAPPING_CONFLICT"
                notes.append("override disagrees with the single current CardTrader Cardmarket ID")
            else:
                status = "EXACT"
                resolved = sole
        else:
            if override and override_pid in valid_ids:
                status = "VERIFIED_MULTI"
                resolved = override_pid
                if override.get("reason"):
                    notes.append(override["reason"])
            elif override:
                status = "MAPPING_CONFLICT"
                notes.append("override ID is not one of the current CardTrader Cardmarket IDs")
            else:
                status = "AMBIGUOUS_MULTI"
                notes.append("multiple current Cardmarket IDs; excluded from arbitrage until manually resolved")
                if len(collector_matches) == 1:
                    notes.append(f"one collector-number candidate exists: {collector_matches[0]}")
                if len(name_matches) == 1:
                    notes.append(f"one exact normalized-name candidate exists: {name_matches[0]}")

        mapped = [products[pid] for pid in valid_ids]
        audit.append({
            "blueprint_id": bid,
            "name": r["name"] or "",
            "expansion_id": r["expansion_id"] if r["expansion_id"] is not None else "",
            "expansion_name": r["expansion_name"] or "",
            "version": r["version"] or "",
            "collector_number": r["collector_number"] or "",
            "raw_cardmarket_ids": ";".join(str(x) for x in cleaned_raw),
            "valid_cardmarket_ids": ";".join(str(x) for x in valid_ids),
            "valid_mapping_count": len(valid_ids),
            "collector_match_ids": ";".join(str(x) for x in collector_matches),
            "collector_match_count": len(collector_matches),
            "name_match_ids": ";".join(str(x) for x in name_matches),
            "name_match_count": len(name_matches),
            "override_id_product": override_pid or "",
            "override_status": override_status,
            "mapping_status": status,
            "resolved_id_product": resolved or "",
            "mapped_product_names": " | ".join(str(x["name"]) for x in mapped),
            "mapped_product_expansions": " | ".join(str(x["expansion_name"]) for x in mapped),
            "mapped_product_numbers": " | ".join(str(x["number"]) for x in mapped),
            "notes": "; ".join(notes),
        })

    rank = {
        "MAPPING_CONFLICT": 0,
        "AMBIGUOUS_MULTI": 1,
        "UNMAPPED": 2,
        "VERIFIED_MULTI": 3,
        "EXACT": 4,
    }
    audit.sort(key=lambda row: (rank.get(str(row["mapping_status"]), 9), str(row["name"]), int(row["blueprint_id"])))
    return audit


def write_mapping_audit(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def apply_cardtrader_mapping_guard(
    conn,
    snapshot_date: str | None,
    overrides_path: Path | None,
    audit_path: Path,
) -> dict:
    """Audit mappings and make ambiguous mappings non-actionable for a CT snapshot.

    ``normalize_marketplace`` can only work with the mapping table it receives.
    If a blueprint maps to more than one Cardmarket ID, a single CardTrader offer
    can otherwise be attached to an arbitrary variant. This post-sync guard resets
    every offer to the exact resolved ID derived from the blueprint's *current*
    CardTrader ``card_market_ids`` field, and NULLs ambiguous/conflicting mappings.
    NULL ``id_product`` offers remain stored for diagnostics but cannot contribute
    to Cardmarket/CardTrader arbitrage, seller baskets, or market floors.
    """
    rows = build_mapping_audit(conn, overrides_path)
    write_mapping_audit(audit_path, rows)

    counts: dict[str, int] = {}
    for row in rows:
        status = str(row["mapping_status"])
        counts[status] = counts.get(status, 0) + 1

    offers_resolved = 0
    offers_blocked = 0
    if snapshot_date:
        for row in rows:
            bid = int(row["blueprint_id"])
            resolved = row.get("resolved_id_product")
            if resolved not in (None, ""):
                cur = conn.execute(
                    """UPDATE cardtrader_offer_snapshots
                       SET id_product=?
                       WHERE snapshot_date=? AND blueprint_id=?
                         AND (id_product IS NULL OR id_product<>?)""",
                    (int(resolved), snapshot_date, bid, int(resolved)),
                )
                offers_resolved += max(0, int(cur.rowcount or 0))
            else:
                cur = conn.execute(
                    """UPDATE cardtrader_offer_snapshots
                       SET id_product=NULL
                       WHERE snapshot_date=? AND blueprint_id=? AND id_product IS NOT NULL""",
                    (snapshot_date, bid),
                )
                offers_blocked += max(0, int(cur.rowcount or 0))
        conn.commit()

    return {
        "snapshot_date": snapshot_date,
        "blueprints_audited": len(rows),
        "mapping_status_counts": counts,
        "offers_reassigned_to_resolved_mapping": offers_resolved,
        "offers_blocked_from_ambiguous_mapping": offers_blocked,
        "audit_path": str(audit_path),
        "policy": "Only EXACT or human VERIFIED_MULTI mappings can contribute to arbitrage outputs.",
    }
