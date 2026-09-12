from pathlib import Path
import csv
import json
import sqlite3

root = Path(__file__).resolve().parents[1]
tracked_path = root / "data/reference/tracked_review_cards.csv"
tracked_path.write_text(
    """id_product,name,expansion_name,number,tracking_role
665676,Dragonite VSTAR,Pokémon TCG: Pokémon GO,050/078,RESALE_REVIEW
665687,Dragonite V,Pokémon TCG: Pokémon GO,076/078,RESALE_REVIEW
725239,Dragonite ex,Obsidian Flames,159/197,RESALE_REVIEW
869863,Stunfisk ex,Ascended Heroes,252/217,RESALE_REVIEW
869859,Drakloak,Ascended Heroes,248/217,RESALE_REVIEW
877463,Gastly,Perfect Order,048/088,RESALE_REVIEW
886490,Beedrill ex,Chaos Rising,098/086,RESALE_REVIEW
682075,Alolan Vulpix V,Silver Tempest,033/195,RESALE_REVIEW
682076,Alolan Vulpix VSTAR,Silver Tempest,034/195,RESALE_REVIEW
582085,Rillaboom VMAX,Fusion Strike,023/264,RESALE_REVIEW
873710,Mega Lucario ex,MEP Black Star Promos,MEP 033,RESALE_REVIEW
869855,Cynthia's Spiritomb,Ascended Heroes,244/217,RESALE_REVIEW
869763,Mega Dragonite ex,Ascended Heroes,152/217,RESALE_REVIEW
""",
    encoding="utf-8",
)

# Snapshot exporter: public-safe tracked identities + current price observations only.
exporter_path = root / "scripts/export_dashboard_snapshot.py"
exporter = exporter_path.read_text(encoding="utf-8")
if "TRACKED_REVIEW_PATH" not in exporter:
    exporter = exporter.replace(
        'RESEARCH_WATCH_PATH = ROOT / "data" / "reference" / "research_watchlist.csv"\n',
        'RESEARCH_WATCH_PATH = ROOT / "data" / "reference" / "research_watchlist.csv"\n'
        'TRACKED_REVIEW_PATH = ROOT / "data" / "reference" / "tracked_review_cards.csv"\n',
    )

tracked_func = '''\n\ndef tracked_review_rows(conn: sqlite3.Connection, path: Path) -> list[dict]:
    """Public-safe exact-card watch rows for dashboard Priority Review."""
    rows = read_csv(path)
    if not rows:
        return []
    out: list[dict] = []
    for source in rows:
        try:
            pid = int(source.get("id_product") or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue
        price = None
        if table_exists(conn, "price_snapshots"):
            price = conn.execute(
                """
                SELECT snapshot_date, trend, avg1, avg7, avg30
                FROM price_snapshots
                WHERE id_product=?
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                (pid,),
            ).fetchone()
        price_dict = dict(price) if price else {}
        out.append({
            "snapshot_date": price_dict.get("snapshot_date") or "",
            "id_product": pid,
            "name": source.get("name") or f"Cardmarket ID {pid}",
            "expansion_name": source.get("expansion_name") or "",
            "number": source.get("number") or "",
            "tracking_role": source.get("tracking_role") or "RESALE_REVIEW",
            "status": "TRACKED_REVIEW",
            "trend": price_dict.get("trend"),
            "avg1": price_dict.get("avg1"),
            "avg7": price_dict.get("avg7"),
            "avg30": price_dict.get("avg30"),
        })
    return out
'''
if "def tracked_review_rows(" not in exporter:
    exporter = exporter.replace("\n\ndef build_snapshot() -> dict:\n", tracked_func + "\n\ndef build_snapshot() -> dict:\n")
if "tracked = tracked_review_rows(conn, TRACKED_REVIEW_PATH)" not in exporter:
    exporter = exporter.replace("    snapshot = {\n", "    tracked = tracked_review_rows(conn, TRACKED_REVIEW_PATH)\n\n    snapshot = {\n")
