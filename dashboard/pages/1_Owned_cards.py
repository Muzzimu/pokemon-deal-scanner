from __future__ import annotations

import csv
import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = ROOT / "dashboard" / "data" / "dashboard_snapshot.json"
OWNED_MARKET_PATH = ROOT / "dashboard" / "data" / "owned_market.json"
OWNED_LEDGER_PATH = ROOT / "data" / "reference" / "owned_resale_cards.csv"
CARD_IMAGE_PATH = ROOT / "dashboard" / "data" / "card_images.json"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def card_image_map() -> dict[str, dict]:
    payload = read_json(CARD_IMAGE_PATH)
    cards = payload.get("cards") if isinstance(payload, dict) else None
    return {str(k): dict(v) for k, v in (cards or {}).items() if isinstance(v, dict)}


def image_url(pid: str, quality: str = "low") -> str | None:
    record = CARD_IMAGES.get(str(pid)) or {}
    base = str(record.get("image_base") or "").strip()
    return f"{base}/{quality}.webp" if base else None


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def eur(value) -> str:
    amount = as_float(value)
    return "—" if amount is None else f"€{amount:,.2f}"


def pct(value) -> str:
    amount = as_float(value)
    return "—" if amount is None else f"{amount:,.1f}%"


def signal_label(signal: str | None) -> str:
    labels = {
        "RESELL_TEST": "🟢 RESELL TEST",
        "WATCH_ONLY": "🟡 WATCH",
        "INSUFFICIENT_EXIT_REFERENCE": "🔵 NEEDS EXIT DATA",
        "REVALIDATE_SOURCE": "🟠 REVALIDATE SOURCE",
        "VERIFY_VARIANT": "🔵 VERIFY VARIANT",
        "VERIFY_CONDITION_LANGUAGE": "🔵 VERIFY CONDITION/LANGUAGE",
        "NO_EDGE": "⚪ NO EDGE",
    }
    raw = str(signal or "").upper()
    return labels.get(raw, raw.replace("_", " ") if raw else "🟣 OWNED REVIEW")


def market_floor(source: dict) -> float | None:
    if str(source.get("status") or "").upper() != "OK":
        return None
    return as_float(source.get("floor_eur"))


def market_status(source: dict, source_name: str) -> str:
    status = str(source.get("status") or "NOT_QUERIED").upper()
    if status == "OK":
        bits = [f"{source_name} comparable EN/NM ask"]
        if source.get("visible_sellers") not in (None, ""):
            bits.append(f"{source.get('visible_sellers')} sellers")
        if source.get("visible_units") not in (None, ""):
            bits.append(f"{source.get('visible_units')} units")
        return " · ".join(bits)
    if status == "VERIFY_FINISH":
        return f"{source_name}: finish/parallel could not be verified — floor withheld"
    if status == "NO_COMPARABLE_EN_NM_ASK":
        return f"{source_name}: no comparable EN/NM ask found"
    if status.startswith("MISSING_"):
        return f"{source_name}: source not available in this refresh"
    if status == "DEGRADED":
        return f"{source_name}: refresh degraded"
    return f"{source_name}: not queried"


def index_by_pid(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("id_product")): r for r in rows if r.get("id_product") not in (None, "")}


st.set_page_config(page_title="Owned Pokémon cards", page_icon="🗂️", layout="wide")

snapshot = read_json(SNAPSHOT_PATH)
owned_market = read_json(OWNED_MARKET_PATH)
CARD_IMAGES = card_image_map()
owned_rows = list(owned_market.get("cards") or [])
if not owned_rows:
    owned_rows = read_csv(OWNED_LEDGER_PATH)

routes = index_by_pid(list(snapshot.get("market_routes") or []))
tracked = index_by_pid(list(snapshot.get("tracked_cards") or []))
predictions = index_by_pid(list(snapshot.get("latest_predictions") or []))

st.title("Owned cards")
st.caption("Decision view for cards deliberately bought/tracked for resale review. Bundle-only €1 hero cards are excluded.")
if owned_market.get("generated_at_utc"):
    st.caption(f"Comparable-ask refresh: **{owned_market['generated_at_utc']}**")
else:
    st.warning("The owned-card live market refresh has not published yet. Cost basis is available, but current comparable asks may be blank.")

st.info(
    "Active asks are competition references, not realised sale prices. CM/CT floors are shown only when the refresh can match the exact Cardmarket product, English, NM/raw status and the stored finish rule."
)

search = st.text_input("Find owned card", placeholder="e.g. Dragonite, Gastly, Lucario").strip().lower()
sort_mode = st.selectbox("Sort", ["Name", "Highest landed cost", "Highest current comparable ask", "Highest modelled owner profit"], index=0)

view = [r for r in owned_rows if not search or search in str(r.get("name") or "").lower()]


def owner_profit(row: dict) -> float:
    route = routes.get(str(row.get("id_product")), {})
    exit_net = as_float(route.get("best_sell_net_eur"))
    landed = as_float(row.get("landed_cost_eur"))
    return -1e18 if exit_net is None or landed is None else exit_net - landed


def best_active_ask(row: dict) -> float:
    vals = []
    for source in (row.get("cardmarket") or {}, row.get("cardtrader") or {}):
        value = market_floor(source)
        if value is not None:
            vals.append(value)
    return max(vals) if False else (min(vals) if vals else -1e18)


if sort_mode == "Highest landed cost":
    view.sort(key=lambda r: as_float(r.get("landed_cost_eur")) or -1, reverse=True)
