from pathlib import Path

APP = Path("dashboard/app.py")
DOC = Path("docs/DASHBOARD.md")
text = APP.read_text(encoding="utf-8")

old_import = "import sqlite3\nfrom pathlib import Path"
new_import = "import sqlite3\nfrom datetime import datetime\nfrom pathlib import Path"
if old_import not in text:
    raise SystemExit("Expected import anchor not found")
text = text.replace(old_import, new_import, 1)

old_clean = '''def clean_text(value) -> str | None:\n    if value is None:\n        return None\n    text = str(value).strip()\n    return None if not text or text.lower() in {"none", "nan", "null"} else text\n\n\n'''
new_clean = old_clean + '''def compact_timestamp(value) -> str:\n    text = clean_text(value) or "unknown"\n    try:\n        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))\n    except ValueError:\n        return text\n    if "T" not in text:\n        return parsed.strftime("%d %b %Y").lstrip("0")\n    suffix = " UTC" if text.endswith("+00:00") or text.endswith("Z") else ""\n    return parsed.strftime("%d %b %Y · %H:%M").lstrip("0") + suffix\n\n\n'''
if old_clean not in text:
    raise SystemExit("Expected clean_text anchor not found")
text = text.replace(old_clean, new_clean, 1)

old_setup = '''st.set_page_config(page_title="Pokémon Deal Scanner", page_icon="🃏", layout="wide")\ncfg = load_cfg()'''
new_setup = '''st.set_page_config(page_title="Pokémon Deal Scanner", page_icon="🃏", layout="wide")\nst.markdown(\n    """\n    <style>\n    [data-testid="stAppViewContainer"] .main .block-container {\n        padding-top: 1.05rem;\n    }\n    .scanner-header {\n        display: flex;\n        align-items: baseline;\n        flex-wrap: wrap;\n        gap: 0.25rem 0.9rem;\n        margin: 0 0 0.15rem 0;\n    }\n    .scanner-title {\n        font-size: 2rem;\n        font-weight: 720;\n        line-height: 1.1;\n        letter-spacing: -0.025em;\n    }\n    .scanner-meta {\n        font-size: 0.80rem;\n        line-height: 1.25;\n        color: rgba(127, 127, 127, 0.95);\n    }\n    .market-strip {\n        display: flex;\n        align-items: center;\n        flex-wrap: wrap;\n        gap: 0.42rem;\n        margin: 0.45rem 0 0.7rem 0;\n    }\n    .market-date {\n        font-size: 1.08rem;\n        font-weight: 650;\n        margin-right: 0.15rem;\n    }\n    .kpi-chip {\n        border: 1px solid rgba(127, 127, 127, 0.35);\n        background: rgba(127, 127, 127, 0.08);\n        border-radius: 999px;\n        padding: 0.16rem 0.52rem;\n        font-size: 0.82rem;\n        line-height: 1.35;\n        white-space: nowrap;\n    }\n    .kpi-chip strong { font-weight: 700; }\n    .info-dot {\n        color: rgba(127, 127, 127, 0.95);\n        cursor: help;\n        font-size: 0.92rem;\n        padding-left: 0.1rem;\n    }\n    @media (max-width: 700px) {\n        .scanner-title { font-size: 1.65rem; }\n        .scanner-meta { width: 100%; }\n        .market-date { width: 100%; }\n    }\n    </style>\n    """,\n    unsafe_allow_html=True,\n)\ncfg = load_cfg()'''
if old_setup not in text:
    raise SystemExit("Expected set_page_config anchor not found")
text = text.replace(old_setup, new_setup, 1)

