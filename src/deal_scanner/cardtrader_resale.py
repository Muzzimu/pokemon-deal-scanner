from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path


CT_RESALE_FIELDS = [
    "snapshot_date", "id_product", "name", "expansion_name", "number",
    "acquisition_source", "acquisition_seller", "acquisition_eur",
    "ct_direct_floor_eur", "ct_direct_target_eur", "ct_direct_sellers", "ct_direct_units",
    "ct_direct_fee_eur", "ct_direct_operational_reserve_eur", "ct_direct_net_eur",
    "ct_zero_floor_eur", "ct_zero_target_eur", "ct_zero_sellers", "ct_zero_units",
    "ct_zero_fee_eur", "ct_zero_operational_reserve_eur", "ct_zero_net_eur",
    "best_ct_channel", "best_ct_gross_eur", "best_ct_net_eur",
    "net_spread_eur", "net_roi_pct", "ct_signal", "confidence", "notes",
]

MARKET_ROUTE_FIELDS = [
    "snapshot_date", "id_product", "name", "expansion_name", "number",
    "best_validated_buy_source", "best_validated_buy_eur", "buy_seller",
    "cardtrader_observed_buy_floor_eur",
    "cardmarket_trend_eur", "ebay_expected_eur", "consensus_value_eur",
    "ct_direct_gross_eur", "ct_direct_net_eur",
    "ct_zero_gross_eur", "ct_zero_net_eur",
    "ebay_gross_eur", "ebay_net_eur",
    "best_sell_channel", "best_sell_gross_eur", "best_sell_net_eur",
    "net_spread_eur", "net_roi_pct", "route_signal", "confidence", "notes",
]


