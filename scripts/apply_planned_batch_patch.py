from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- Feature 4: lightweight bundle-market benchmark dashboard ---

path = ROOT / "dashboard/app.py"
text = path.read_text(encoding="utf-8")

const_anchor = 'CARD_FUNDAMENTALS_PATH = ROOT / "data" / "reference" / "card_fundamentals.csv"\n'
if 'BUNDLE_COMPETITORS_PATH' not in text:
    text = text.replace(
        const_anchor,
        const_anchor
        + 'BUNDLE_COMPETITORS_PATH = ROOT / "data" / "business" / "bundle_competitors.csv"\n'
        + 'BUNDLE_RECIPES_PATH = ROOT / "data" / "business" / "bundle_recipes.csv"\n'
        + 'BUNDLE_SALES_PATH = ROOT / "data" / "business" / "bundle_sales.csv"\n',
        1,
    )

helper_anchor = 'def provider_usage_summary(rows: list[dict], limits: list[dict]) -> list[dict]:\n'
helpers = '''def median_numeric(rows: list[dict], field: str) -> float | None:\n    values = sorted(value for value in (as_float(row.get(field)) for row in rows) if value is not None)\n    if not values:\n        return None\n    middle = len(values) // 2\n    if len(values) % 2:\n        return values[middle]\n    return (values[middle - 1] + values[middle]) / 2.0\n\n\ndef bundle_recipe_rows(rows: list[dict]) -> list[dict]:\n    output = []\n    for row in rows:\n        total = as_float(row.get("total_cards"))\n        foils = as_float(row.get("holo_reverse"))\n        output.append({\n            "Bundle": clean_text(row.get("bundle_type")) or "—",\n            "Ask (Adverts)": as_float(row.get("adverts_price_eur")),\n            "Cards": as_int(row.get("total_cards")),\n            "Hero V/ex": as_int(row.get("v_ex")),\n            "Guaranteed icon": as_int(row.get("icon")),\n            "Holo/RH minimum": as_int(row.get("holo_reverse")),\n            "Foil density": (foils / total) if total and foils is not None else None,\n            "Trainers": as_int(row.get("trainers")),\n        })\n    return output\n\n\ndef bundle_competitor_rows(rows: list[dict]) -> list[dict]:\n    output = []\n    for row in rows:\n        output.append({\n            "Observed": clean_text(row.get("observed_at")) or "—",\n            "Source": clean_text(row.get("source")) or "—",\n            "Ask": as_float(row.get("ask_price_eur")),\n            "Cards": as_int(row.get("card_count")),\n            "€/card": as_float(row.get("price_per_card_eur")),\n            "Hero hits": as_int(row.get("hero_v_ex_count")),\n            "Holo": as_int(row.get("holo_count")),\n            "Reverse": as_int(row.get("reverse_holo_count")),\n            "Foil density": as_float(row.get("foil_density")),\n            "Language": clean_text(row.get("language_mix")) or "UNKNOWN",\n            "Duplicates": clean_text(row.get("duplicate_policy")) or "UNKNOWN",\n            "Theme": clean_text(row.get("theme")) or "UNKNOWN",\n            "Location": clean_text(row.get("seller_location")) or "—",\n            "Status": clean_text(row.get("status")) or "—",\n        })\n    return output\n\n\n'''
if 'def bundle_recipe_rows(' not in text:
    text = text.replace(helper_anchor, helpers + helper_anchor, 1)

load_anchor = 'card_fundamentals_by_pid = {str(r.get("id_product")): r for r in card_fundamental_rows if r.get("id_product")}\n'
if 'bundle_competitors = read_csv(BUNDLE_COMPETITORS_PATH)' not in text:
    text = text.replace(
        load_anchor,
        load_anchor
        + 'bundle_competitors = read_csv(BUNDLE_COMPETITORS_PATH)\n'
        + 'bundle_recipes = read_csv(BUNDLE_RECIPES_PATH)\n'
        + 'bundle_sales = read_csv(BUNDLE_SALES_PATH)\n',
        1,
    )

old_tabs = 'tab_today, tab_card, tab_health = st.tabs(["Today", "Card detail", "Model health"])\n'
new_tabs = 'tab_today, tab_card, tab_bundle, tab_health = st.tabs(["Today", "Card detail", "Bundle market", "Model health"])\n'
if old_tabs in text:
    text = text.replace(old_tabs, new_tabs, 1)

