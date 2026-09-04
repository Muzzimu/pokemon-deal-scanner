from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


def _eligible_offer_rows(conn, snapshot_date: str, max_unit_price: float):
    return conn.execute(
        """
        SELECT o.*, p.name, p.expansion_name, p.number, p.rarity
        FROM cardtrader_offer_snapshots o
        JOIN products p ON p.id_product=o.id_product
        WHERE o.snapshot_date=?
          AND o.id_product IS NOT NULL
          AND o.language='en'
          AND lower(o.condition) IN ('near mint','near_mint','nm')
          AND o.graded=0 AND o.on_vacation=0
          AND o.price_eur IS NOT NULL AND o.price_eur <= ?
        ORDER BY o.seller_id, o.price_eur, p.name
        """,
        (snapshot_date, max_unit_price),
    ).fetchall()


def build_seller_baskets(conn, snapshot_date: str | None, cfg: dict) -> list[dict]:
    if not snapshot_date:
        return []
    rules = cfg["seller_baskets"]
    rows = _eligible_offer_rows(conn, snapshot_date, float(rules["max_unit_price_eur"]))
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["seller_id"], r["seller_username"], r["seller_country"])].append(dict(r))

    out = []
    for (seller_id, username, country), offers in grouped.items():
        by_product = defaultdict(list)
        for o in offers:
            by_product[int(o["id_product"])].append(o)
        if len(by_product) < int(rules["min_distinct_hits"]):
            continue
        for pid in by_product:
            by_product[pid].sort(key=lambda x: x["price_eur"])

        # First buy one of each cheapest distinct hit, then spend remaining unit budget on
        # duplicates ordered by price. This preserves variety for kids' bundles.
        selected = []
        max_units = int(rules["max_units_per_seller"])
        max_copies = int(rules["max_copies_per_card"])
        for pid, opts in sorted(by_product.items(), key=lambda kv: kv[1][0]["price_eur"]):
            o = opts[0]
            selected.append({**o, "take_qty": 1})
            if len(selected) >= max_units:
                break

        units_used = sum(x["take_qty"] for x in selected)
        extra_candidates = []
        for pid, opts in by_product.items():
            remaining = max(0, max_copies - 1)
            for o in opts:
                if remaining <= 0:
                    break
                qty_available = int(o["quantity"] or 1)
                if o is opts[0]:
                    qty_available -= 1
                if qty_available <= 0:
                    continue
                q = min(qty_available, remaining)
                extra_candidates.append((o["price_eur"], pid, o, q))
                remaining -= q
        extra_candidates.sort(key=lambda x: x[0])
        for _, pid, o, available in extra_candidates:
            if units_used >= max_units:
                break
            take = min(available, max_units - units_used)
            if take:
                selected.append({**o, "take_qty": take})
                units_used += take

        # Merge selected lines for display.
        display_lines = defaultdict(lambda: {"qty": 0, "price": 0.0, "ct_zero": False})
        total = 0.0
        zero_units = 0
        for x in selected:
            qty = int(x["take_qty"])
            total += float(x["price_eur"]) * qty
            if x["ct_zero"]:
                zero_units += qty
            key = (x["id_product"], x["name"], x["price_eur"])
            display_lines[key]["qty"] += qty
            display_lines[key]["price"] = float(x["price_eur"])
            display_lines[key]["ct_zero"] = bool(x["ct_zero"])

        if units_used <= 0:
            continue
        planning_shipping = float(rules["planning_direct_shipping_eur"])
        target_landed = float(rules["target_landed_per_hit_eur"])
        max_shipping = max(0.0, target_landed * units_used - total)
        lines = []
        for (pid, name, price), d in sorted(display_lines.items(), key=lambda kv: kv[0][2]):
            z = " [Zero]" if d["ct_zero"] else ""
            lines.append(f"{name} x{d['qty']} @ €{price:.2f}{z}")
        out.append({
            "seller_id": seller_id,
            "seller": username,
            "country": country,
            "distinct_hits": len(by_product),
            "units_selected": units_used,
            "article_cost_eur": round(total, 2),
            "avg_article_cost_eur": round(total / units_used, 3),
            "planning_shipping_eur": planning_shipping,
            "planning_landed_total_eur": round(total + planning_shipping, 2),
            "planning_landed_per_hit_eur": round((total + planning_shipping) / units_used, 3),
            "max_shipping_for_target_eur": round(max_shipping, 2),
            "ct_zero_units": zero_units,
            "all_selected_zero": zero_units == units_used,
            "cards": " | ".join(lines),
        })

    out.sort(key=lambda x: (-x["distinct_hits"], x["planning_landed_per_hit_eur"], -x["units_selected"]))
    return out[: int(rules["max_report_rows"])]


def write_seller_baskets(path: Path, rows: list[dict]) -> None:
    fields = [
        "seller_id", "seller", "country", "distinct_hits", "units_selected",
        "article_cost_eur", "avg_article_cost_eur", "planning_shipping_eur",
        "planning_landed_total_eur", "planning_landed_per_hit_eur",
        "max_shipping_for_target_eur", "ct_zero_units", "all_selected_zero", "cards",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