old_header = '''st.title("Pokémon Deal Scanner")\nst.caption(f"v{scanner_version} · read-only decision dashboard · scanner rules remain authoritative")\nst.caption(f"Data mode: **{data_mode}** · Updated: **{data_updated}**")\n\ntab_today, tab_card, tab_health = st.tabs(["Today", "Card detail", "Model health"])\n\nwith tab_today:\n    route_signals = [str(r.get("route_signal") or "").upper() for r in routes]\n    resell_count = sum(s in RESELL_SIGNALS or s == "STRONG_ARBITRAGE" for s in route_signals)\n    watch_count = sum(s in WATCH_SIGNALS for s in route_signals)\n    needs_count = sum(s in NEEDS_EVIDENCE_SIGNALS for s in route_signals)\n    latest_date = predictions[0].get("snapshot_date", "—") if predictions else "—"\n    st.markdown(f"### {latest_date} market review")\n    c1, c2, c3, c4 = st.columns(4)\n    c1.metric("Resell tests", resell_count)\n    c2.metric("Watch", watch_count)\n    c3.metric("Needs evidence", needs_count)\n    c4.metric("Discovery queue", len(discovery))\n    st.caption("Market-profile diagnostics explain the evidence; they do not create new BUY rules or alter v0.12 route signals.")\n\n    st.divider()\n    st.subheader("Priority review")'''
new_header = '''compact_mode = "Hosted snapshot" if data_mode == "Hosted public snapshot" else data_mode\nst.markdown(\n    f"""\n    <div class="scanner-header">\n      <div class="scanner-title">Pokémon Deal Scanner</div>\n      <div class="scanner-meta">v{scanner_version} · {compact_mode} · Updated {compact_timestamp(data_updated)} · read-only</div>\n    </div>\n    """,\n    unsafe_allow_html=True,\n)\n\ntab_today, tab_card, tab_health = st.tabs(["Today", "Card detail", "Model health"])\n\nwith tab_today:\n    route_signals = [str(r.get("route_signal") or "").upper() for r in routes]\n    resell_count = sum(s in RESELL_SIGNALS or s == "STRONG_ARBITRAGE" for s in route_signals)\n    watch_count = sum(s in WATCH_SIGNALS for s in route_signals)\n    needs_count = sum(s in NEEDS_EVIDENCE_SIGNALS for s in route_signals)\n    latest_date = predictions[0].get("snapshot_date", "—") if predictions else "—"\n    review_date = compact_timestamp(latest_date).split(" · ", 1)[0]\n    st.markdown(\n        f"""\n        <div class="market-strip">\n          <span class="market-date">{review_date} market review</span>\n          <span class="kpi-chip">🟢 Resell <strong>{resell_count}</strong></span>\n          <span class="kpi-chip">🟡 Watch <strong>{watch_count}</strong></span>\n          <span class="kpi-chip">🔵 Needs data <strong>{needs_count}</strong></span>\n          <span class="kpi-chip">🔎 Discovery <strong>{len(discovery)}</strong></span>\n          <span class="info-dot" title="Market-profile diagnostics explain evidence only; they do not create BUY rules or alter v0.12 route signals.">ⓘ</span>\n        </div>\n        """,\n        unsafe_allow_html=True,\n    )\n\n    st.subheader("Priority review")'''
if old_header not in text:
    raise SystemExit("Expected dashboard header block not found")
text = text.replace(old_header, new_header, 1)

APP.write_text(text, encoding="utf-8")

# Persist the layout principle in the dashboard UX contract.
doc = DOC.read_text(encoding="utf-8")
anchor = "8. **Artwork follows exact identity.** Small card images may be shown only from an explicit Cardmarket-product → TCGdex mapping. Never fuzzy-match artwork in the UI; if the mapping is missing, show no image.\n"
addition = anchor + "9. **Keep orientation chrome compact.** Version, freshness and review counters should use minimal vertical space so the first actionable review content appears quickly; governance detail can move to tooltips or progressive disclosure.\n"
if "9. **Keep orientation chrome compact.**" not in doc:
    if anchor not in doc:
        raise SystemExit("Expected dashboard UX contract anchor not found")
    doc = doc.replace(anchor, addition, 1)
    DOC.write_text(doc, encoding="utf-8")