exporter = exporter.replace(
    '        "privacy_note": "Market/model fields only; no secrets, personal inventory, or seller-level data.",\n',
    '        "privacy_note": "Market/model fields plus public-safe tracked-card identities; no purchase prices, inventory quantities, secrets, or seller-level data.",\n',
)
if '        "tracked_cards": tracked,\n' not in exporter:
    exporter = exporter.replace('        "discovery_candidates": discovery,\n', '        "discovery_candidates": discovery,\n        "tracked_cards": tracked,\n')
exporter_path.write_text(exporter, encoding="utf-8")

# Dashboard UI.
app_path = root / "dashboard/app.py"
app = app_path.read_text(encoding="utf-8")
if "TRACKED_REVIEW_PATH" not in app:
    app = app.replace(
        'SNAPSHOT_PATH = ROOT / "dashboard" / "data" / "dashboard_snapshot.json"\n',
        'SNAPSHOT_PATH = ROOT / "dashboard" / "data" / "dashboard_snapshot.json"\n'
        'TRACKED_REVIEW_PATH = ROOT / "data" / "reference" / "tracked_review_cards.csv"\n',
    )

tracked_renderer = '''\n\ndef render_tracked_card(row: dict) -> None:
    with st.container(border=True):
        st.markdown(f"#### {short_name(row.get('name'))}")
        st.caption(card_context(row))
        st.markdown("**🟣 TRACKED REVIEW**")
        c1, c2 = st.columns(2)
        c1.metric("Cardmarket trend", format_eur(row.get("trend")))
        c2.metric("30d average", format_eur(row.get("avg30")))
        c3, c4 = st.columns(2)
        c3.metric("7d average", format_eur(row.get("avg7")))
        c4.metric("1d average", format_eur(row.get("avg1")))
        st.caption("Tracked for review. No BUY, fair-value or exit signal is fabricated when the card is not in the routed model.")
'''
if "def render_tracked_card(" not in app:
    app = app.replace('\n\nst.set_page_config(page_title="Pokémon Deal Scanner", page_icon="🃏", layout="wide")\n', tracked_renderer + '\n\nst.set_page_config(page_title="Pokémon Deal Scanner", page_icon="🃏", layout="wide")\n')
app = app.replace(
    '    discovery = read_csv(output_dir / "top_flips.csv")[:75]\n    maturity = matured_stats(conn)\n',
    '    discovery = read_csv(output_dir / "top_flips.csv")[:75]\n    tracked = read_csv(TRACKED_REVIEW_PATH)\n    maturity = matured_stats(conn)\n',
)
app = app.replace(
    '    discovery = list(snapshot.get("discovery_candidates") or [])\n    maturity = dict(snapshot.get("maturity") or {})\n',
    '    discovery = list(snapshot.get("discovery_candidates") or [])\n    tracked = list(snapshot.get("tracked_cards") or [])\n    maturity = dict(snapshot.get("maturity") or {})\n',
)