health_anchor = 'with tab_health:\n    st.subheader("Provider usage")\n'
bundle_block = '''with tab_bundle:\n    st.subheader("Bundle market")\n    st.caption("Business-market diagnostic only — this does not affect exact-card fair value or BUY logic.")\n\n    competitor_count = len(bundle_competitors)\n    median_ask = median_numeric(bundle_competitors, "ask_price_eur")\n    median_ppc = median_numeric(bundle_competitors, "price_per_card_eur")\n    median_foil = median_numeric(bundle_competitors, "foil_density")\n    hero_known = [as_float(row.get("hero_v_ex_count")) for row in bundle_competitors]\n    hero_known = [value for value in hero_known if value is not None]\n    hero_prevalence = (sum(1 for value in hero_known if value > 0) / len(hero_known) * 100.0) if hero_known else None\n\n    b1, b2, b3, b4 = st.columns(4)\n    b1.metric("Comparable listings", competitor_count)\n    b2.metric("Median ask", format_eur(median_ask))\n    b3.metric("Median €/card", format_eur(median_ppc))\n    b4.metric("Median foil density", format_pct(None if median_foil is None else median_foil * 100.0))\n    if competitor_count < 5:\n        st.info(f"Early benchmark: only {competitor_count} clearly comparable listing{'s' if competitor_count != 1 else ''} stored so far. Treat medians as descriptive, not a market estimate.")\n\n    st.markdown("**Our current recipes**")\n    recipe_view = bundle_recipe_rows(bundle_recipes)\n    if recipe_view:\n        st.dataframe(\n            recipe_view,\n            use_container_width=True,\n            hide_index=True,\n            column_config={\n                "Ask (Adverts)": st.column_config.NumberColumn(format="€%.2f"),\n                "Foil density": st.column_config.NumberColumn(format="%.0f%%"),\n            },\n        )\n    else:\n        st.caption("No bundle recipes are stored yet.")\n\n    st.markdown("**Comparable market listings**")\n    competitor_view = bundle_competitor_rows(bundle_competitors)\n    if competitor_view:\n        st.dataframe(\n            competitor_view,\n            use_container_width=True,\n            hide_index=True,\n            column_config={\n                "Ask": st.column_config.NumberColumn(format="€%.2f"),\n                "€/card": st.column_config.NumberColumn(format="€%.2f"),\n                "Foil density": st.column_config.NumberColumn(format="%.0f%%"),\n            },\n        )\n        if hero_prevalence is not None:\n            st.caption(f"Visible hero-card prevalence in the current annotated sample: {hero_prevalence:.0f}%. Composition fields remain UNKNOWN when the listing does not disclose them.")\n    else:\n        st.caption("No comparable competitor listings are stored yet.")\n\n    st.markdown("**Own realised bundle sales**")\n    if bundle_sales:\n        realised = []\n        for row in bundle_sales:\n            realised.append({\n                "Date": clean_text(row.get("date")) or "—",\n                "Channel": clean_text(row.get("platform")) or "—",\n                "Bundle": clean_text(row.get("bundle_type")) or "—",\n                "Qty": as_int(row.get("quantity")),\n                "Revenue": as_float(row.get("item_revenue_eur")),\n                "Net cash": as_float(row.get("net_cash_received_eur")),\n            })\n        st.dataframe(\n            realised,\n            use_container_width=True,\n            hide_index=True,\n            column_config={\n                "Revenue": st.column_config.NumberColumn(format="€%.2f"),\n                "Net cash": st.column_config.NumberColumn(format="€%.2f"),\n            },\n        )\n    else:\n        st.caption("No realised bundle sales recorded yet. When sales start, this section becomes the feedback loop between competitor design and our actual sell-through/economics.")\n\n\nwith tab_health:\n    st.subheader("Provider usage")\n'''
if health_anchor in text and 'with tab_bundle:' not in text:
    text = text.replace(health_anchor, bundle_block, 1)
path.write_text(text, encoding="utf-8")

# Test the business files and dashboard contract.
test = '''import csv\nfrom pathlib import Path\n\n\ndef test_bundle_benchmark_inputs_exist():\n    for name in ("bundle_competitors.csv", "bundle_recipes.csv", "bundle_sales.csv"):\n        assert (Path("data/business") / name).exists()\n\n\ndef test_bundle_competitor_schema_supports_comparison():\n    with Path("data/business/bundle_competitors.csv").open(newline="", encoding="utf-8") as fh:\n        fields = csv.DictReader(fh).fieldnames or []\n    for field in ("ask_price_eur", "card_count", "price_per_card_eur", "hero_v_ex_count", "foil_density", "status"):\n        assert field in fields\n\n\ndef test_dashboard_has_bundle_market_tab():\n    text = Path("dashboard/app.py").read_text(encoding="utf-8")\n    assert '"Bundle market"' in text\n    assert "Business-market diagnostic only" in text\n'''
(ROOT / "tests/test_bundle_market_dashboard.py").write_text(test, encoding="utf-8")

doc_path = ROOT / "docs/DASHBOARD.md"
doc = doc_path.read_text(encoding="utf-8")
note = '''\n## Bundle market benchmark\n\nThe `Bundle market` tab is a separate business diagnostic based on curated comparable bundle listings plus our stored bundle recipes and realised bundle sales. It may show ask, card count, €/card, hero-card prevalence, foil density and disclosed composition. UNKNOWN fields stay unknown, disappeared listings are not treated as sold, and small samples are labelled explicitly. This page never feeds exact-card fair value or BUY logic.\n\n'''
if "## Bundle market benchmark" not in doc:
    doc += note
    doc_path.write_text(doc, encoding="utf-8")

(ROOT / ".patch-message").write_text("Add bundle market benchmark dashboard\n", encoding="utf-8")
