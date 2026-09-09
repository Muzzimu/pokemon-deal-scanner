from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUSINESS = ROOT / "data" / "business"
OUTPUT = ROOT / "output" / "business_cost_summary.json"


def read_rows(name: str) -> list[dict[str, str]]:
    path = BUSINESS / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def fnum(value: str | None) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def is_true(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def main() -> None:
    inventory = read_rows("inventory_lots.csv")
    assumptions = read_rows("cost_assumptions.csv")
    packaging = read_rows("packaging_purchases.csv")
    research = read_rows("research_marketing.csv")
    recipes = read_rows("bundle_recipes.csv")
    sales = read_rows("bundle_sales.csv")

    business_inventory = [r for r in inventory if is_true(r.get("business_inventory"))]
    bulk_inventory = [r for r in business_inventory if (r.get("cost_pool") or "bulk_base") == "bulk_base"]
    icon_inventory = [r for r in business_inventory if r.get("cost_pool") == "icon_inventory"]

    inventory_spend = sum(fnum(r.get("landed_cost_eur")) for r in business_inventory)
    bulk_inventory_spend = sum(fnum(r.get("landed_cost_eur")) for r in bulk_inventory)
    icon_inventory_spend = sum(fnum(r.get("landed_cost_eur")) for r in icon_inventory)
    packaging_spend = sum(fnum(r.get("landed_cost_eur")) for r in packaging)
    research_spend = sum(fnum(r.get("cash_cost_eur")) for r in research if is_true(r.get("include_in_all_in_project_cash")))
    operating_research_spend = sum(
        fnum(r.get("cash_cost_eur")) for r in research if is_true(r.get("include_in_operating_break_even"))
    )

    total_cards = sum(fnum(r.get("total_cards_est")) for r in business_inventory)
    total_holo = sum(fnum(r.get("holo_reverse_cards_est")) for r in business_inventory)
    bulk_cards = sum(fnum(r.get("total_cards_est")) for r in bulk_inventory)
    icon_cards = sum(fnum(r.get("total_cards_est")) for r in icon_inventory)
    avg_bulk_cost = bulk_inventory_spend / bulk_cards if bulk_cards else 0.0
    avg_icon_cost = icon_inventory_spend / icon_cards if icon_cards else 0.0

    assumption_map = {r["assumption_key"]: fnum(r.get("value")) for r in assumptions}
    v_ex_cost = assumption_map.get("v_ex_card_unit_cost", 0.0)

    recipe_costs: dict[str, dict[str, float]] = {}
    for r in recipes:
        bundle = r["bundle_type"]
        bulk_cards_per_bundle = fnum(r.get("total_cards")) - fnum(r.get("v_ex"))
        raw_cost = bulk_cards_per_bundle * avg_bulk_cost + fnum(r.get("v_ex")) * v_ex_cost
        recipe_costs[bundle] = {
            "raw_card_cost_eur": round(raw_cost, 4),
            "adverts_price_eur": fnum(r.get("adverts_price_eur")),
            "vinted_test_price_eur": fnum(r.get("vinted_test_price_eur")),
            "holo_reverse_per_bundle": fnum(r.get("holo_reverse")),
        }

    sales_revenue = sum(fnum(r.get("item_revenue_eur")) for r in sales)
    net_cash_received = sum(fnum(r.get("net_cash_received_eur")) for r in sales)

    operating_cash_invested = inventory_spend + packaging_spend + operating_research_spend
    all_in_project_cash_spent = operating_cash_invested + research_spend - operating_research_spend

    summary = {
        "inventory_spend_eur": round(inventory_spend, 2),
        "bulk_inventory_spend_eur": round(bulk_inventory_spend, 2),
        "icon_inventory_spend_eur": round(icon_inventory_spend, 2),
        "packaging_spend_eur": round(packaging_spend, 2),
        "research_test_spend_eur": round(research_spend, 2),
        "operating_cash_invested_eur": round(operating_cash_invested, 2),
        "all_in_project_cash_spent_eur": round(all_in_project_cash_spent, 2),
        "estimated_business_cards": int(total_cards),
        "estimated_holo_reverse_cards": int(total_holo),
        "estimated_icon_cards": int(icon_cards),
        "average_bulk_card_cost_eur": round(avg_bulk_cost, 4),
        "average_icon_card_cost_eur": round(avg_icon_cost, 4),
        "v_ex_planning_cost_eur": round(v_ex_cost, 2),
        "bundle_raw_card_costs": recipe_costs,
        "sales_item_revenue_eur": round(sales_revenue, 2),
        "sales_net_cash_received_eur": round(net_cash_received, 2),
        "operating_break_even_remaining_eur": round(max(0.0, operating_cash_invested - net_cash_received), 2),
        "all_in_break_even_remaining_eur": round(max(0.0, all_in_project_cash_spent - net_cash_received), 2),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
