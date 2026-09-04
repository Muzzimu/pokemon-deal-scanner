from __future__ import annotations

import csv
import math
from pathlib import Path


RATING_BASE = {
    "outstanding": 100.0,
    "very good": 88.0,
    "good": 75.0,
    "average": 65.0,
    "unrated": 60.0,
    "new": 60.0,
    "bad": 20.0,
    "red": 20.0,
}

OUTPUT_FIELDS = [
    "id_product", "name", "expansion_name", "number",
    "article_price_eur", "shipping_total_eur", "shipping_allocation_eur",
    "allocated_landed_cost_eur", "seller", "seller_rating", "seller_sales",
    "seller_confidence", "seller_risk_penalty_eur", "risk_adjusted_article_eur",
    "risk_adjusted_landed_eur", "ships_to_ireland", "language", "condition",
    "decision", "eligibility_reason", "checked_at", "source", "notes",
]


def _float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _yes(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _rating_key(rating: str | None) -> str:
    value = str(rating or "").strip().lower().replace("_", " ")
    if "outstanding" in value:
        return "outstanding"
    if "very good" in value:
        return "very good"
    if value == "good" or value.startswith("good "):
        return "good"
    if "bad" in value or "red" in value:
        return "bad"
    if "unrated" in value or "new" in value or not value:
        return "unrated"
    return "average"


def seller_confidence(rating: str | None, sales: int | str | None) -> float:
    """Combine rating quality with confidence supplied by transaction history."""
    base = RATING_BASE[_rating_key(rating)]
    n = max(0, _int(sales))
    volume_factor = min(math.log10(n + 1) / 4.0, 1.0)
    return round(max(0.0, min(100.0, base * (0.85 + 0.15 * volume_factor))), 1)


def read_sourcing_offers(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _product_lookup(conn, product_id: int) -> dict:
    row = conn.execute(
        "SELECT id_product,name,expansion_name,number FROM products WHERE id_product=?",
        (product_id,),
    ).fetchone()
    return dict(row) if row else {
        "id_product": product_id,
        "name": "UNKNOWN_PRODUCT",
        "expansion_name": None,
        "number": None,
    }


def analyze_sourcing_offers(conn, cfg: dict, rows: list[dict]) -> list[dict]:
    out = []
    required_language = str(cfg.get("sourcing", {}).get("required_language", "en")).lower()
    required_condition = str(cfg.get("sourcing", {}).get("required_condition", "NM")).lower().replace("_", " ")
    max_penalty = float(cfg.get("sourcing", {}).get("seller_risk_max_penalty_eur", 1.50))
    dragonite_cfg = cfg["watchlists"]["dragonite"]
    standalone_max = float(dragonite_cfg["standalone_buy_max_landed_eur"])
    bundle_max = float(dragonite_cfg["bundle_buy_max_landed_eur"])

    for raw in rows:
        try:
            pid = int(raw.get("id_product") or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue

        product = _product_lookup(conn, pid)
        article = _float(raw.get("article_price_eur"))
        shipping_total = _float(raw.get("shipping_total_eur"))
        shipping_alloc = _float(raw.get("shipping_allocation_eur"))
        sales = _int(raw.get("seller_sales"))
        confidence = seller_confidence(raw.get("seller_rating"), sales)
        risk_penalty = round(max_penalty * (1.0 - confidence / 100.0), 2)

        language = str(raw.get("language") or "").strip().lower()
        condition = str(raw.get("condition") or "").strip().lower().replace("_", " ")
        ships_ie = _yes(raw.get("ships_to_ireland"))

        reasons = []
        accepted_languages = {required_language}
        if required_language == "en":
            accepted_languages.add("english")
        accepted_conditions = {required_condition}
        if required_condition == "nm":
            accepted_conditions.add("near mint")
        if language not in accepted_languages:
            reasons.append("NOT_ENGLISH")
        if condition not in accepted_conditions:
            reasons.append("NOT_NM")
        if not ships_ie:
            reasons.append("NO_IRELAND_SHIPPING")
        if article is None:
            reasons.append("NO_ARTICLE_PRICE")

        landed = None if article is None or shipping_alloc is None else round(article + shipping_alloc, 2)
        risk_article = None if article is None else round(article + risk_penalty, 2)
        risk_landed = None if landed is None else round(landed + risk_penalty, 2)

        if reasons:
            decision = "INELIGIBLE"
        elif landed is None:
            decision = "VERIFY_LANDED"
            reasons.append("SHIPPING_COST_NOT_CONFIRMED")
        elif dragonite_cfg["query"].lower() in str(product["name"]).lower():
            if risk_landed <= standalone_max:
                decision = "STANDALONE_BUY"
            elif risk_landed <= bundle_max:
                decision = "BUNDLE_BUY"
            else:
                decision = "WAIT"
        else:
            decision = "VALIDATED_SOURCE"

        out.append({
            **product,
            "article_price_eur": article,
            "shipping_total_eur": shipping_total,
            "shipping_allocation_eur": shipping_alloc,
            "allocated_landed_cost_eur": landed,
            "seller": raw.get("seller") or "",
            "seller_rating": raw.get("seller_rating") or "",
            "seller_sales": sales,
            "seller_confidence": confidence,
            "seller_risk_penalty_eur": risk_penalty,
            "risk_adjusted_article_eur": risk_article,
            "risk_adjusted_landed_eur": risk_landed,
            "ships_to_ireland": ships_ie,
            "language": raw.get("language") or "",
            "condition": raw.get("condition") or "",
            "decision": decision,
            "eligibility_reason": "|".join(reasons) if reasons else "ELIGIBLE",
            "checked_at": raw.get("checked_at") or "",
            "source": raw.get("source") or "manual",
            "notes": raw.get("notes") or "",
        })

    order = {
        "STANDALONE_BUY": 0,
        "BUNDLE_BUY": 1,
        "VERIFY_LANDED": 2,
        "VALIDATED_SOURCE": 3,
        "WAIT": 4,
        "INELIGIBLE": 5,
    }
    return sorted(out, key=lambda r: (
        order.get(r["decision"], 99),
        r["risk_adjusted_landed_eur"] if r["risk_adjusted_landed_eur"] is not None else 9999,
        r["risk_adjusted_article_eur"] if r["risk_adjusted_article_eur"] is not None else 9999,
    ))


def write_sourcing_report(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def generate_cardmarket_sourcing_report(conn, cfg: dict, reference_path: Path, output_path: Path) -> dict:
    rows = analyze_sourcing_offers(conn, cfg, read_sourcing_offers(reference_path))
    write_sourcing_report(output_path, rows)
    return {
        "evidence_rows": len(rows),
        "eligible_en_nm_ireland": sum(1 for r in rows if r["decision"] != "INELIGIBLE"),
        "confirmed_landed_rows": sum(1 for r in rows if r["allocated_landed_cost_eur"] is not None and r["decision"] != "INELIGIBLE"),
        "standalone_buy_rows": sum(1 for r in rows if r["decision"] == "STANDALONE_BUY"),
        "bundle_buy_rows": sum(1 for r in rows if r["decision"] == "BUNDLE_BUY"),
        "verify_landed_rows": sum(1 for r in rows if r["decision"] == "VERIFY_LANDED"),
        "ineligible_rows": sum(1 for r in rows if r["decision"] == "INELIGIBLE"),
    }
