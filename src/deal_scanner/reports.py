from __future__ import annotations

import csv
import json
from pathlib import Path

from .scoring import matches_hit, score_row


COMMON_FIELDS = [
    "id_product", "name", "expansion_name", "number", "rarity", "snapshot_date",
    "low", "trend", "avg1", "avg7", "avg30",
    "cm_en_nm_floor", "cm_en_nm_checked_at",
    "ct_en_nm_floor", "ct_visible_units", "ct_visible_sellers", "ct_zero_units",
    "hist_low", "hist_days", "gap_pct", "volatility_30d",
    "popularity_score", "best_validated_sourcing_price", "deal_score", "status",
]


def _to_dict(row) -> dict:
    return dict(row)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def scored_rows(db_rows, cfg: dict) -> list[dict]:
    return [score_row(_to_dict(r), cfg) for r in db_rows]


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
    query = cfg["watchlists"]["dragonite"]["query"].lower()
    out = [r for r in rows if query in r["name"].lower()]
    target_hero = float(cfg["watchlists"]["dragonite"]["target_hero_cost_eur"])
    target_support = float(cfg["watchlists"]["dragonite"]["target_support_cost_eur"])
    for r in out:
        validated = r.get("best_validated_sourcing_price")
        if validated is None:
            r["dragonite_target"] = "VALIDATE_EN_NM"
        elif validated <= target_support:
            r["dragonite_target"] = "SUPPORT_BUY"
        elif validated <= target_hero:
            r["dragonite_target"] = "HERO_BUY"
        else:
            r["dragonite_target"] = "WAIT"
    return sorted(out, key=lambda x: (x.get("best_validated_sourcing_price") or 999, -x["deal_score"]))


def build_top_flips(rows: list[dict], cfg: dict) -> list[dict]:
    min_avg = cfg["rules"]["minimum_avg30_for_gap_score_eur"]
    min_gap = cfg["rules"]["minimum_gap_pct"]
    out = []
    for r in rows:
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
        "cardmarket_snapshot_date": latest_snapshot_date(conn),
        "cardtrader_snapshot_date": latest_cardtrader_snapshot_date(conn),
        "cards_scored": len(scored),
        "cheap_hit_rows": len(cheap),
        "dragonite_rows": len(dragons),
        "top_flip_rows": len(flips),
        "bundle_rows": len(bundles),
        "validated_cardmarket_en_nm": sum(1 for r in scored if r.get("cm_en_nm_floor") is not None),
        "visible_cardtrader_en_nm": sum(1 for r in scored if r.get("ct_en_nm_floor") is not None),
        "pricing_guardrail": "Generic Cardmarket low is discovery only. BUY requires Cardmarket EN/NM validation or is explicitly labelled CardTrader EN/NM.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "scanner_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status
