from __future__ import annotations

import csv
import json
from html import escape
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


def signed_eur(value) -> str:
    amount = as_float(value)
    if amount is None:
        return "—"
    if amount > 0:
        return f"+€{amount:,.2f}"
    if amount < 0:
        return f"-€{abs(amount):,.2f}"
    return "€0.00"


def pct(value) -> str:
    amount = as_float(value)
    return "—" if amount is None else f"{amount:,.1f}%"


def signed_pct(value) -> str:
    amount = as_float(value)
    if amount is None:
        return "—"
    return f"{amount:+,.1f}%"


def clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if not text or text.lower() in {"none", "nan", "null"} else text


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


def friendly_source(value) -> str:
    raw = clean_text(value)
    if not raw:
        return "Source not retained"
    labels = {
        "CARDTRADER_EN_NM": "CardTrader EN/NM ask",
        "CARDMARKET_EN_NM": "Cardmarket EN/NM ask",
        "CARDTRADER_DIRECT": "CardTrader Direct",
        "CARDTRADER_ZERO": "CardTrader Zero",
        "ADVERTS": "Adverts",
        "ADVERTS.IE": "Adverts.ie",
        "CARDMARKET": "Cardmarket",
    }
    return labels.get(raw.upper(), raw.replace("_", " ").title())


def market_floor(source: dict) -> float | None:
    if str(source.get("status") or "").upper() != "OK":
        return None
    return as_float(source.get("floor_eur"))


def market_robust_floor(source: dict) -> float | None:
    if str(source.get("status") or "").upper() != "OK":
        return None
    return as_float(source.get("robust_floor_eur"))


def ask_sample_text(source: dict) -> str | None:
    values = source.get("ask_sample_eur")
    if not isinstance(values, list) or not values:
        return None
    return " / ".join(eur(v) for v in values)


def market_depth(source: dict, source_name: str) -> str:
    status = str(source.get("status") or "NOT_QUERIED").upper()
    if status != "OK":
        if status == "VERIFY_FINISH":
            return "finish unverified"
        if status == "NO_COMPARABLE_EN_NM_ASK":
            return "no exact ask"
        if status.startswith("MISSING_"):
            return "source unavailable"
        if status == "DEGRADED":
            return "refresh degraded"
        return "not queried"
    if source_name == "CardTrader":
        sellers = source.get("visible_sellers")
        units = source.get("visible_units")
        bits = []
        if sellers not in (None, ""):
            bits.append(f"{sellers} sellers")
        if units not in (None, ""):
            bits.append(f"{units} cards")
        return " · ".join(bits) if bits else "exact EN/NM"
    offers = source.get("visible_offer_rows")
    return f"{offers} comparable offers" if offers not in (None, "") else "exact EN/NM"


def market_status(source: dict, source_name: str) -> str:
    status = str(source.get("status") or "NOT_QUERIED").upper()
    if status == "OK":
        return f"{source_name}: exact comparable EN/NM ask"
    if status == "VERIFY_FINISH":
        return f"{source_name}: finish/parallel could not be verified — floor withheld"
    if status == "NO_COMPARABLE_EN_NM_ASK":
        return f"{source_name}: no comparable EN/NM ask found"
    if status.startswith("MISSING_"):
        return f"{source_name}: source not available in this refresh"
    if status == "DEGRADED":
        return f"{source_name}: refresh degraded"
    return f"{source_name}: not queried"


