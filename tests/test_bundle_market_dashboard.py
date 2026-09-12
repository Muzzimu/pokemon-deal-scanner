import csv
from pathlib import Path


def test_bundle_benchmark_inputs_exist():
    for name in ("bundle_competitors.csv", "bundle_recipes.csv", "bundle_sales.csv"):
        assert (Path("data/business") / name).exists()


def test_bundle_competitor_schema_supports_comparison():
    with Path("data/business/bundle_competitors.csv").open(newline="", encoding="utf-8") as fh:
        fields = csv.DictReader(fh).fieldnames or []
    for field in ("ask_price_eur", "card_count", "price_per_card_eur", "hero_v_ex_count", "foil_density", "status"):
        assert field in fields


def test_dashboard_has_bundle_market_tab():
    text = Path("dashboard/app.py").read_text(encoding="utf-8")
    assert '"Bundle market"' in text
    assert "Business-market diagnostic only" in text


def test_bundle_density_is_displayed_as_percent_points():
    text = Path("dashboard/app.py").read_text(encoding="utf-8")
    assert "foils / total * 100.0" in text
    assert 'row.get("foil_density")) * 100.0' in text
