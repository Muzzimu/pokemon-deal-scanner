from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from deal_scanner.cardmarket_live import (
    ParseBotCardmarketClient, _extract_listing_rows, _listing_price, _summary, _seller_key, _quantity
)
from deal_scanner.cardtrader import CardTraderClient, normalize_marketplace
from deal_scanner.config import load_config, resolve_path
from deal_scanner.db import blueprint_product_map_for_expansion, expansion_ids_for_products
from deal_scanner.provider_usage import append_provider_usage

OWNED_PATH = ROOT / "data" / "reference" / "owned_resale_cards.csv"
OUTPUT_PATH = ROOT / "dashboard" / "data" / "owned_market.json"
USAGE_PATH = ROOT / "dashboard" / "data" / "provider_usage.csv"
DEPTH_HISTORY_PATH = ROOT / "dashboard" / "data" / "owned_depth_history.csv"


def read_owned() -> list[dict]:
    with OWNED_PATH.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def as_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "reverse", "reverse holo", "reverse_holo"}:
        return True
    if text in {"0", "false", "no", "n", "normal", "non-reverse", "non_reverse", "standard"}:
        return False
    return None


def nested_reverse_value(value):
    if isinstance(value, dict):
        for key, child in value.items():
            key_norm = str(key).lower().replace(" ", "_")
            if key_norm in {"pokemon_reverse", "reverse", "reverse_holo", "is_reverse", "is_reverse_holo"}:
                parsed = as_bool(child.get("value") if isinstance(child, dict) else child)
                if parsed is not None:
                    return parsed
        for child in value.values():
            parsed = nested_reverse_value(child)
            if parsed is not None:
                return parsed
    elif isinstance(value, list):
        for child in value:
            parsed = nested_reverse_value(child)
            if parsed is not None:
                return parsed
    return None


def ct_reverse_by_offer(payload) -> dict[int, bool | None]:
    result: dict[int, bool | None] = {}
    groups = []
    if isinstance(payload, dict):
        groups = [v for v in payload.values() if isinstance(v, list)]
    elif isinstance(payload, list):
        groups = [payload]
    for group in groups:
        for row in group:
            if not isinstance(row, dict):
                continue
            raw_id = row.get("id") or row.get("product_id") or row.get("productId")
            try:
                offer_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            result[offer_id] = nested_reverse_value(row.get("properties_hash") or row.get("properties") or row)
    return result


def matches_finish(requirement: str, reverse_value: bool | None) -> tuple[bool, bool]:
    """Return (comparable, finish_verified). UNIQUE_PRODUCT is exact by product identity."""
    req = (requirement or "").strip().upper()
    if req == "UNIQUE_PRODUCT":
        return True, True
    if req == "NON_REVERSE":
        return reverse_value is False, reverse_value is not None
    if req == "REVERSE":
        return reverse_value is True, reverse_value is not None
    return False, False


def ask_diagnostics(rows: list[dict], sample_size: int) -> dict:
    """Return floor, robust floor and ask-side structure from already-fetched rows.

    These are diagnostic-only market-structure measures. They do not create a BUY,
    fair-value override or executable exit.
    """
    summary = _summary(rows, sample_size)
    offers = []
    for index, row in enumerate(rows):
        price = _listing_price(row)
        if price is None or float(price) <= 0:
            continue
        offers.append({
            "price": float(price),
            "seller": _seller_key(row, index),
            "quantity": _quantity(row),
        })
    offers.sort(key=lambda r: r["price"])
    prices = [r["price"] for r in offers]
    n = min(max(1, sample_size), len(prices)) if prices else 0
    sample = [round(value, 2) for value in prices[:n]]
    floor = summary.get("floor")
    robust = summary.get("robust")
    spread_pct = None
    if floor not in (None, 0) and robust is not None:
        spread_pct = round((float(robust) / float(floor) - 1.0) * 100.0, 1)

    def band_stats(multiplier: float) -> tuple[int, int]:
        if not offers:
            return 0, 0
        ceiling = offers[0]["price"] * multiplier
        selected = [r for r in offers if r["price"] <= ceiling + 1e-9]
        return sum(int(r["quantity"]) for r in selected), len({r["seller"] for r in selected})

    floor3_units, floor3_sellers = band_stats(1.03)
    near10_units, near10_sellers = band_stats(1.10)
    next_distinct_gap_pct = None
    if offers:
        base = offers[0]["price"]
        for row in offers[1:]:
            if row["price"] > base + 1e-9:
                next_distinct_gap_pct = round((row["price"] / base - 1.0) * 100.0, 1)
                break

    seller_units: dict[str, int] = {}
    for row in offers:
        seller_units[row["seller"]] = seller_units.get(row["seller"], 0) + int(row["quantity"])
    total_units = sum(seller_units.values())
    shares = sorted((units / total_units for units in seller_units.values()), reverse=True) if total_units else []
    top1 = round(shares[0] * 100.0, 1) if shares else None
    top3 = round(sum(shares[:3]) * 100.0, 1) if shares else None
    hhi = round(sum(share * share for share in shares) * 10000.0, 0) if shares else None

    return {
        **summary,
        "robust_sample_size": n,
        "ask_sample_eur": sample,
        "floor_to_robust_spread_pct": spread_pct,
        "floor_depth_3pct_units": floor3_units,
        "floor_depth_3pct_sellers": floor3_sellers,
        "near_floor_10pct_units": near10_units,
        "near_floor_10pct_sellers": near10_sellers,
        "next_distinct_ask_gap_pct": next_distinct_gap_pct,
        "top1_seller_unit_share_pct": top1,
        "top3_seller_unit_share_pct": top3,
        "seller_hhi": hhi,
    }


