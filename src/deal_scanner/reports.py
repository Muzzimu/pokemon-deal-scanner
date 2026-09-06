from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from .scoring import matches_hit, score_row


COMMON_FIELDS = [
    "id_product", "name", "expansion_name", "number", "rarity", "date_added", "snapshot_date",
    "product_age_days", "low", "trend", "avg1", "avg7", "avg30",
    "cm_en_nm_floor", "cm_en_nm_checked_at",
    "ct_en_nm_floor", "ct_visible_units", "ct_visible_sellers", "ct_zero_units",
    "hist_low", "hist_days", "generic_gap_pct", "gap_pct", "volatility_30d",
    "popularity_score", "best_validated_sourcing_price", "deal_score", "status",
]


def _to_dict(row) -> dict:
    return dict(row)


def _age_days(date_added, snapshot_date) -> int | None:
    if not date_added or not snapshot_date:
        return None
    try:
        added = date.fromisoformat(str(date_added)[:10])
        snap = date.fromisoformat(str(snapshot_date)[:10])
        return max(0, (snap - added).days)
    except (TypeError, ValueError):
        return None


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def scored_rows(db_rows, cfg: dict) -> list[dict]:
    out = []
    for row in db_rows:
        scored = score_row(_to_dict(row), cfg)
        scored["product_age_days"] = _age_days(scored.get("date_added"), scored.get("snapshot_date"))
        out.append(scored)
    return out


def build_cheap_hits(rows: list[dict], cfg: dict) -> list[dict]:
    patterns = cfg["rules"]["hit_patterns"]
    max_generic = cfg["rules"]["cheap_hit_discovery_low_max_eur"]
    max_cm = cfg["rules"]["cheap_hit_actionable_en_nm_max_eur"]
    max_ct = cfg["cardtrader"]["actionable_en_nm_max_eur"]
    out = []
    for r in rows:
        if not matches_hit(r["name"], patterns):
            continue
        generic = r.get("low") is not None and r["low"] <= max_generic
        cm_ok = r.get("cm_en_nm_floor") is not None and r["cm_en_nm_floor"] <= max_cm
        ct_ok = r.get("ct_en_nm_floor") is not None and r["ct_en_nm_floor"] <= max_ct
        if generic or cm_ok or ct_ok:
            out.append(r)
    return sorted(out, key=lambda x: (-x["deal_score"], x.get("best_validated_sourcing_price") or 999, x.get("low") or 999))


def build_dragonite(rows: list[dict], cfg: dict) -> list[dict]:
    rules = cfg["watchlists"]["dragonite"]
    query = rules["query"].lower()
    out = [r for r in rows if query in r["name"].lower()]
    target_support = float(rules["target_support_cost_eur"])
    target_standalone = float(rules["standalone_buy_max_landed_eur"])
    target_bundle = float(rules["bundle_buy_max_landed_eur"])
    for r in out:
        validated = r.get("best_validated_sourcing_price")
        if validated is None:
            r["dragonite_target"] = "VALIDATE_EN_NM"
        elif validated <= target_support:
            r["dragonite_target"] = "SUPPORT_PRICE_CANDIDATE"
        elif validated <= target_standalone:
            r["dragonite_target"] = "HERO_PRICE_CANDIDATE"
        elif validated <= target_bundle:
            r["dragonite_target"] = "BUNDLE_PRICE_CANDIDATE"
        else:
            r["dragonite_target"] = "WAIT"
    return sorted(out, key=lambda x: (x.get("best_validated_sourcing_price") or 999, -x["deal_score"]))


def build_top_flips(rows: list[dict], cfg: dict) -> list[dict]:
    min_avg = cfg["rules"]["minimum_avg30_for_gap_score_eur"]
    min_gap = cfg["rules"]["minimum_gap_pct"]
    min_age = int(cfg["rules"].get("min_product_age_days_for_flip_signal", 0))
    out = []
    for r in rows:
        # New releases often have unstable day-1 lows/averages. Do not call the
        # launch volatility a flip signal until the product has aged enough.
        age = r.get("product_age_days")
        if age is not None and age < min_age:
            continue

        # v0.5 guardrail: a top-flip candidate must have validated EN/NM
        # acquisition evidence. Generic Cardmarket low (which may be Italian or
        # another language/condition) is discovery-only and cannot qualify a flip.
        if r.get("best_validated_sourcing_price") is None:
            continue
        if (r.get("avg30") or 0) < min_avg:
            continue
        if (r.get("gap_pct") or -999) < min_gap:
            continue
        out.append(r)
    return sorted(out, key=lambda x: (-x["deal_score"], -(x.get("gap_pct") or 0)))