def historical_reference_quality(row: dict) -> dict:
    """Consistency diagnostic for product-level Cardmarket summary marks."""
    fields = {
        "Trend": as_float(row.get("trend")),
        "1d": as_float(row.get("avg1")),
        "7d": as_float(row.get("avg7")),
        "30d": as_float(row.get("avg30")),
    }
    values = {label: value for label, value in fields.items() if value is not None and value > 0}
    if len(values) < 3:
        return {
            "label": "⚪ INSUFFICIENT",
            "quality": "INSUFFICIENT",
            "spread_ratio": None,
            "values": values,
            "note": "Fewer than three positive Cardmarket summary marks are available.",
        }
    low = min(values.values())
    high = max(values.values())
    ratio = high / low if low > 0 else None
    if ratio is None:
        quality, label = "INSUFFICIENT", "⚪ INSUFFICIENT"
    elif ratio >= 2.0:
        quality, label = "LOW", "🔴 LOW"
    elif ratio >= 1.35:
        quality, label = "MEDIUM", "🟠 MEDIUM"
    else:
        quality, label = "HIGH", "🟢 HIGH"
    return {
        "label": label,
        "quality": quality,
        "spread_ratio": ratio,
        "values": values,
        "note": "Summary-consistency diagnostic only; historical sales may mix condition/language and must not be treated as an EN/NM realised-price series.",
    }


def index_by_pid(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("id_product")): r for r in rows if r.get("id_product") not in (None, "")}


def compact_stat(label: str, value: str, sub: str | None = None) -> None:
    sub_html = f'<div class="owned-stat-sub">{escape(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="owned-stat"><div class="owned-stat-label">{escape(label)}</div>'
        f'<div class="owned-stat-value">{escape(value)}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def render_price_table(cardmarket: dict, cardtrader: dict, landed: float | None) -> None:
    rows = []
    for source_name, source in (("Cardmarket", cardmarket), ("CardTrader", cardtrader)):
        floor = market_floor(source)
        robust = market_robust_floor(source)
        delta = None if floor is None or landed is None else floor - landed
        rows.append(
            "<tr>"
            f"<td><strong>{escape(source_name)}</strong></td>"
            f"<td>{escape(eur(floor))}</td>"
            f"<td>{escape(eur(robust))}</td>"
            f"<td>{escape(market_depth(source, source_name))}</td>"
            f"<td>{escape(signed_eur(delta))}</td>"
            "</tr>"
        )
    st.markdown(
        '<table class="owned-price-table"><thead><tr><th>Source</th><th>Lowest ask</th>'
        '<th>Robust ask</th><th>Depth</th><th>vs landed</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>",
        unsafe_allow_html=True,
    )
    samples = []
    for label, source in (("CM", cardmarket), ("CT", cardtrader)):
        sample = ask_sample_text(source)
        if sample:
            samples.append(f"{label} cheapest sample: {sample}")
    if samples:
        st.caption(" · ".join(samples))


def result_summary(model_exit: float | None, landed: float | None, model_profit: float | None, model_roi: float | None, route: str | None) -> str:
    if model_exit is not None and landed is not None and model_profit is not None:
        direction = "gain" if model_profit >= 0 else "loss"
        return (
            f"Scanner's current net-exit estimate is {eur(model_exit)} via {friendly_source(route)}, "
            f"which would be a {direction} of {eur(abs(model_profit))} ({abs(model_roi or 0):.1f}%) versus your landed cost."
        )
    return "No routed net-exit estimate exists yet; live asks below are market context, not a sell recommendation."