def append_depth_history(cards: list[dict], observed_at: str) -> None:
    fields = [
        "observed_at_utc", "id_product", "name", "provider", "status",
        "floor_eur", "robust_floor_eur", "visible_sellers", "visible_units",
        "floor_depth_3pct_units", "floor_depth_3pct_sellers",
        "near_floor_10pct_units", "near_floor_10pct_sellers",
        "next_distinct_ask_gap_pct", "top1_seller_unit_share_pct",
        "top3_seller_unit_share_pct", "seller_hhi",
    ]
    existing = []
    if DEPTH_HISTORY_PATH.exists():
        with DEPTH_HISTORY_PATH.open(newline="", encoding="utf-8") as fh:
            existing = [dict(row) for row in csv.DictReader(fh)]
    keys = {(observed_at, str(card.get("id_product")), provider) for card in cards for provider in ("cardmarket", "cardtrader")}
    existing = [
        row for row in existing
        if (row.get("observed_at_utc"), str(row.get("id_product")), row.get("provider")) not in keys
    ]
    for card in cards:
        for provider in ("cardmarket", "cardtrader"):
            source = card.get(provider) or {}
            row = {
                "observed_at_utc": observed_at,
                "id_product": card.get("id_product"),
                "name": card.get("name"),
                "provider": provider.upper(),
                "status": source.get("status"),
            }
            for field in fields[5:]:
                row[field] = source.get(field)
            existing.append(row)
    existing.sort(key=lambda r: (r.get("observed_at_utc", ""), str(r.get("id_product", "")), r.get("provider", "")))
    DEPTH_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DEPTH_HISTORY_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(existing)