old_filters = '''    non_edge_signals = sorted({s for s in route_signals if s and s != "NO_EDGE"})
    f1, f2, f3 = st.columns([2, 2, 3])
    selected_signals = f1.multiselect("Signals", options=non_edge_signals, default=non_edge_signals, format_func=signal_label)
    price_bands = sorted({clean_text(r.get("price_band")) for r in routes if clean_text(r.get("price_band"))})
    selected_bands = f2.multiselect("Price bands", options=price_bands, default=price_bands)
    search_text = f3.text_input("Find card", placeholder="e.g. Dragonite, Pikachu, Charizard").strip().lower()

    priority = []
    for row in routes:
        signal = str(row.get("route_signal") or "").upper()
        if signal == "NO_EDGE" or (selected_signals and signal not in selected_signals):
            continue
        band = clean_text(row.get("price_band"))
        if selected_bands and band not in selected_bands:
            continue
        if search_text and search_text not in str(row.get("name") or "").lower():
            continue
        priority.append(row)
    priority.sort(key=route_sort_key)

    if priority:
        for start in range(0, min(len(priority), 6), 3):
            cols = st.columns(3)
            for offset, row in enumerate(priority[start:start + 3]):
                with cols[offset]:
                    render_route_card(row)
    else:
        st.info("No current routed cards match these filters.")
'''
new_filters = '''    non_edge_signals = sorted({s for s in route_signals if s and s != "NO_EDGE"})
    f0, f1, f2, f3 = st.columns([2, 2, 2, 3])
    review_set = f0.selectbox(
        "Review set",
        options=["Routed + tracked", "Tracked cards", "Routed priority"],
        index=0,
        help="Tracked cards are the exact resale-review cards on the public-safe watchlist; bundle-only €1 hero cards are excluded.",
    )
    selected_signals = f1.multiselect("Signals", options=non_edge_signals, default=non_edge_signals, format_func=signal_label)
    price_bands = sorted({clean_text(r.get("price_band")) for r in routes if clean_text(r.get("price_band"))})
    selected_bands = f2.multiselect("Price bands", options=price_bands, default=price_bands)
    search_text = f3.text_input("Find card", placeholder="e.g. Dragonite, Pikachu, Charizard").strip().lower()

    routed_priority = []
    if review_set in {"Routed + tracked", "Routed priority"}:
        for row in routes:
            signal = str(row.get("route_signal") or "").upper()
            if signal == "NO_EDGE" or (selected_signals and signal not in selected_signals):
                continue
            band = clean_text(row.get("price_band"))
            if selected_bands and band not in selected_bands:
                continue
            if search_text and search_text not in str(row.get("name") or "").lower():
                continue
            routed_priority.append(dict(row))
        routed_priority.sort(key=route_sort_key)

    tracked_map = {str(r.get("id_product") or "").strip(): dict(r) for r in tracked if r.get("id_product") not in (None, "")}
    route_map = {str(r.get("id_product") or "").strip(): dict(r) for r in routes if r.get("id_product") not in (None, "")}
    tracked_priority = []
    if review_set in {"Routed + tracked", "Tracked cards"}:
        for pid_key, tracked_row in tracked_map.items():
            if search_text and search_text not in str(tracked_row.get("name") or "").lower():
                continue
            route_row = route_map.get(pid_key)
            if route_row:
                merged = dict(tracked_row)
                merged.update({k: v for k, v in route_row.items() if v not in (None, "")})
                merged["_tracked"] = True
                tracked_priority.append(merged)
            else:
                tracked_row["_tracked"] = True
                tracked_priority.append(tracked_row)
        tracked_priority.sort(key=lambda r: short_name(r.get("name")).lower())

    combined_priority = []
    seen_priority = set()
    for row in tracked_priority + routed_priority:
        pid_key = str(row.get("id_product") or "").strip()
        if pid_key and pid_key in seen_priority:
            continue
        if pid_key:
            seen_priority.add(pid_key)
        combined_priority.append(row)

    if combined_priority:
        display_limit = len(combined_priority) if review_set == "Tracked cards" else min(len(combined_priority), 18)
        for start in range(0, display_limit, 3):
            cols = st.columns(3)
            for offset, row in enumerate(combined_priority[start:start + 3]):
                with cols[offset]:
                    if clean_text(row.get("route_signal")):
                        if row.get("_tracked"):
                            st.caption("🟣 Tracked review card")
                        render_route_card(row)
                    else:
                        render_tracked_card(row)
    else:
        st.info("No cards match these Priority Review filters.")
'''
if old_filters not in app:
    raise SystemExit("Priority Review patch target not found")
app = app.replace(old_filters, new_filters)