def build_bundle_candidates(rows: list[dict], cfg: dict) -> list[dict]:
    chars = cfg["bundles"]["characters"]
    max_generic = cfg["bundles"]["max_generic_discovery_cost_eur"]
    max_valid = cfg["bundles"]["max_validated_en_nm_cost_eur"]
    out = []
    for char in chars:
        pool = [r for r in rows if char.lower() in r["name"].lower()]
        if not pool:
            continue
        pool = sorted(pool, key=lambda x: (
            x.get("best_validated_sourcing_price") if x.get("best_validated_sourcing_price") is not None else 999,
            x.get("low") if x.get("low") is not None else 999,
            -x["deal_score"],
        ))
        chosen = pool[: int(cfg["bundles"]["cards_per_bundle"])]
        generic_total = sum((r.get("low") or 0) for r in chosen)
        validated = [r.get("best_validated_sourcing_price") for r in chosen]
        valid_complete = bool(chosen) and all(v is not None for v in validated)
        valid_total = sum(validated) if valid_complete else None
        out.append({
            "character": char,
            "cards_found": len(chosen),
            "cards": " | ".join(f"{r['name']} [{r.get('expansion_name') or ''}]" for r in chosen),
            "generic_low_total": round(generic_total, 2),
            "validated_en_nm_total": None if valid_total is None else round(valid_total, 2),
            "generic_discovery_ok": generic_total <= max_generic,
            "validated_buy_ok": valid_total is not None and valid_total <= max_valid,
        })
    return out


def generate_reports(conn, cfg: dict, output_dir: Path) -> dict:
    from .db import latest_rows_with_history, latest_snapshot_date, latest_cardtrader_snapshot_date
    scored = scored_rows(latest_rows_with_history(conn), cfg)
    cheap = build_cheap_hits(scored, cfg)[: cfg["rules"]["max_report_rows"]]
    dragons = build_dragonite(scored, cfg)
    flips = build_top_flips(scored, cfg)[: cfg["rules"]["max_report_rows"]]
    bundles = build_bundle_candidates(scored, cfg)

    write_csv(output_dir / "cheap_ex.csv", cheap, COMMON_FIELDS)
    write_csv(output_dir / "dragonite.csv", dragons, COMMON_FIELDS + ["dragonite_target"])
    write_csv(output_dir / "top_flips.csv", flips, COMMON_FIELDS)
    write_csv(output_dir / "bundle_candidates.csv", bundles, [
        "character", "cards_found", "cards", "generic_low_total", "validated_en_nm_total",
        "generic_discovery_ok", "validated_buy_ok",
    ])
    status = {
        "version": str(cfg.get("version", "unknown")),
        "cardmarket_snapshot_date": latest_snapshot_date(conn),
        "cardtrader_snapshot_date": latest_cardtrader_snapshot_date(conn),
        "cards_scored": len(scored),
        "cheap_hit_rows": len(cheap),
        "dragonite_rows": len(dragons),
        "top_flip_rows": len(flips),
        "bundle_rows": len(bundles),
        "new_product_signal_guard_days": int(cfg["rules"].get("min_product_age_days_for_flip_signal", 0)),
        "validated_cardmarket_en_nm": sum(1 for r in scored if r.get("cm_en_nm_floor") is not None),
        "visible_cardtrader_en_nm": sum(1 for r in scored if r.get("ct_en_nm_floor") is not None),
        "pricing_guardrail": "Cardmarket generic low is discovery only and cannot drive gap_pct, deal-score gap, or top-flip qualification. Top flips require validated EN/NM acquisition evidence. A Cardmarket BUY additionally requires EN/NM + ships to Ireland + confirmed landed/basket-adjusted cost in the sourcing layer. CardTrader EN/NM remains separately labelled. eBay active asks are never labelled as sold prices.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "scanner_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status