def ct_market(conn: sqlite3.Connection, cfg: dict, owned: list[dict]) -> dict[str, dict]:
    token = os.environ.get(str(cfg.get("cardtrader", {}).get("token_env") or "CARDTRADER_API_TOKEN"))
    if not token:
        return {str(r["id_product"]): {"status": "MISSING_CARDTRADER_TOKEN"} for r in owned}
    owned_ids = [int(r["id_product"]) for r in owned]
    owned_by_pid = {int(r["id_product"]): r for r in owned}
    sample_size = max(1, int(cfg.get("cardmarket_live", {}).get("robust_floor_sample_size", 3)))
    client = CardTraderClient(
        cfg["sources"]["cardtrader_base_url"],
        token,
        other_delay=float(cfg["cardtrader"].get("other_delay_seconds", 0.08)),
        marketplace_delay=float(cfg["cardtrader"].get("marketplace_delay_seconds", 1.05)),
        timeout=int(cfg["cardtrader"].get("timeout_seconds", 60)),
    )
    offers_by_pid: dict[int, list[dict]] = {pid: [] for pid in owned_ids}
    finish_unknown_by_pid: dict[int, int] = {pid: 0 for pid in owned_ids}
    errors: dict[int, str] = {}
    for expansion_id in expansion_ids_for_products(conn, owned_ids):
        try:
            bpmap = blueprint_product_map_for_expansion(conn, expansion_id)
            payload = client.marketplace(expansion_id, language="en")
            reverse_map = ct_reverse_by_offer(payload)
            for offer in normalize_marketplace(payload, bpmap):
                pid = offer.get("id_product")
                if pid not in owned_by_pid:
                    continue
                cond = str(offer.get("condition") or "").strip().lower().replace("_", " ")
                lang = str(offer.get("language") or "").strip().lower()
                if lang not in {"en", "english"} or cond not in {"nm", "near mint"}:
                    continue
                if offer.get("graded") or offer.get("on_vacation") or offer.get("price_eur") in (None, 0):
                    continue
                reverse_value = reverse_map.get(int(offer["offer_id"]))
                comparable, finish_verified = matches_finish(owned_by_pid[pid].get("finish_requirement", ""), reverse_value)
                if not finish_verified and owned_by_pid[pid].get("finish_requirement") != "UNIQUE_PRODUCT":
                    finish_unknown_by_pid[pid] += 1
                if comparable:
                    offers_by_pid[pid].append(offer)
        except Exception as exc:
            for pid in owned_ids:
                errors.setdefault(pid, str(exc))

    result: dict[str, dict] = {}
    for pid in owned_ids:
        offers = sorted(offers_by_pid[pid], key=lambda x: float(x["price_eur"]))
        if offers:
            diag = ask_diagnostics(offers, sample_size)
            result[str(pid)] = {
                "status": "OK",
                "floor_eur": diag["floor"],
                "robust_floor_eur": diag["robust"],
                "robust_sample_size": diag["robust_sample_size"],
                "ask_sample_eur": diag["ask_sample_eur"],
                "floor_to_robust_spread_pct": diag["floor_to_robust_spread_pct"],
                "visible_sellers": diag["sellers"],
                "visible_units": diag["units"],
                "visible_offer_rows": diag["rows"],
                "floor_depth_3pct_units": diag["floor_depth_3pct_units"],
                "floor_depth_3pct_sellers": diag["floor_depth_3pct_sellers"],
                "near_floor_10pct_units": diag["near_floor_10pct_units"],
                "near_floor_10pct_sellers": diag["near_floor_10pct_sellers"],
                "next_distinct_ask_gap_pct": diag["next_distinct_ask_gap_pct"],
                "top1_seller_unit_share_pct": diag["top1_seller_unit_share_pct"],
                "top3_seller_unit_share_pct": diag["top3_seller_unit_share_pct"],
                "seller_hhi": diag["seller_hhi"],
                "finish_verified": True,
            }
        elif finish_unknown_by_pid[pid]:
            result[str(pid)] = {
                "status": "VERIFY_FINISH",
                "floor_eur": None,
                "robust_floor_eur": None,
                "visible_sellers": 0,
                "visible_units": 0,
                "finish_verified": False,
            }
        else:
            result[str(pid)] = {
                "status": "NO_COMPARABLE_EN_NM_ASK" if pid not in errors else "DEGRADED",
                "floor_eur": None,
                "robust_floor_eur": None,
                "visible_sellers": 0,
                "visible_units": 0,
                "finish_verified": owned_by_pid[pid].get("finish_requirement") == "UNIQUE_PRODUCT",
                "error": errors.get(pid),
            }
    return result