st.set_page_config(page_title="Owned Pokémon cards", page_icon="🗂️", layout="wide")
st.markdown(
    """
    <style>
    .owned-stat {padding: 0.18rem 0 0.48rem 0;}
    .owned-stat-label {font-size: 0.74rem; opacity: 0.72; line-height: 1.15;}
    .owned-stat-value {font-size: 1.28rem; font-weight: 650; line-height: 1.2; margin-top: 0.12rem;}
    .owned-stat-sub {font-size: 0.70rem; opacity: 0.68; line-height: 1.25; margin-top: 0.12rem;}
    .owned-section-title {font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.035em; margin-top: 0.45rem; margin-bottom: 0.25rem; opacity: 0.82;}
    .owned-summary {font-size: 0.88rem; line-height: 1.45; padding: 0.38rem 0.52rem; border-left: 3px solid rgba(128,128,128,0.45); margin: 0.20rem 0 0.55rem 0;}
    .owned-price-table {width: 100%; border-collapse: collapse; font-size: 0.78rem; margin: 0.10rem 0 0.30rem 0;}
    .owned-price-table th {text-align: left; font-size: 0.69rem; opacity: 0.68; font-weight: 650; padding: 0.30rem 0.32rem; border-bottom: 1px solid rgba(128,128,128,0.30);}
    .owned-price-table td {padding: 0.36rem 0.32rem; border-bottom: 1px solid rgba(128,128,128,0.16); vertical-align: top;}
    </style>
    """,
    unsafe_allow_html=True,
)

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
    "Active asks are competition references, not realised sale prices. Lowest ask = cheapest exact comparable listing. Robust ask = median of the cheapest three comparable asks when available."
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
    return min(vals) if vals else -1e18


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
            cm_robust = market_robust_floor(cm)
            ct_robust = market_robust_floor(ct)
            active_floors = [x for x in (cm_floor, ct_floor) if x is not None]
            robust_floors = [x for x in (cm_robust, ct_robust) if x is not None]
            lowest_ask = min(active_floors) if active_floors else None
            lowest_robust = min(robust_floors) if robust_floors else None
            landed = as_float(card.get("landed_cost_eur"))
            item_paid = as_float(card.get("item_paid_eur"))
            shipping = as_float(card.get("allocated_shipping_eur"))
            model_exit = as_float(route.get("best_sell_net_eur"))
            model_profit = None if model_exit is None or landed is None else model_exit - landed
            model_roi = None if model_profit is None or not landed else (model_profit / landed) * 100.0
            history = historical_reference_quality(tracked_row)

            with st.container(border=True):
                art = image_url(pid, "low")
                if art:
                    art_col, title_col = st.columns([1, 2.8], vertical_alignment="top")
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

                summary = result_summary(model_exit, landed, model_profit, model_roi, route.get("best_sell_channel"))
                st.markdown(f'<div class="owned-summary">{escape(summary)}</div>', unsafe_allow_html=True)

                st.markdown('<div class="owned-section-title">Your position</div>', unsafe_allow_html=True)
                purchase_source = clean_text(card.get("purchase_source")) or "Unknown source"
                purchase_date = clean_text(card.get("purchase_date")) or "date not retained"
                st.caption(f"Bought {purchase_date} on **{purchase_source}** · finish rule: {card.get('finish_requirement') or '—'}")
                p1, p2, p3 = st.columns(3)
                with p1:
                    compact_stat("Card price", eur(item_paid))
                with p2:
                    compact_stat("Allocated shipping", eur(shipping), card.get("shipping_allocation_method") or None)
                with p3:
                    compact_stat("Landed cost", eur(landed))

                st.markdown('<div class="owned-section-title">Live market</div>', unsafe_allow_html=True)
                render_price_table(cm, ct, landed)
                if lowest_ask is not None:
                    literal_room = None if landed is None else lowest_ask - landed
                    robust_room = None if landed is None or lowest_robust is None else lowest_robust - landed
                    st.caption(
                        f"Lowest literal ask {eur(lowest_ask)} ({signed_eur(literal_room)} vs your landed cost)"
                        + (f" · lowest robust ask {eur(lowest_robust)} ({signed_eur(robust_room)} vs landed)" if lowest_robust is not None else "")
                        + ". Active asks are not realised exits."
                    )

                st.markdown('<div class="owned-section-title">Cardmarket history</div>', unsafe_allow_html=True)
                marks = [
                    f"Trend {eur(tracked_row.get('trend'))}",
                    f"1d {eur(tracked_row.get('avg1'))}",
                    f"7d {eur(tracked_row.get('avg7'))}",
                    f"30d {eur(tracked_row.get('avg30'))}",
                ]
                st.markdown(" · ".join(marks) + f" · **Reference confidence {history['label']}**")
                spread = history.get("spread_ratio")
                if spread is not None:
                    st.caption(f"Summary spread {spread:.2f}×. {history['note']}")
                else:
                    st.caption(history["note"])

                if route:
                    st.markdown('<div class="owned-section-title">Scanner view</div>', unsafe_allow_html=True)
                    s1, s2 = st.columns(2)
                    with s1:
                        compact_stat("EU model value", eur(route.get("eu_fair_value_eur")))
                    with s2:
                        compact_stat(
                            "Scanner acquisition reference",
                            eur(route.get("best_validated_buy_eur")),
                            friendly_source(route.get("best_validated_buy_source")),
                        )
                    s3, s4 = st.columns(2)
                    with s3:
                        compact_stat("Modelled net exit", eur(model_exit), friendly_source(route.get("best_sell_channel")))
                    with s4:
                        compact_stat(
                            "Your result at modelled exit",
                            signed_eur(model_profit),
                            signed_pct(model_roi),
                        )

                with st.expander("Purchase details"):
                    st.write({
                        "purchase_date": card.get("purchase_date"),
                        "source": card.get("purchase_source"),
                        "item_paid_eur": item_paid,
                        "allocated_shipping_eur": shipping,
                        "landed_cost_eur": landed,
                        "shipping_allocation": card.get("shipping_allocation_method"),
                        "finish_rule": card.get("finish_requirement"),
                        "language": card.get("language"),
                        "condition": card.get("condition"),
                    })
                    st.caption("Basket shipping is allocated explicitly so the original card price and total invested cost remain separately visible.")

                with st.expander("Market evidence"):
                    st.write({
                        "Cardmarket status": market_status(cm, "Cardmarket"),
                        "Cardmarket lowest ask": cm_floor,
                        "Cardmarket robust ask": cm_robust,
                        "Cardmarket cheapest sample": cm.get("ask_sample_eur"),
                        "Cardmarket floor-to-robust spread %": as_float(cm.get("floor_to_robust_spread_pct")),
                        "CardTrader status": market_status(ct, "CardTrader"),
                        "CardTrader lowest ask": ct_floor,
                        "CardTrader robust ask": ct_robust,
                        "CardTrader cheapest sample": ct.get("ask_sample_eur"),
                        "CardTrader sellers": ct.get("visible_sellers"),
                        "CardTrader units": ct.get("visible_units"),
                        "CardTrader floor-to-robust spread %": as_float(ct.get("floor_to_robust_spread_pct")),
                        "Cardmarket trend": as_float(tracked_row.get("trend")),
                        "Cardmarket 1d average": as_float(tracked_row.get("avg1")),
                        "Cardmarket 7d average": as_float(tracked_row.get("avg7")),
                        "Cardmarket 30d average": as_float(tracked_row.get("avg30")),
                        "historical summary confidence": history.get("quality"),
                        "historical summary spread x": history.get("spread_ratio"),
                    })

                if route:
                    with st.expander("Why this scanner status?"):
                        st.markdown(
                            " · ".join(
                                [
                                    f"**PCS {eur(None) if as_float(route.get('eu_price_confidence_score')) is None else as_float(route.get('eu_price_confidence_score')):.0f}**" if as_float(route.get('eu_price_confidence_score')) is not None else "**PCS —**",
                                    f"**LQS {as_float(route.get('eu_liquidity_score') or route.get('liquidity_score')):.0f}**" if as_float(route.get('eu_liquidity_score') or route.get('liquidity_score')) is not None else "**LQS —**",
                                    f"**ECS {as_float(route.get('exit_confidence_score')):.0f}**" if as_float(route.get('exit_confidence_score')) is not None else "**ECS —**",
                                    f"**BOS {as_float(route.get('bridge_opportunity_score')):.0f}**" if as_float(route.get('bridge_opportunity_score')) is not None else "**BOS —**",
                                ]
                            )
                        )
                        st.caption("PCS = price confidence · LQS = liquidity · ECS = exit confidence · BOS = bridge support")
                        if route.get("quality_gate_reason"):
                            st.write(route.get("quality_gate_reason"))
                    if prediction:
                        st.caption("Immutable forecast exists for this card.")

st.divider()
st.caption(
    "UX rule: your cost basis and source-by-source market evidence come before scanner diagnostics. Robust asks and historical consistency are diagnostics only; the dashboard does not invent a new BUY/SELL gate."
)
