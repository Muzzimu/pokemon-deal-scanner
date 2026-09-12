from pathlib import Path

PATH = Path("dashboard/app.py")
text = PATH.read_text(encoding="utf-8")
start = text.index("\ndef owned_floor")
end = text.index("\nst.set_page_config", start)

new_block = r'''
def owned_floor(row: dict, source_name: str):
    source = row.get(source_name) or {}
    if not isinstance(source, dict) or str(source.get("status") or "").upper() != "OK":
        return None
    return as_float(source.get("floor_eur"))


def owned_robust_floor(row: dict, source_name: str):
    source = row.get(source_name) or {}
    if not isinstance(source, dict) or str(source.get("status") or "").upper() != "OK":
        return None
    return as_float(source.get("robust_floor_eur"))


def owned_ask_sample(row: dict, source_name: str) -> str | None:
    source = row.get(source_name) or {}
    values = source.get("ask_sample_eur") if isinstance(source, dict) else None
    if not isinstance(values, list) or not values:
        return None
    return " / ".join(format_eur(v) for v in values)


def owned_market_depth(row: dict, source_name: str, label: str) -> str:
    source = row.get(source_name) or {}
    if not isinstance(source, dict):
        return "not queried"
    status = str(source.get("status") or "NOT_QUERIED").upper()
    if status != "OK":
        return {
            "VERIFY_FINISH": "finish unverified",
            "NO_COMPARABLE_EN_NM_ASK": "no exact ask",
            "DEGRADED": "refresh degraded",
        }.get(status, "source unavailable" if status.startswith("MISSING_") else "not queried")
    if source_name == "cardtrader":
        bits = []
        if source.get("visible_sellers") not in (None, ""):
            bits.append(f"{source.get('visible_sellers')} sellers")
        if source.get("visible_units") not in (None, ""):
            bits.append(f"{source.get('visible_units')} cards")
        return " · ".join(bits) if bits else "exact EN/NM"
    offers = source.get("visible_offer_rows")
    return f"{offers} comparable offers" if offers not in (None, "") else "exact EN/NM"


def owned_source_caption(row: dict, source_name: str, label: str) -> str:
    source = row.get(source_name) or {}
    if not isinstance(source, dict):
        return f"{label}: not queried"
    status = str(source.get("status") or "NOT_QUERIED").upper()
    if status == "OK":
        bits = [f"{label}: exact comparable EN/NM ask"]
        sample = owned_ask_sample(row, source_name)
        if sample:
            bits.append(f"cheapest sample {sample}")
        return " · ".join(bits)
    if status == "VERIFY_FINISH":
        return f"{label}: finish/parallel not verified — floor withheld"
    if status == "NO_COMPARABLE_EN_NM_ASK":
        return f"{label}: no comparable EN/NM ask found"
    if status.startswith("MISSING_"):
        return f"{label}: source unavailable in this refresh"
    if status == "DEGRADED":
        return f"{label}: refresh degraded"
    return f"{label}: not queried"


def signed_eur(value) -> str:
    amount = as_float(value)
    if amount is None:
        return "—"
    if amount > 0:
        return f"+€{amount:,.2f}"
    if amount < 0:
        return f"-€{abs(amount):,.2f}"
    return "€0.00"


def signed_pct(value) -> str:
    amount = as_float(value)
    return "—" if amount is None else f"{amount:+.1f}%"


def compact_stat(label: str, value: str, sub: str | None = None) -> None:
    st.caption(label)
    st.markdown(f"#### {value}")
    if sub:
        st.caption(sub)


def friendly_reference_source(value) -> str:
    raw = clean_text(value)
    if not raw:
        return "source not retained"
    known = {
        "CARDTRADER_EN_NM": "CardTrader EN/NM ask",
        "CARDMARKET_EN_NM": "Cardmarket EN/NM ask",
        "CARDTRADER_DIRECT": "CardTrader Direct",
        "CARDTRADER_ZERO": "CardTrader Zero",
    }
    return known.get(raw.upper(), raw.replace("_", " ").title())


def owned_history_quality(row: dict) -> dict:
    values = {
        "Trend": as_float(row.get("trend")),
        "1d": as_float(row.get("avg1")),
        "7d": as_float(row.get("avg7")),
        "30d": as_float(row.get("avg30")),
    }
    positive = {k: v for k, v in values.items() if v is not None and v > 0}
    if len(positive) < 3:
        return {"label": "⚪ INSUFFICIENT", "ratio": None}
    low, high = min(positive.values()), max(positive.values())
    ratio = high / low if low > 0 else None
    if ratio is None:
        return {"label": "⚪ INSUFFICIENT", "ratio": None}
    if ratio >= 2.0:
        label = "🔴 LOW"
    elif ratio >= 1.35:
        label = "🟠 MEDIUM"
    else:
        label = "🟢 HIGH"
    return {"label": label, "ratio": ratio}


def render_owned_price_table(row: dict, landed: float | None) -> None:
    lines = [
        "| Source | Lowest ask | Robust ask | Depth | vs landed |",
        "|---|---:|---:|---|---:|",
    ]
    for source_name, label in (("cardmarket", "Cardmarket"), ("cardtrader", "CardTrader")):
        floor = owned_floor(row, source_name)
        robust = owned_robust_floor(row, source_name)
        delta = None if floor is None or landed is None else floor - landed
        lines.append(
            f"| **{label}** | {format_eur(floor)} | {format_eur(robust)} | "
            f"{owned_market_depth(row, source_name, label)} | {signed_eur(delta)} |"
        )
    st.markdown("\n".join(lines))
    samples = []
    for source_name, label in (("cardmarket", "CM"), ("cardtrader", "CT")):
        sample = owned_ask_sample(row, source_name)
        if sample:
            samples.append(f"{label} cheapest sample: {sample}")
    if samples:
        st.caption(" · ".join(samples))


def owned_result_summary(row: dict, landed: float | None) -> tuple[str, float | None, float | None]:
    model_exit = as_float(row.get("best_sell_net_eur"))
    if model_exit is None or landed is None:
        return "No routed net-exit estimate yet; live asks are market context, not a sell recommendation.", None, None
    profit = model_exit - landed
    roi = (profit / landed * 100.0) if landed else None
    direction = "gain" if profit >= 0 else "loss"
    return (
        f"Current modelled net exit is {format_eur(model_exit)} via {human_channel(row.get('best_sell_channel'))}. "
        f"Against your landed cost, that implies a {direction} of {format_eur(abs(profit))} ({abs(roi or 0):.1f}%).",
        profit,
        roi,
    )


def render_owned_position(row: dict, routed: bool) -> None:
    landed = as_float(row.get("landed_cost_eur"))
    item_paid = as_float(row.get("item_paid_eur"))
    shipping = as_float(row.get("allocated_shipping_eur"))
    summary, owner_profit, owner_roi = owned_result_summary(row, landed)
    st.markdown(f"**What it means:** {summary}")

    st.markdown("**Your position**")
    purchase_source = clean_text(row.get("purchase_source")) or "Unknown source"
    purchase_date = clean_text(row.get("purchase_date")) or "date not retained"
    st.caption(
        f"Bought {purchase_date} on **{purchase_source}** · {clean_text(row.get('language')) or '—'} / "
        f"{clean_text(row.get('condition')) or '—'} · finish rule {clean_text(row.get('finish_requirement')) or '—'}"
    )
    p1, p2, p3 = st.columns(3)
    with p1:
        compact_stat("Card price", format_eur(item_paid))
    with p2:
        compact_stat("Allocated shipping", format_eur(shipping))
    with p3:
        compact_stat("Landed cost", format_eur(landed))

    st.markdown("**Live pricing**")
    render_owned_price_table(row, landed)
    st.caption("Active asks are competition references, not realised exits. Robust ask = median of the cheapest three exact comparable asks when available.")

    history = owned_history_quality(row)
    marks = (
        f"Trend {format_eur(row.get('trend'))} · 1d {format_eur(row.get('avg1'))} · "
        f"7d {format_eur(row.get('avg7'))} · 30d {format_eur(row.get('avg30'))}"
    )
    st.markdown(f"**Cardmarket history:** {marks} · reference confidence **{history['label']}**")
    if history.get("ratio") is not None:
        st.caption(f"Summary spread {history['ratio']:.2f}×. Product-level history may mix condition/language and is not treated as a clean EN/NM realised-price series.")

    if routed:
        st.markdown("**Scanner view**")
        s1, s2 = st.columns(2)
        with s1:
            compact_stat("EU model value", format_eur(row.get("eu_fair_value_eur")))
        with s2:
            compact_stat(
                "Scanner acquisition reference",
                format_eur(row.get("best_validated_buy_eur")),
                friendly_reference_source(row.get("best_validated_buy_source")),
            )
        s3, s4 = st.columns(2)
        with s3:
            compact_stat("Modelled net exit", format_eur(row.get("best_sell_net_eur")), human_channel(row.get("best_sell_channel")))
        with s4:
            compact_stat("Your result", signed_eur(owner_profit), signed_pct(owner_roi))

        with st.expander("Why this scanner status?"):
            explanation = plain_gate_explanation(row)
            if explanation:
                st.markdown(explanation)
            render_score_line(row)
            st.caption("PCS = price confidence · LQS = liquidity · ECS = exit confidence · BOS = bridge support")
            raw_reason = clean_text(row.get("quality_gate_reason"))
            if raw_reason:
                st.code(raw_reason)

        with st.expander("Market evidence"):
            st.markdown(f"**Market state:** {market_trend_text(row)} · confidence {trend_confidence_text(row)}")
            render_market_profile(row, expanded=True)
            st.caption(owned_source_caption(row, "cardmarket", "Cardmarket"))
            st.caption(owned_source_caption(row, "cardtrader", "CardTrader"))
    else:
        with st.expander("Market evidence"):
            st.write({
                "Cardmarket trend": format_eur(row.get("trend")),
                "30d average": format_eur(row.get("avg30")),
                "7d average": format_eur(row.get("avg7")),
                "1d average": format_eur(row.get("avg1")),
                "purchase date": row.get("purchase_date"),
                "purchase source": row.get("purchase_source"),
                "allocated shipping": format_eur(row.get("allocated_shipping_eur")),
                "finish rule": row.get("finish_requirement"),
            })
            st.caption(owned_source_caption(row, "cardmarket", "Cardmarket"))
            st.caption(owned_source_caption(row, "cardtrader", "CardTrader"))


def render_route_card(row: dict) -> None:
    with st.container(border=True):
        render_card_title(row)
        st.markdown(f"**{signal_label(row.get('route_signal'))}**")
        owner_landed = as_float(row.get("landed_cost_eur"))
        if owner_landed is not None:
            render_owned_position(row, routed=True)
            return

        st.markdown(f"**Exit route:** {human_channel(row.get('best_sell_channel'))}")
        p1, p2 = st.columns(2)
        p1.metric("Scanner validated buy", format_eur(row.get("best_validated_buy_eur")))
        p2.metric("EU fair value", format_eur(row.get("eu_fair_value_eur")))
        p3, p4 = st.columns(2)
        p3.metric("Modelled net exit", format_eur(row.get("best_sell_net_eur")))
        p4.metric("Scanner modelled net profit", format_eur(row.get("net_spread_eur")))
        st.markdown(f"**Scanner modelled ROI:** {format_pct(row.get('net_roi_pct'))}")
        position = eu_position_text(row)
        if position:
            st.caption(position)
        render_score_line(row)
        st.caption(f"Market: {market_trend_text(row)} · confidence {trend_confidence_text(row)}")
        render_market_profile(row)
        explanation = plain_gate_explanation(row)
        if explanation:
            st.markdown(f"**Why not actionable:** {explanation}")
        raw_reason = clean_text(row.get("quality_gate_reason"))
        if raw_reason:
            with st.expander("Show numeric gate detail"):
                st.code(raw_reason)


def render_tracked_card(row: dict) -> None:
    with st.container(border=True):
        render_card_title(row)
        st.markdown("**🟣 OWNED REVIEW**")
        render_owned_position(row, routed=False)
        st.caption("No BUY/SELL signal is fabricated when an owned card is not routed.")
'''

patched = text[:start] + "\n" + new_block.strip("\n") + "\n\n" + text[end:]
if patched == text:
    raise SystemExit("No changes produced")
PATH.write_text(patched, encoding="utf-8")
print("Patched dashboard/app.py owned-card layout")