app = app.replace(
    '    discovery_map = {str(r.get("id_product")): r for r in discovery if r.get("id_product") not in (None, "")}\n    detail_ids = sorted(\n        set(prediction_map) | set(route_rows_by_pid) | set(discovery_map),\n',
    '    discovery_map = {str(r.get("id_product")): r for r in discovery if r.get("id_product") not in (None, "")}\n'
    '    tracked_detail_map = {str(r.get("id_product")): r for r in tracked if r.get("id_product") not in (None, "")}\n'
    '    detail_ids = sorted(\n        set(prediction_map) | set(route_rows_by_pid) | set(discovery_map) | set(tracked_detail_map),\n',
)
app = app.replace(
    '                or discovery_map.get(pid_key, {}).get("name")\n',
    '                or discovery_map.get(pid_key, {}).get("name")\n                or tracked_detail_map.get(pid_key, {}).get("name")\n',
)
app = app.replace(
    '            for source in (\n                discovery_map.get(pid_key),\n                prediction_map.get(pid_key),\n',
    '            for source in (\n                tracked_detail_map.get(pid_key),\n                discovery_map.get(pid_key),\n                prediction_map.get(pid_key),\n',
)
app = app.replace(
    '            if pid_key in route_rows_by_pid:\n                return "ROUTED"\n',
    '            if pid_key in route_rows_by_pid and pid_key in tracked_detail_map:\n                return "ROUTED · TRACKED"\n            if pid_key in route_rows_by_pid:\n                return "ROUTED"\n',
)
app = app.replace(
    '            if pid_key in prediction_map:\n                return "FORECAST"\n',
    '            if pid_key in prediction_map:\n                return "FORECAST"\n            if pid_key in tracked_detail_map:\n                return "TRACKED"\n',
)
app = app.replace(
    '            help="Includes routed cards, immutable forecasts, discovery candidates and explicit research watches present in the current dashboard dataset.",\n',
    '            help="Includes routed cards, tracked review cards, immutable forecasts, discovery candidates and explicit research watches present in the current dashboard dataset.",\n',
)
app_path.write_text(app, encoding="utf-8")

# Update today's hosted snapshot without regenerating discovery, preserving the balanced cross-price preview.
snapshot_path = root / "dashboard/data/dashboard_snapshot.json"
if snapshot_path.exists():
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    tracked_rows = []
    db_path = root / "db/pokemon_deal_scanner.sqlite"
    conn = sqlite3.connect(db_path) if db_path.exists() else None
    if conn:
        conn.row_factory = sqlite3.Row
    with tracked_path.open(newline="", encoding="utf-8") as fh:
        for source in csv.DictReader(fh):
            price = None
            if conn:
                price = conn.execute(
                    "SELECT snapshot_date,trend,avg1,avg7,avg30 FROM price_snapshots WHERE id_product=? ORDER BY snapshot_date DESC LIMIT 1",
                    (int(source["id_product"]),),
                ).fetchone()
            p = dict(price) if price else {}
            tracked_rows.append({
                "snapshot_date": p.get("snapshot_date") or "",
                "id_product": int(source["id_product"]),
                "name": source["name"],
                "expansion_name": source["expansion_name"],
                "number": source["number"],
                "tracking_role": source["tracking_role"],
                "status": "TRACKED_REVIEW",
                "trend": p.get("trend"),
                "avg1": p.get("avg1"),
                "avg7": p.get("avg7"),
                "avg30": p.get("avg30"),
            })
    if conn:
        conn.close()
    snapshot["tracked_cards"] = tracked_rows
    snapshot["privacy_note"] = "Market/model fields plus public-safe tracked-card identities; no purchase prices, inventory quantities, secrets, or seller-level data."
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

docs_path = root / "docs/DASHBOARD.md"
docs = docs_path.read_text(encoding="utf-8")
if "### Tracked Priority Review" not in docs:
    docs += """\n\n### Tracked Priority Review\n\nThe Today → Priority Review can switch between routed priority cards, the exact tracked resale-review watchlist, or both. `data/reference/tracked_review_cards.csv` is intentionally public-safe: it contains exact card identity and a generic tracking role only. Purchase prices, ownership quantities and seller-level information are not exported to the hosted snapshot. Bundle-only €1 hero cards are intentionally excluded from this review list. Tracked cards without a current route show current Cardmarket observations without inventing a BUY/fair-value/exit signal.\n"""
    docs_path.write_text(docs, encoding="utf-8")

print("Tracked Priority Review upgrade prepared")