def cm_market(cfg: dict, owned: list[dict]) -> dict[str, dict]:
    live_cfg = cfg.get("cardmarket_live", {})
    api_key = os.environ.get(str(live_cfg.get("api_key_env") or "PARSE_API_KEY"))
    if not api_key:
        return {str(r["id_product"]): {"status": "MISSING_CARDMARKET_LIVE_KEY"} for r in owned}

    sample_size = max(1, int(live_cfg.get("robust_floor_sample_size", 3)))
    # Preserve provider pacing but avoid an unnecessary sleep after the final request.
    local_cfg = deepcopy(cfg)
    delay = float(local_cfg.get("cardmarket_live", {}).get("request_delay_seconds", 12.5))
    local_cfg.setdefault("cardmarket_live", {})["request_delay_seconds"] = 0
    client = ParseBotCardmarketClient(local_cfg, api_key)
    result: dict[str, dict] = {}

    for index, card in enumerate(owned):
        pid = int(card["id_product"])
        try:
            payload = client.listings(pid)
            rows = _extract_listing_rows(payload)
            comparable_rows: list[dict] = []
            finish_unknown = 0
            for row in rows:
                price = _listing_price(row)
                if price is None or price <= 0:
                    continue
                reverse_value = nested_reverse_value(row)
                comparable, finish_verified = matches_finish(card.get("finish_requirement", ""), reverse_value)
                if not finish_verified and card.get("finish_requirement") != "UNIQUE_PRODUCT":
                    finish_unknown += 1
                if comparable:
                    comparable_rows.append(row)
            if comparable_rows:
                diag = ask_diagnostics(comparable_rows, sample_size)
                result[str(pid)] = {
                    "status": "OK",
                    "floor_eur": diag["floor"],
                    "robust_floor_eur": diag["robust"],
                    "robust_sample_size": diag["robust_sample_size"],
                    "ask_sample_eur": diag["ask_sample_eur"],
                    "floor_to_robust_spread_pct": diag["floor_to_robust_spread_pct"],
                    "visible_offer_rows": diag["rows"],
                    "visible_sellers": diag["sellers"],
                    "visible_units": diag["units"],
                    "floor_depth_3pct_units": diag["floor_depth_3pct_units"],
                "floor_depth_3pct_sellers": diag["floor_depth_3pct_sellers"],
                "near_floor_10pct_units": diag["near_floor_10pct_units"],
                "near_floor_10pct_sellers": diag["near_floor_10pct_sellers"],
                "next_distinct_ask_gap_pct": diag["next_distinct_ask_gap_pct"],
                "top1_seller_unit_share_pct": diag["top1_seller_unit_share_pct"],
                "top3_seller_unit_share_pct": diag["top3_seller_unit_share_pct"],
                "seller_hhi": diag["seller_hhi"],
                "finish_verified": True,
                }
            elif finish_unknown:
                result[str(pid)] = {
                    "status": "VERIFY_FINISH",
                    "floor_eur": None,
                    "robust_floor_eur": None,
                    "visible_offer_rows": 0,
                    "finish_verified": False,
                }
            else:
                result[str(pid)] = {
                    "status": "NO_COMPARABLE_EN_NM_ASK",
                    "floor_eur": None,
                    "robust_floor_eur": None,
                    "visible_offer_rows": 0,
                    "finish_verified": card.get("finish_requirement") == "UNIQUE_PRODUCT",
                }
        except Exception as exc:
            result[str(pid)] = {
                "status": "DEGRADED",
                "floor_eur": None,
                "robust_floor_eur": None,
                "visible_offer_rows": 0,
                "finish_verified": False,
                "error": str(exc),
            }
        if delay > 0 and index < len(owned) - 1:
            time.sleep(delay)
    return result


def main() -> int:
    cfg = load_config(ROOT / "config.yaml")
    db_path = resolve_path(cfg, cfg["paths"]["database"])
    if not db_path.exists():
        raise FileNotFoundError(f"Scanner DB not found: {db_path}")
    owned = read_owned()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ct = ct_market(conn, cfg, owned)
    conn.close()
    cm = cm_market(cfg, owned)
    live_cfg = cfg.get("cardmarket_live", {})
    parse_key = os.environ.get(str(live_cfg.get("api_key_env") or "PARSE_API_KEY"))
    parse_requests = len(owned) if parse_key else 0

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    cards = []
    for card in owned:
        pid = str(card["id_product"])
        cards.append({
            **card,
            "item_paid_eur": float(card["item_paid_eur"]),
            "allocated_shipping_eur": float(card["allocated_shipping_eur"]),
            "landed_cost_eur": float(card["landed_cost_eur"]),
            "cardmarket": cm.get(pid, {"status": "NOT_QUERIED"}),
            "cardtrader": ct.get(pid, {"status": "NOT_QUERIED"}),
        })
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    append_depth_history(cards, now)
    OUTPUT_PATH.write_text(
        json.dumps({
            "schema_version": 3,
            "generated_at_utc": now,
            "purpose": "owned-card decision support; asks are competition references, not realised exits",
            "robust_ask_note": "robust_floor_eur is the median of the cheapest comparable asks already fetched; diagnostic only",
            "depth_note": "ask-side depth/concentration fields are prospective diagnostics only and do not alter BUY/FV logic",
            "cards": cards,
        }, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    append_provider_usage(
        USAGE_PATH,
        provider="PARSE_CARDMARKET",
        operation="owned_card_live_asks",
        requests=parse_requests,
        documented_credits=parse_requests if parse_key else 0,
        status="OK" if parse_key else "UNAVAILABLE",
        rows=sum(1 for value in cm.values() if str(value.get("status") or "").upper() == "OK"),
        notes="Account UI indicates approximately one credit per simple live call; one exact-product request per owned card.",
        observed_at_utc=now,
    )
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} with {len(cards)} owned cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
