from __future__ import annotations

import csv
import json
import math
from datetime import date
from pathlib import Path

import requests


ARBITRAGE_FIELDS = [
    "snapshot_date", "id_product", "name", "source_platform", "source_region",
    "source_url", "source_price", "source_currency", "fx_to_eur", "fx_source",
    "acquisition_eur", "friction_reserve_eur", "landed_eur",
    "cardmarket_en_nm_eur", "cardmarket_trend_eur", "ebay_reference_eur",
    "chosen_exit_reference_eur", "reference_type", "reference_strength",
    "estimated_exit_after_costs_eur", "net_spread_eur", "net_roi_pct",
    "exact_printing_verified", "language_status", "condition_status",
    "arbitrage_signal", "confidence", "notes",
]


def _float(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def fetch_fx_rates(cfg: dict) -> dict:
    """Return currency->EUR multipliers, degrading confidence on configured fallback."""
    fcfg = cfg.get("fx", {})
    timeout = float(fcfg.get("timeout_seconds", 10))
    url = str(fcfg.get("url", "https://api.frankfurter.app/latest?from=EUR&to=GBP,USD"))
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": "PokemonDealScanner/0.7"})
        response.raise_for_status()
        payload = response.json()
        rates = payload.get("rates") or {}
        gbp_per_eur = float(rates["GBP"])
        usd_per_eur = float(rates["USD"])
        if gbp_per_eur <= 0 or usd_per_eur <= 0:
            raise ValueError("non-positive FX rate")
        return {
            "rates": {"EUR": 1.0, "GBP": 1.0 / gbp_per_eur, "USD": 1.0 / usd_per_eur},
            "source": f"LIVE:{payload.get('date') or 'Frankfurter'}",
            "live": True,
            "error": "",
        }
    except Exception as exc:
        gbp = _float(fcfg.get("fallback_gbp_to_eur"))
        usd = _float(fcfg.get("fallback_usd_to_eur"))
        rates = {"EUR": 1.0}
        if gbp:
            rates["GBP"] = gbp
        if usd:
            rates["USD"] = usd
        return {
            "rates": rates,
            "source": "CONFIG_FALLBACK",
            "live": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _to_eur(value, currency: str, fx: dict) -> float | None:
    amount = _float(value)
    rate = _float((fx.get("rates") or {}).get(str(currency or "").upper()))
    if amount is None or rate is None:
        return None
    return round(amount * rate, 2)


def _latest_cm(conn, id_product: int) -> tuple[float | None, float | None, str]:
    override = conn.execute(
        """SELECT en_nm_floor_eur,checked_at FROM cardmarket_en_nm_overrides
           WHERE id_product=?""",
        (id_product,),
    ).fetchone()
    floor = _float(override["en_nm_floor_eur"]) if override else None
    checked = str(override["checked_at"] or "") if override else ""
    snap = conn.execute(
        """SELECT trend FROM price_snapshots WHERE id_product=?
           ORDER BY snapshot_date DESC LIMIT 1""",
        (id_product,),
    ).fetchone()
    trend = _float(snap["trend"]) if snap else None
    return floor, trend, checked


def _best_ebay_reference_eur(conn, id_product: int, fx: dict) -> dict | None:
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ebay_reference_history'"
    ).fetchone()
    if not table:
        return None
    latest = conn.execute(
        "SELECT MAX(snapshot_date) AS d FROM ebay_reference_history WHERE id_product=?",
        (id_product,),
    ).fetchone()
    if not latest or not latest["d"]:
        return None
    rows = conn.execute(
        """SELECT region,currency,chosen_reference,reference_type,strength
           FROM ebay_reference_history
           WHERE id_product=? AND snapshot_date=? AND chosen_reference IS NOT NULL""",
        (id_product, latest["d"]),
    ).fetchall()
    strength_order = {"STRONG": 0, "MEDIUM": 1, "WEAK": 2, "VERY_WEAK": 3, "NONE": 9}
    region_order = {"IRELAND": 0, "EU": 1, "UK": 2, "GLOBAL": 3}
    candidates = []
    for row in rows:
        eur = _to_eur(row["chosen_reference"], row["currency"], fx)
        if eur is None:
            continue
        candidates.append({
            "eur": eur,
            "type": str(row["reference_type"]),
            "strength": str(row["strength"]),
            "region": str(row["region"]),
        })
    if not candidates:
        return None
    candidates.sort(key=lambda r: (
        strength_order.get(r["strength"], 9),
        region_order.get(r["region"], 9),
        r["eur"],
    ))
    return candidates[0]


def _product_name(conn, id_product: int) -> str:
    row = conn.execute("SELECT name FROM products WHERE id_product=?", (id_product,)).fetchone()
    return str(row["name"]) if row else f"Product {id_product}"


def _region_friction(acquisition_eur: float, region: str, cfg: dict) -> float:
    rcfg = cfg.get("arbitrage", {}).get("regions", {}).get(region, {})
    fixed = float(rcfg.get("fixed_friction_eur", 0))
    pct = float(rcfg.get("friction_pct", 0))
    return round(fixed + acquisition_eur * pct / 100.0, 2)


def _choose_exit_reference(cm_floor: float | None, ebay: dict | None) -> tuple[float | None, str, str]:
    refs: list[tuple[float, str, str]] = []
    if cm_floor is not None:
        refs.append((cm_floor, "CARDMARKET_VALIDATED_EN_NM", "MEDIUM"))
    if ebay and ebay.get("strength") in {"STRONG", "MEDIUM"}:
        refs.append((
            float(ebay["eur"]),
            f"EBAY_{ebay['type']}_{ebay['region']}",
            str(ebay["strength"]),
        ))
    if refs:
        chosen_value = min(x[0] for x in refs)
        chosen = next(x for x in refs if x[0] == chosen_value)
        return round(chosen[0], 2), chosen[1], chosen[2]
    if ebay:
        return round(float(ebay["eur"]), 2), f"EBAY_{ebay['type']}_{ebay['region']}", str(ebay["strength"])
    return None, "NONE", "NONE"


def evaluate_gumtree_listing(conn, listing: dict, cfg: dict, fx: dict, snapshot_date: str) -> dict:
    acfg = cfg.get("arbitrage", {})
    source_price = _float(listing.get("price_gbp"))
    fx_rate = _float((fx.get("rates") or {}).get("GBP"))
    acquisition = _to_eur(source_price, "GBP", fx) if source_price is not None else None
    region = str(listing.get("region") or "GREAT_BRITAIN")
    friction = _region_friction(acquisition, region, cfg) if acquisition is not None else None
    landed = round(acquisition + friction, 2) if acquisition is not None and friction is not None else None

    try:
        pid = int(listing.get("id_product") or 0)
    except (TypeError, ValueError):
        pid = 0
    exact = str(listing.get("exact_match") or "").strip().lower() in {"1", "true", "yes"}
    language = str(listing.get("language_status") or "UNKNOWN")
    condition = str(listing.get("condition_status") or "UNKNOWN")

    cm_floor = cm_trend = None
    cm_checked = ""
    ebay = None
    if pid > 0:
        cm_floor, cm_trend, cm_checked = _latest_cm(conn, pid)
        ebay = _best_ebay_reference_eur(conn, pid, fx)

    ebay_eur = None if not ebay else round(float(ebay["eur"]), 2)
    exit_ref, ref_type, ref_strength = _choose_exit_reference(cm_floor, ebay)
    exit_cost_pct = float(acfg.get("exit_cost_pct", 8.0))
    exit_after = None if exit_ref is None else round(exit_ref * (1.0 - exit_cost_pct / 100.0), 2)
    spread = None if landed is None or exit_after is None else round(exit_after - landed, 2)
    roi = None if spread is None or landed in (None, 0) else round(spread / landed * 100.0, 1)

    min_spread = float(acfg.get("minimum_net_spread_eur", 8.0))
    min_roi = float(acfg.get("minimum_net_roi_pct", 25.0))
    if not exact:
        signal = "VERIFY_VARIANT"
    elif bool(acfg.get("require_english", True)) and language != "EN_CONFIRMED":
        signal = "VERIFY_CONDITION_LANGUAGE"
    elif bool(acfg.get("require_nm", True)) and condition != "NM_CLAIMED":
        signal = "VERIFY_CONDITION_LANGUAGE"
    elif landed is None:
        signal = "INSUFFICIENT_FX"
    elif exit_ref is None:
        signal = "INSUFFICIENT_REFERENCE"
    elif spread is not None and roi is not None and spread >= min_spread and roi >= min_roi:
        if fx.get("live") and ref_strength in {"STRONG", "MEDIUM"}:
            signal = "STRONG_ARBITRAGE"
        else:
            signal = "POSSIBLE_ARBITRAGE"
    else:
        signal = "NO_EDGE"

    if signal == "STRONG_ARBITRAGE":
        confidence = "HIGH" if ref_strength == "STRONG" else "MEDIUM"
    elif signal == "POSSIBLE_ARBITRAGE":
        confidence = "MEDIUM" if ref_strength in {"STRONG", "MEDIUM"} else "LOW"
    elif signal in {"VERIFY_VARIANT", "VERIFY_CONDITION_LANGUAGE"}:
        confidence = "LOW"
    else:
        confidence = "MEDIUM" if exit_ref is not None and landed is not None else "LOW"

    notes = []
    if cm_checked:
        notes.append(f"Cardmarket EN/NM checked {cm_checked}")
    if ebay:
        notes.append(f"eBay {ebay['type']} {ebay['strength']} {ebay['region']}")
    if not fx.get("live"):
        notes.append("FX fallback used; strong arbitrage disabled")
    if signal == "VERIFY_VARIANT":
        notes.append("Exact set/collector-number/variant gate not satisfied")
    if signal == "VERIFY_CONDITION_LANGUAGE":
        notes.append("Require explicit English + NM evidence before actionable signal")

    return {
        "snapshot_date": snapshot_date,
        "id_product": pid or "",
        "name": _product_name(conn, pid) if pid else listing.get("product_name") or "",
        "source_platform": "GUMTREE",
        "source_region": region,
        "source_url": listing.get("url") or "",
        "source_price": source_price,
        "source_currency": "GBP",
        "fx_to_eur": fx_rate,
        "fx_source": fx.get("source") or "",
        "acquisition_eur": acquisition,
        "friction_reserve_eur": friction,
        "landed_eur": landed,
        "cardmarket_en_nm_eur": cm_floor,
        "cardmarket_trend_eur": cm_trend,
        "ebay_reference_eur": ebay_eur,
        "chosen_exit_reference_eur": exit_ref,
        "reference_type": ref_type,
        "reference_strength": ref_strength,
        "estimated_exit_after_costs_eur": exit_after,
        "net_spread_eur": spread,
        "net_roi_pct": roi,
        "exact_printing_verified": int(exact),
        "language_status": language,
        "condition_status": condition,
        "arbitrage_signal": signal,
        "confidence": confidence,
        "notes": "; ".join(notes),
    }


def _cardmarket_to_ebay_rows(resale_path: Path, snapshot_date: str) -> list[dict]:
    rows = []
    for src in _read_csv(resale_path):
        landed = _float(src.get("risk_adjusted_landed_eur"))
        exit_ref = _float(src.get("expected_resale_eur"))
        spread = _float(src.get("gross_spread_eur"))
        roi = _float(src.get("gross_roi_pct"))
        if landed is None or exit_ref is None:
            continue
        decision = str(src.get("resale_decision") or "")
        rows.append({
            "snapshot_date": snapshot_date,
            "id_product": src.get("id_product") or "",
            "name": src.get("name") or "",
            "source_platform": "CARDMARKET",
            "source_region": "EU_TO_IRELAND",
            "source_url": "",
            "source_price": landed,
            "source_currency": "EUR",
            "fx_to_eur": 1.0,
            "fx_source": "EUR",
            "acquisition_eur": landed,
            "friction_reserve_eur": 0.0,
            "landed_eur": landed,
            "cardmarket_en_nm_eur": "",
            "cardmarket_trend_eur": "",
            "ebay_reference_eur": exit_ref,
            "chosen_exit_reference_eur": exit_ref,
            "reference_type": src.get("reference_type") or "",
            "reference_strength": src.get("reference_strength") or "",
            "estimated_exit_after_costs_eur": exit_ref,
            "net_spread_eur": spread,
            "net_roi_pct": roi,
            "exact_printing_verified": 1,
            "language_status": "EN_CONFIRMED",
            "condition_status": "NM_CLAIMED",
            "arbitrage_signal": "POSSIBLE_ARBITRAGE" if decision == "BUY" else "NO_EDGE",
            "confidence": "MEDIUM" if src.get("reference_strength") in {"STRONG", "MEDIUM"} else "LOW",
            "notes": "Existing Cardmarket-to-eBay resale layer; landed sourcing and reference rules unchanged.",
        })
    return rows


def build_arbitrage_report(
    conn,
    cfg: dict,
    gumtree_path: Path,
    resale_path: Path,
    output_path: Path,
    *,
    fx: dict | None = None,
    today: date | None = None,
) -> tuple[list[dict], dict]:
    today = today or date.today()
    snapshot_date = today.isoformat()
    fx = fx or fetch_fx_rates(cfg)
    rows = [
        evaluate_gumtree_listing(conn, listing, cfg, fx, snapshot_date)
        for listing in _read_csv(gumtree_path)
    ]
    rows.extend(_cardmarket_to_ebay_rows(resale_path, snapshot_date))
    order = {
        "STRONG_ARBITRAGE": 0,
        "POSSIBLE_ARBITRAGE": 1,
        "VERIFY_VARIANT": 2,
        "VERIFY_CONDITION_LANGUAGE": 3,
        "INSUFFICIENT_REFERENCE": 4,
        "INSUFFICIENT_FX": 5,
        "NO_EDGE": 6,
    }
    rows.sort(key=lambda r: (
        order.get(str(r.get("arbitrage_signal")), 99),
        -(float(r.get("net_spread_eur")) if r.get("net_spread_eur") not in (None, "") else -999999),
    ))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ARBITRAGE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "rows": len(rows),
        "strong_arbitrage": sum(1 for r in rows if r["arbitrage_signal"] == "STRONG_ARBITRAGE"),
        "possible_arbitrage": sum(1 for r in rows if r["arbitrage_signal"] == "POSSIBLE_ARBITRAGE"),
        "verify_variant": sum(1 for r in rows if r["arbitrage_signal"] == "VERIFY_VARIANT"),
        "verify_condition_language": sum(1 for r in rows if r["arbitrage_signal"] == "VERIFY_CONDITION_LANGUAGE"),
        "fx_source": fx.get("source"),
        "fx_live": bool(fx.get("live")),
        "fx_error": fx.get("error") or "",
        "note": (
            "Arbitrage uses conservative landed-cost friction reserves and validated "
            "Cardmarket EN/NM/eBay evidence. Configured reserves are planning assumptions, "
            "not tax, customs, postage or legal advice."
        ),
    }
    return rows, summary


def write_status(path: Path, gumtree_status: dict, arbitrage_status: dict) -> None:
    payload = {"gumtree": gumtree_status, "arbitrage": arbitrage_status}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