def _float(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _latest_ct_snapshot(conn) -> str | None:
    row = conn.execute("SELECT MAX(snapshot_date) AS d FROM cardtrader_offer_snapshots").fetchone()
    return str(row["d"]) if row and row["d"] else None


def _latest_cm_trend(conn, id_product: int) -> float | None:
    row = conn.execute(
        """SELECT trend FROM price_snapshots
           WHERE id_product=? ORDER BY snapshot_date DESC LIMIT 1""",
        (id_product,),
    ).fetchone()
    return _float(row["trend"]) if row else None


def _best_sourcing_rows(path: Path) -> dict[int, dict]:
    """Choose the cheapest validated/risk-adjusted landed Cardmarket route per product."""
    best: dict[int, dict] = {}
    for row in _read_csv(path):
        # WAIT can still be a valid source: it only means the card failed a
        # product-specific buy threshold. INELIGIBLE/VERIFY_LANDED are not usable.
        if str(row.get("decision") or "") in {"INELIGIBLE", "VERIFY_LANDED"}:
            continue
        landed = _float(row.get("risk_adjusted_landed_eur"))
        if landed is None or landed <= 0:
            continue
        try:
            pid = int(row.get("id_product") or 0)
        except (TypeError, ValueError):
            continue
        if pid <= 0:
            continue
        if pid not in best or landed < float(best[pid]["_landed"]):
            best[pid] = {**row, "_landed": landed}
    return best


def _strength_rank(value: str) -> int:
    return {"STRONG": 0, "MEDIUM": 1, "WEAK": 2, "VERY_WEAK": 3, "NONE": 9}.get(
        str(value or "NONE").upper(), 9
    )


def _best_ebay_rows(path: Path) -> dict[int, dict]:
    """Collapse resale output to one conservative exit reference per product."""
    grouped: dict[int, list[dict]] = {}
    for row in _read_csv(path):
        expected = _float(row.get("expected_resale_eur"))
        if expected is None or expected <= 0:
            continue
        try:
            pid = int(row.get("id_product") or 0)
        except (TypeError, ValueError):
            continue
        if pid > 0:
            grouped.setdefault(pid, []).append(row)

    out: dict[int, dict] = {}
    for pid, rows in grouped.items():
        # Prefer stronger evidence; when evidence strength ties, use the lower
        # expected exit to avoid optimistic route selection.
        rows.sort(key=lambda r: (
            _strength_rank(str(r.get("reference_strength") or "NONE")),
            _float(r.get("expected_resale_eur")) or 999999.0,
        ))
        out[pid] = rows[0]
    return out


def _channel_summary(offers: list[dict], undercut_eur: float) -> dict | None:
    if not offers:
        return None

    # One seller can expose more than one row for the same mapped printing. Use
    # that seller's cheapest row for seller-depth calculations while keeping total
    # visible units from all rows.
    by_seller: dict[str, dict] = {}
    for offer in offers:
        price = _float(offer.get("price_eur"))
        if price is None or price <= 0:
            continue
        key = str(offer.get("seller_id") or offer.get("seller_username") or offer.get("offer_id") or "")
        current = by_seller.get(key)
        if current is None or price < float(current["price_eur"]):
            by_seller[key] = {**offer, "price_eur": price}
    if not by_seller:
        return None

    seller_rows = sorted(by_seller.values(), key=lambda r: float(r["price_eur"]))
    floor = float(seller_rows[0]["price_eur"])
    target = max(0.01, round(floor - max(0.0, undercut_eur), 2))
    return {
        "floor_eur": round(floor, 2),
        "target_eur": target,
        "visible_sellers": len(seller_rows),
        "visible_units": sum(max(1, _int(o.get("quantity"), 1)) for o in offers),
        "second_seller_eur": round(float(seller_rows[1]["price_eur"]), 2) if len(seller_rows) >= 2 else None,
    }


def _ct_market_summary(conn, snapshot_date: str, cfg: dict) -> dict[int, dict]:
    rcfg = cfg.get("cardtrader_resale", {})
    excluded_names = {
        str(x).strip().lower()
        for x in (rcfg.get("excluded_seller_usernames") or [])
        if str(x).strip()
    }
    undercut = float(rcfg.get("undercut_eur", 0.01))

    rows = conn.execute(
        """
        SELECT offer_id,id_product,seller_id,seller_username,quantity,price_eur,ct_zero
        FROM cardtrader_offer_snapshots
        WHERE snapshot_date=?
          AND id_product IS NOT NULL
          AND price_eur IS NOT NULL
          AND language='en'
          AND lower(condition) IN ('near mint','near_mint','nm')
          AND graded=0 AND on_vacation=0
        """,
        (snapshot_date,),
    ).fetchall()

    grouped: dict[int, list[dict]] = {}
    for raw in rows:
        row = dict(raw)
        username = str(row.get("seller_username") or "").strip().lower()
        if username and username in excluded_names:
            continue
        pid = int(row["id_product"])
        grouped.setdefault(pid, []).append(row)

    out: dict[int, dict] = {}
    for pid, offers in grouped.items():
        out[pid] = {
            "direct": _channel_summary(offers, undercut),
            "zero": _channel_summary([o for o in offers if _int(o.get("ct_zero")) == 1], undercut),
        }
    return out


def _fee(gross: float, pct: float, vat_pct: float, minimum_fee_eur: float) -> float:
    base = max(minimum_fee_eur, gross * pct / 100.0)
    return round(base * (1.0 + vat_pct / 100.0), 2)


def _channel_financials(summary: dict | None, cfg: dict, channel: str) -> dict | None:
    if not summary:
        return None
    rcfg = cfg.get("cardtrader_resale", {})
    gross = _float(summary.get("target_eur"))
    if gross is None:
        return None
    if channel == "CARDTRADER_ZERO":
        pct = float(rcfg.get("zero_fee_pct", 7.3))
        reserve = float(rcfg.get("zero_operational_reserve_eur", 0.50))
    else:
        pct = float(rcfg.get("direct_fee_pct", 5.3))
        reserve = float(rcfg.get("direct_operational_reserve_eur", 0.15))
    fee = _fee(
        gross,
        pct,
        float(rcfg.get("fee_vat_pct", 23.0)),
        float(rcfg.get("minimum_fee_eur", 0.01)),
    )
    net = round(gross - fee - reserve, 2)
    return {
        **summary,
        "channel": channel,
        "gross_eur": round(gross, 2),
        "fee_eur": fee,
        "reserve_eur": round(reserve, 2),
        "net_eur": net,
    }


def _ct_confidence(channel: dict | None) -> str:
    if not channel:
        return "NONE"
    sellers = int(channel.get("visible_sellers") or 0)
    if sellers >= 3:
        return "MEDIUM"
    if sellers == 2:
        return "LOW_MEDIUM"
    return "LOW"


def _consensus_value(cm_trend: float | None, ebay: dict | None) -> float | None:
    values: list[float] = []
    if cm_trend is not None and cm_trend > 0:
        values.append(cm_trend)
    if ebay and str(ebay.get("reference_strength") or "").upper() in {"STRONG", "MEDIUM"}:
        expected = _float(ebay.get("expected_resale_eur"))
        if expected is not None and expected > 0:
            values.append(expected)
    if not values:
        return None
    return round(float(statistics.median(values)), 2)


def generate_cardtrader_resale_reports(
    conn,
    cfg: dict,
    sourcing_path: Path,
    ebay_resale_path: Path,
    ct_output_path: Path,
    route_output_path: Path,
) -> dict:
    """Build CardTrader exit candidates and a cross-market buy/value/sell route table."""
    sourcing = _best_sourcing_rows(sourcing_path)
    ebay = _best_ebay_rows(ebay_resale_path)
    snapshot_date = _latest_ct_snapshot(conn)

    if not snapshot_date:
        _write_csv(ct_output_path, [], CT_RESALE_FIELDS)
        _write_csv(route_output_path, [], MARKET_ROUTE_FIELDS)
        return {
            "enabled": False,
            "reason": "no CardTrader marketplace snapshot",
            "candidate_rows": 0,
            "route_rows": 0,
        }

    ct_market = _ct_market_summary(conn, snapshot_date, cfg)
    rcfg = cfg.get("cardtrader_resale", {})
    min_spread = float(rcfg.get("minimum_net_spread_eur", cfg.get("resale", {}).get("minimum_gross_spread_eur", 2.0)))
    min_roi = float(rcfg.get("minimum_net_roi_pct", cfg.get("resale", {}).get("minimum_gross_roi_pct", 25.0)))
    min_sellers = int(rcfg.get("minimum_competing_sellers", 2))
    ebay_exit_pct = float(rcfg.get("ebay_exit_cost_pct", cfg.get("arbitrage", {}).get("exit_cost_pct", 8.0)))

    ct_rows: list[dict] = []
    route_rows: list[dict] = []

    for pid, src in sourcing.items():
        acquisition = float(src["_landed"])
        market = ct_market.get(pid, {})
        direct = _channel_financials(market.get("direct"), cfg, "CARDTRADER_DIRECT")
        zero = _channel_financials(market.get("zero"), cfg, "CARDTRADER_ZERO")

        ct_options = [x for x in (direct, zero) if x is not None]
        best_ct = max(ct_options, key=lambda x: float(x["net_eur"])) if ct_options else None

        if best_ct:
            ct_spread = round(float(best_ct["net_eur"]) - acquisition, 2)
            ct_roi = round(ct_spread / acquisition * 100.0, 1) if acquisition > 0 else 0.0
            seller_depth = int(best_ct.get("visible_sellers") or 0)
            edge = ct_spread >= min_spread and ct_roi >= min_roi
            if edge and seller_depth >= min_sellers:
                ct_signal = "RESELL_TEST"
            elif edge:
                ct_signal = "WATCH_ONLY"
            else:
                ct_signal = "NO_EDGE"
            ct_conf = _ct_confidence(best_ct)

            notes = [
                "CardTrader values are active English/NM marketplace asks, not confirmed sales",
                f"seller depth={seller_depth}",
            ]
            if seller_depth < min_sellers:
                notes.append(f"requires >= {min_sellers} competing sellers for RESELL_TEST")
            ct_rows.append({
                "snapshot_date": snapshot_date,
                "id_product": pid,
                "name": src.get("name") or "",
                "expansion_name": src.get("expansion_name") or "",
                "number": src.get("number") or "",
                "acquisition_source": "CARDMARKET_VALIDATED_LANDED",
                "acquisition_seller": src.get("seller") or "",
                "acquisition_eur": round(acquisition, 2),
                "ct_direct_floor_eur": None if not direct else direct.get("floor_eur"),
                "ct_direct_target_eur": None if not direct else direct.get("gross_eur"),
                "ct_direct_sellers": 0 if not direct else direct.get("visible_sellers"),
                "ct_direct_units": 0 if not direct else direct.get("visible_units"),
                "ct_direct_fee_eur": None if not direct else direct.get("fee_eur"),
                "ct_direct_operational_reserve_eur": None if not direct else direct.get("reserve_eur"),
                "ct_direct_net_eur": None if not direct else direct.get("net_eur"),
                "ct_zero_floor_eur": None if not zero else zero.get("floor_eur"),
                "ct_zero_target_eur": None if not zero else zero.get("gross_eur"),
                "ct_zero_sellers": 0 if not zero else zero.get("visible_sellers"),
                "ct_zero_units": 0 if not zero else zero.get("visible_units"),
                "ct_zero_fee_eur": None if not zero else zero.get("fee_eur"),
                "ct_zero_operational_reserve_eur": None if not zero else zero.get("reserve_eur"),
                "ct_zero_net_eur": None if not zero else zero.get("net_eur"),
                "best_ct_channel": best_ct["channel"],
                "best_ct_gross_eur": best_ct["gross_eur"],
                "best_ct_net_eur": best_ct["net_eur"],
                "net_spread_eur": ct_spread,
                "net_roi_pct": ct_roi,
                "ct_signal": ct_signal,
                "confidence": ct_conf,
                "notes": "; ".join(notes),
            })

        cm_trend = _latest_cm_trend(conn, pid)
        ebay_row = ebay.get(pid)
        ebay_gross = _float(ebay_row.get("expected_resale_eur")) if ebay_row else None
        ebay_net = None if ebay_gross is None else round(ebay_gross * (1.0 - ebay_exit_pct / 100.0), 2)

        sell_options: list[dict] = []
        if direct:
            sell_options.append({
                "channel": "CARDTRADER_DIRECT",
                "gross": float(direct["gross_eur"]),
                "net": float(direct["net_eur"]),
                "confidence": _ct_confidence(direct),
                "sellers": int(direct.get("visible_sellers") or 0),
            })
        if zero:
            sell_options.append({
                "channel": "CARDTRADER_ZERO",
                "gross": float(zero["gross_eur"]),
                "net": float(zero["net_eur"]),
                "confidence": _ct_confidence(zero),
                "sellers": int(zero.get("visible_sellers") or 0),
            })
        if ebay_gross is not None and ebay_net is not None:
            strength = str(ebay_row.get("reference_strength") or "NONE").upper() if ebay_row else "NONE"
            sell_options.append({
                "channel": "EBAY_IE_EU",
                "gross": ebay_gross,
                "net": ebay_net,
                "confidence": "HIGH" if strength == "STRONG" else ("MEDIUM" if strength == "MEDIUM" else "LOW"),
                "sellers": 999 if strength in {"STRONG", "MEDIUM"} else 0,
            })

        best_sell = max(sell_options, key=lambda x: float(x["net"])) if sell_options else None
        if best_sell:
            spread = round(float(best_sell["net"]) - acquisition, 2)
            roi = round(spread / acquisition * 100.0, 1) if acquisition > 0 else 0.0
            edge = spread >= min_spread and roi >= min_roi
            if best_sell["channel"].startswith("CARDTRADER"):
                actionable_depth = int(best_sell.get("sellers") or 0) >= min_sellers
            else:
                actionable_depth = best_sell.get("confidence") in {"HIGH", "MEDIUM"}
            if edge and actionable_depth:
                route_signal = "RESELL_TEST"
            elif edge:
                route_signal = "WATCH_ONLY"
            else:
                route_signal = "NO_EDGE"
            route_conf = str(best_sell.get("confidence") or "LOW")
        else:
            spread = roi = None
            route_signal = "INSUFFICIENT_EXIT_REFERENCE"
            route_conf = "LOW"

        observed_ct_floor = None
        if market.get("direct"):
            observed_ct_floor = _float(market["direct"].get("floor_eur"))

        route_notes = [
            "Validated buy cost is landed/risk-adjusted Cardmarket evidence",
            "CardTrader observed floor is article price only and is not a landed buy cost",
        ]
        if ebay_row:
            route_notes.append(
                f"eBay reference={ebay_row.get('reference_type') or ''}/{ebay_row.get('reference_strength') or ''}"
            )
        route_rows.append({
            "snapshot_date": snapshot_date,
            "id_product": pid,
            "name": src.get("name") or "",
            "expansion_name": src.get("expansion_name") or "",
            "number": src.get("number") or "",
            "best_validated_buy_source": "CARDMARKET_VALIDATED_LANDED",
            "best_validated_buy_eur": round(acquisition, 2),
            "buy_seller": src.get("seller") or "",
            "cardtrader_observed_buy_floor_eur": observed_ct_floor,
            "cardmarket_trend_eur": cm_trend,
            "ebay_expected_eur": ebay_gross,
            "consensus_value_eur": _consensus_value(cm_trend, ebay_row),
            "ct_direct_gross_eur": None if not direct else direct.get("gross_eur"),
            "ct_direct_net_eur": None if not direct else direct.get("net_eur"),
            "ct_zero_gross_eur": None if not zero else zero.get("gross_eur"),
            "ct_zero_net_eur": None if not zero else zero.get("net_eur"),
            "ebay_gross_eur": ebay_gross,
            "ebay_net_eur": ebay_net,
            "best_sell_channel": "" if not best_sell else best_sell["channel"],
            "best_sell_gross_eur": None if not best_sell else round(float(best_sell["gross"]), 2),
            "best_sell_net_eur": None if not best_sell else round(float(best_sell["net"]), 2),
            "net_spread_eur": spread,
            "net_roi_pct": roi,
            "route_signal": route_signal,
            "confidence": route_conf,
            "notes": "; ".join(route_notes),
        })

    signal_order = {"RESELL_TEST": 0, "WATCH_ONLY": 1, "NO_EDGE": 2}
    ct_rows.sort(key=lambda r: (
        signal_order.get(str(r.get("ct_signal")), 99),
        -(float(r.get("net_roi_pct")) if r.get("net_roi_pct") not in (None, "") else -999999),
        -(float(r.get("net_spread_eur")) if r.get("net_spread_eur") not in (None, "") else -999999),
    ))
    route_order = {"RESELL_TEST": 0, "WATCH_ONLY": 1, "NO_EDGE": 2, "INSUFFICIENT_EXIT_REFERENCE": 3}
    route_rows.sort(key=lambda r: (
        route_order.get(str(r.get("route_signal")), 99),
        -(float(r.get("net_roi_pct")) if r.get("net_roi_pct") not in (None, "") else -999999),
    ))

    _write_csv(ct_output_path, ct_rows, CT_RESALE_FIELDS)
    _write_csv(route_output_path, route_rows, MARKET_ROUTE_FIELDS)

    return {
        "enabled": bool(cfg.get("cardtrader_resale", {}).get("enabled", True)),
        "snapshot_date": snapshot_date,
        "validated_sourcing_products": len(sourcing),
        "cardtrader_covered_products": sum(1 for pid in sourcing if pid in ct_market),
        "candidate_rows": len(ct_rows),
        "resell_test_rows": sum(1 for r in ct_rows if r["ct_signal"] == "RESELL_TEST"),
        "watch_only_rows": sum(1 for r in ct_rows if r["ct_signal"] == "WATCH_ONLY"),
        "route_rows": len(route_rows),
        "route_resell_test_rows": sum(1 for r in route_rows if r["route_signal"] == "RESELL_TEST"),
        "note": (
            "CardTrader exit values are active English/NM competitive asks. Net proceeds subtract configured "
            "Direct/Zero seller commission, VAT on commission and operating reserves; they are not confirmed sales."
        ),
    }
