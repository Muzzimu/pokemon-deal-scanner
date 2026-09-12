from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import median

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
LOCAL_PATH = ROOT / "output" / "cross_price_research.csv"
HOSTED_PATH = ROOT / "dashboard" / "data" / "cross_price_research_preview.csv"


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value):
    number = as_float(value)
    return None if number is None else int(number)


def short_name(value) -> str:
    text = str(value or "Unknown card")
    return text.split(" [", 1)[0]


def compact_basis(value: str | None) -> str:
    value = str(value or "")
    if value == "VALIDATED_EN_NM":
        return "Validated EN/NM"
    if value == "CARDMARKET_GENERIC_LOW_SCREENING_ONLY":
        return "Generic CM low — screen only"
    return value.replace("_", " ").title() if value else "Unknown"


st.set_page_config(page_title="Cross-price research", page_icon="⚖️", layout="wide")

path = LOCAL_PATH if LOCAL_PATH.exists() else HOSTED_PATH
rows = read_csv(path)

st.title("Cross-price research")
st.caption("Research-only comparison across value bands. This page does not create or change BUY signals, fair values, route gates, or v0.12 scoring.")
st.warning(
    "Cardmarket 30-day average is used only as a diagnostic reference. Rows labelled 'Generic CM low — screen only' do not have validated English/NM acquisition economics yet, so their headroom is a screening estimate, not executable profit."
)

if not rows:
    st.info("No cross-price research data is available yet. Run the scanner or the cross-price research preview workflow first.")
    st.stop()

bands = list(dict.fromkeys(str(row.get("reference_band") or "UNKNOWN") for row in rows))
validated_count = sum(str(row.get("acquisition_basis") or "") == "VALIDATED_EN_NM" for row in rows)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Research candidates", len(rows))
c2.metric("Reference bands", len(bands))
c3.metric("Validated EN/NM acquisition", validated_count)
c4.metric("Needs acquisition validation", len(rows) - validated_count)

summary_groups: dict[str, list[dict]] = defaultdict(list)
for row in rows:
    summary_groups[str(row.get("reference_band") or "UNKNOWN")].append(row)

summary = []
for band in bands:
    group = summary_groups[band]
    headrooms = [as_float(row.get("gross_headroom_eur")) for row in group]
    headrooms = [value for value in headrooms if value is not None]
    summary.append(
        {
            "Reference band": band,
            "Candidates": len(group),
            "Validated EN/NM": sum(str(row.get("acquisition_basis") or "") == "VALIDATED_EN_NM" for row in group),
            "Median screening headroom": median(headrooms) if headrooms else None,
            "Max screening headroom": max(headrooms) if headrooms else None,
        }
    )

st.subheader("Band balance")
st.dataframe(
    summary,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Median screening headroom": st.column_config.NumberColumn(format="€%.2f"),
        "Max screening headroom": st.column_config.NumberColumn(format="€%.2f"),
    },
)

st.divider()
st.subheader("Candidate comparison")
f1, f2, f3 = st.columns([2, 2, 3])
selected_bands = f1.multiselect("Reference bands", bands, default=bands)
evidence_filter = f2.selectbox("Acquisition evidence", ["All", "Validated EN/NM", "Needs validation"])
search_text = f3.text_input("Find card", placeholder="e.g. Pikachu, Charizard, Dragonite").strip().lower()

view = []
for row in rows:
    band = str(row.get("reference_band") or "UNKNOWN")
    if selected_bands and band not in selected_bands:
        continue
    validated = str(row.get("acquisition_basis") or "") == "VALIDATED_EN_NM"
    if evidence_filter == "Validated EN/NM" and not validated:
        continue
    if evidence_filter == "Needs validation" and validated:
        continue
    if search_text and search_text not in str(row.get("name") or "").lower():
        continue
    view.append(row)

comparison = []
for row in view:
    comparison.append(
        {
            "Card": short_name(row.get("name")),
            "Set": row.get("expansion_name") or "—",
            "No.": row.get("number") or "—",
            "Band": row.get("reference_band"),
            "Screening acquisition": as_float(row.get("screening_acquisition_eur")),
            "Buy source": str(row.get("screening_acquisition_source") or "UNKNOWN").replace("_", " "),
            "Acquisition evidence": compact_basis(row.get("acquisition_basis")),
            "30d reference": as_float(row.get("reference_value_eur")),
            "Screening headroom": as_float(row.get("gross_headroom_eur")),
            "Friction budget": as_float(row.get("friction_budget_eur")),
            "Gap %": as_float(row.get("cross_price_gap_pct")),
            "CT sellers": as_int(row.get("ct_visible_sellers")),
            "Research state": str(row.get("research_state") or "").replace("_", " "),
        }
    )

st.dataframe(
    comparison,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Screening acquisition": st.column_config.NumberColumn(format="€%.2f"),
        "30d reference": st.column_config.NumberColumn(format="€%.2f"),
        "Screening headroom": st.column_config.NumberColumn(format="€%.2f"),
        "Friction budget": st.column_config.NumberColumn(format="€%.2f"),
        "Gap %": st.column_config.NumberColumn(format="%.1f%%"),
        "CT sellers": st.column_config.NumberColumn(format="%d"),
    },
)

st.caption(
    "Friction budget is the gross screening headroom available before acquisition shipping, platform fees, seller shipping, packaging, FX and execution loss reduce contribution to zero. It is not a profit forecast."
)

with st.expander("Method and guardrails"):
    st.markdown(
        """
- The panel samples up to **15 cards per reference-value band**: €0–10, €10–30, €30–50, €50–100 and €100+.
- Bands use **Cardmarket 30-day average** as a diagnostic reference, not an executable exit price.
- Within each band, validated English/NM acquisition evidence is ranked ahead of generic Cardmarket-low screening rows.
- Generic Cardmarket low remains discovery-only because it can reflect another language or condition.
- Absolute euro headroom and percentage gap are shown together so cheap cards do not dominate solely through percentage moves.
- Final economics still belong to the normal route layer, where landed acquisition, executable exit, net contribution, ROI and market-quality gates apply.
"""
    )
