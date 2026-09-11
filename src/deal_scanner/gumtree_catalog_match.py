from __future__ import annotations

import csv
import re
from pathlib import Path

from deal_scanner.gumtree import OUTPUT_FIELDS


NUMBER_RE = re.compile(r"\b([A-Za-z]{0,4}\d{1,4})\s*/\s*([A-Za-z]{0,4}\d{1,4})\b")
HASH_RE = re.compile(r"(?:#|no\.?\s*)([A-Za-z]{0,4}\d{1,4})\b", re.I)
STOP_TOKENS = {
    "ex", "v", "vstar", "vmax", "gx", "mega", "the", "of", "forme",
    "pokemon", "card", "cards",
}


def _norm(value: str | None) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _number_candidates(text: str) -> set[str]:
    values = {m.group(1).upper() for m in NUMBER_RE.finditer(text or "")}
    values.update(m.group(1).upper() for m in HASH_RE.finditer(text or ""))
    return values


def _important_tokens(value: str | None) -> list[str]:
    return [
        token for token in _norm(value).split()
        if token not in STOP_TOKENS and len(token) >= 2 and not any(ch.isdigit() for ch in token)
    ]


def match_catalog_exact(conn, text: str) -> int | None:
    """Conservative auto-match requiring explicit number, Pokemon/card name and set."""
    blob = _norm(text)
    numbers = _number_candidates(text)
    if not numbers:
        return None
    matches = []
    for number in numbers:
        variants = {number.lower(), number.lstrip("0").lower() or "0"}
        placeholders = ",".join("?" for _ in variants)
        rows = conn.execute(
            f"""SELECT id_product,name,expansion_name,number FROM products
                WHERE lower(number) IN ({placeholders})""",
            tuple(sorted(variants)),
        ).fetchall()
        for row in rows:
            name_tokens = _important_tokens(row["name"])
            set_tokens = _important_tokens(row["expansion_name"])
            if not name_tokens or not set_tokens:
                continue
            if not all(re.search(rf"\b{re.escape(t)}\b", blob) for t in name_tokens):
                continue
            if not all(re.search(rf"\b{re.escape(t)}\b", blob) for t in set_tokens):
                continue
            matches.append(int(row["id_product"]))
    unique = sorted(set(matches))
    return unique[0] if len(unique) == 1 else None


def enrich_gumtree_catalog_matches(conn, path: Path) -> dict:
    if not path.exists():
        return {"rows": 0, "new_exact_matches": 0}
    with path.open(newline="", encoding="utf-8") as f:
        rows = [dict(r) for r in csv.DictReader(f)]
    added = 0
    for row in rows:
        if str(row.get("exact_match") or "").strip().lower() in {"1", "true", "yes"}:
            continue
        text = " ".join([row.get("title") or "", row.get("description") or ""])
        pid = match_catalog_exact(conn, text)
        if pid is None:
            continue
        product = conn.execute("SELECT name FROM products WHERE id_product=?", (pid,)).fetchone()
        row["id_product"] = pid
        row["product_name"] = str(product["name"]) if product else ""
        row["exact_match"] = 1
        row["identification_source"] = "catalog_name_set_number_unique"
        conn.execute(
            """UPDATE gumtree_listing_state
               SET id_product=?,exact_match=1,identification_source=?
               WHERE listing_id=?""",
            (pid, row["identification_source"], row.get("listing_id")),
        )
        added += 1
    conn.commit()
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return {"rows": len(rows), "new_exact_matches": added}