elif sort_mode == "Highest current comparable ask":
    view.sort(key=best_active_ask, reverse=True)
elif sort_mode == "Highest modelled owner profit":
    view.sort(key=owner_profit, reverse=True)
else:
    view.sort(key=lambda r: str(r.get("name") or "").lower())

for start in range(0, len(view), 2):
    cols = st.columns(2)
    for offset, card in enumerate(view[start:start + 2]):
        with cols[offset]:
            pid = str(card.get("id_product"))
            route = routes.get(pid, {})
            tracked_row = tracked.get(pid, {})
            prediction = predictions.get(pid, {})
            cm = card.get("cardmarket") or {}
            ct = card.get("cardtrader") or {}
            cm_floor = market_floor(cm)
            ct_floor = market_floor(ct)
            active_floors = [x for x in (cm_floor, ct_floor) if x is not None]
            lowest_ask = min(active_floors) if active_floors else None
            landed = as_float(card.get("landed_cost_eur"))
            item_paid = as_float(card.get("item_paid_eur"))
            model_exit = as_float(route.get("best_sell_net_eur"))
            model_profit = None if model_exit is None or landed is None else model_exit - landed
            model_roi = None if model_profit is None or not landed else (model_profit / landed) * 100.0
            gross_room = None if lowest_ask is None or landed is None else lowest_ask - landed

            with st.container(border=True):
                art = image_url(pid, "low")
                if art:
                    art_col, title_col = st.columns([1, 2.6], vertical_alignment="top")
                    with art_col:
                        st.image(art, width=125)
                    with title_col:
                        st.markdown(f"### {card.get('name') or 'Unknown card'}")
                        st.caption(
                            f"{card.get('expansion_name') or 'Unknown set'} · {card.get('number') or 'No number'} · "
                            f"{card.get('language') or '—'} · {card.get('condition') or '—'} · Cardmarket ID {pid}"
                        )
                        st.markdown(f"**{signal_label(route.get('route_signal'))}**")
                else:
                    st.markdown(f"### {card.get('name') or 'Unknown card'}")
                    st.caption(
                        f"{card.get('expansion_name') or 'Unknown set'} · {card.get('number') or 'No number'} · "
                        f"{card.get('language') or '—'} · {card.get('condition') or '—'} · Cardmarket ID {pid}"
                    )
                    st.markdown(f"**{signal_label(route.get('route_signal'))}**")

                c1, c2 = st.columns(2)
                c1.metric("You paid", eur(item_paid))
                c2.metric("Your landed cost", eur(landed))

                c3, c4 = st.columns(2)
                c3.metric("Lowest comparable CM ask", eur(cm_floor))
                c4.metric("Lowest comparable CT ask", eur(ct_floor))
                st.caption(market_status(cm, "Cardmarket"))
                st.caption(market_status(ct, "CardTrader"))

                c5, c6 = st.columns(2)
                c5.metric("Lowest comparable active ask", eur(lowest_ask))
                c6.metric("Gross room vs landed", eur(gross_room))
                st.caption("Gross room is before selling fees, outbound shipping and execution slippage; it is not profit.")

                if model_exit is not None:
                    c7, c8 = st.columns(2)
                    c7.metric("Modelled net exit", eur(model_exit))
                    c8.metric("Your profit at modelled exit", eur(model_profit))
                    st.markdown(f"**Your ROI at modelled exit:** {pct(model_roi)}")
                    if route.get("best_sell_channel"):
                        st.caption(f"Modelled exit route: {str(route['best_sell_channel']).replace('_', ' ').title()}")
                else:
                    st.caption("No routed net-exit model for this card yet. Current asks are shown as market context only.")

                with st.expander("Purchase basis"):
                    st.write({
                        "purchase_date": card.get("purchase_date"),
                        "source": card.get("purchase_source"),
                        "item_paid_eur": item_paid,
                        "allocated_shipping_eur": as_float(card.get("allocated_shipping_eur")),
                        "landed_cost_eur": landed,
                        "shipping_allocation": card.get("shipping_allocation_method"),
                        "finish_rule": card.get("finish_requirement"),
                    })
                    st.caption("Basket shipping is currently allocated equally per card so item price and landed investment remain separately visible.")

                with st.expander("Market / model detail"):
                    if route:
                        st.write({
                            "EU fair value": as_float(route.get("eu_fair_value_eur")),
                            "scanner validated buy": as_float(route.get("best_validated_buy_eur")),
                            "scanner modelled profit": as_float(route.get("net_spread_eur")),
                            "scanner modelled ROI %": as_float(route.get("net_roi_pct")),
                            "PCS": as_float(route.get("eu_price_confidence_score")),
                            "LQS": as_float(route.get("eu_liquidity_score") or route.get("liquidity_score")),
                            "ECS": as_float(route.get("exit_confidence_score")),
                            "BOS": as_float(route.get("bridge_opportunity_score")),
                            "quality gate": route.get("quality_gate_reason"),
                        })
                    else:
                        st.write({
                            "Cardmarket trend": as_float(tracked_row.get("trend")),
                            "Cardmarket 1d average": as_float(tracked_row.get("avg1")),
                            "Cardmarket 7d average": as_float(tracked_row.get("avg7")),
                            "Cardmarket 30d average": as_float(tracked_row.get("avg30")),
                        })
                    if prediction:
                        st.caption("Immutable forecast exists for this card.")

st.divider()
st.caption(
    "UX rule: cost basis and current comparable market asks are shown before scanner diagnostics. Technical evidence remains available under expanders; the dashboard does not invent a new BUY/SELL gate."
)
