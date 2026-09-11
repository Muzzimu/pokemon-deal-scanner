from __future__ import annotations

import csv
import math
import statistics
import time
from datetime import date
from pathlib import Path

import requests


LIVE_FIELDS = [
    "snapshot_date", "id_product", "name", "expansion_name", "number", "watch_priority",
    "provider", "query_status", "live_article_floor_eur", "live_robust_floor_eur",
    "live_offer_rows", "live_sellers", "live_units", "validated_landed_eur",
    "delta_vs_validated_landed_pct", "validation_signal", "confidence", "notes",
]

ROUTE_LIVE_FIELDS = [
    "cm_live_provider", "cm_live_query_status", "cm_live_article_floor_eur",
    "cm_live_robust_floor_eur", "cm_live_sellers", "cm_live_units",
    "cm_live_delta_vs_validated_landed_pct", "cm_live_validation_signal",
]


def _float(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        if isinstance(value, dict):
            for key in ("eur", "value", "amount", "price"):
                if key in value:
                    return _float(value[key])
            return None
        if isinstance(value, str):
            text = value.strip().replace("€", "").replace("EUR", "").replace(" ", "")
            if "," in text and "." in text:
                # Cardmarket-style European thousands + decimal separators.
                if text.rfind(",") > text.rfind("."):
                    text = text.replace(".", "").replace(",", ".")
                else:
                    text = text.replace(",", "")
            elif "," in text:
                text = text.replace(",", ".")
            value = text
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> tuple[list[dict], list[str]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader], list(reader.fieldnames or [])


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _append_fields(existing: list[str], additions: list[str]) -> list[str]:
    out = list(existing)
    for field in additions:
        if field not in out:
            out.append(field)
    return out


def _nested_lists(payload) -> list[list[dict]]:
    found: list[list[dict]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in {"listings", "offers", "articles", "items", "results"} and isinstance(value, list):
                if not value or all(isinstance(x, dict) for x in value):
                    found.append(value)
            found.extend(_nested_lists(value))
    elif isinstance(payload, list):
        for value in payload:
            found.extend(_nested_lists(value))
    return found


def _extract_listing_rows(payload) -> list[dict]:
    """Best-effort parser for provider wrappers without coupling to one JSON nesting shape."""
    candidates = _nested_lists(payload)
    scored: list[tuple[int, list[dict]]] = []
    for rows in candidates:
        score = 0
        for row in rows[:10]:
            keys = {str(k).lower() for k in row.keys()}
            if keys & {"price", "price_eur", "price_value", "article_price"}:
                score += 2
            if keys & {"seller", "seller_name", "username", "vendor"}:
                score += 1
            if keys & {"condition", "language", "quantity"}:
                score += 1
        scored.append((score, rows))
    if not scored:
        return []
    scored.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
    return [dict(r) for r in scored[0][1]]


def _listing_price(row: dict) -> float | None:
    for key in ("price_eur", "price_value", "article_price", "price"):
        if key in row:
            value = _float(row.get(key))
            if value is not None:
                return value
    return None


def _seller_key(row: dict, index: int) -> str:
    seller = row.get("seller")
    if isinstance(seller, dict):
        for key in ("id", "username", "name"):
            if seller.get(key) not in (None, ""):
                return str(seller[key])
    for key in ("seller_id", "seller_name", "username", "vendor"):
        if row.get(key) not in (None, ""):
            return str(row[key])
    return f"row:{index}"


def _quantity(row: dict) -> int:
    return max(1, _int(row.get("quantity") or row.get("qty") or 1, 1))


def _summary(rows: list[dict], sample_size: int) -> dict:
    offers = []
    for i, row in enumerate(rows):
        price = _listing_price(row)
        if price is None or price <= 0:
            continue
        offers.append({"price": price, "seller": _seller_key(row, i), "quantity": _quantity(row)})
    if not offers:
        return {"floor": None, "robust": None, "rows": 0, "sellers": 0, "units": 0}
    offers.sort(key=lambda r: r["price"])
    cheapest = offers[: max(1, sample_size)]
    robust = statistics.median([r["price"] for r in cheapest])
    return {
        "floor": round(offers[0]["price"], 2),
        "robust": round(float(robust), 2),
        "rows": len(offers),
        "sellers": len({r["seller"] for r in offers}),
        "units": sum(r["quantity"] for r in offers),
    }


class ParseBotCardmarketClient:
    """Low-volume exact-product Cardmarket validator through Parse.bot.

    This client does not log into Cardmarket, manage cookies, rotate proxies or try to
    defeat anti-bot controls itself. It calls a configured external REST provider.
    """

    def __init__(self, cfg: dict, api_key: str):
        lcfg = cfg.get("cardmarket_live", {})
        self.base_url = str(lcfg.get("base_url") or "").rstrip("/")
        self.endpoint = str(lcfg.get("endpoint") or "get_card_listings")
        self.game = str(lcfg.get("game") or "Pokemon")
        self.language = str(lcfg.get("language") or "English")
        self.min_condition = str(lcfg.get("min_condition") or "NM")
        self.timeout = float(lcfg.get("timeout_seconds", 30))
        self.delay = float(lcfg.get("request_delay_seconds", 12.5))
        self.api_key = api_key
        self.session = requests.Session()

    def listings(self, product_id: int) -> dict:
        if not self.base_url:
            raise RuntimeError("cardmarket_live.base_url is not configured")
        url = f"{self.base_url}/{self.endpoint}"
        response = self.session.get(
            url,
            params={
                "game": self.game,
                "product_id": int(product_id),
                "language": self.language,
                "min_condition": self.min_condition,
                "page": 1,
            },
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if self.delay > 0:
            time.sleep(self.delay)
        return payload


def _select_candidates(core_rows: list[dict], cfg: dict) -> list[dict]:
    lcfg = cfg.get("cardmarket_live", {})
    priorities = {str(x).upper() for x in (lcfg.get("watch_priorities") or ["A", "B"])}
    min_lag = int(lcfg.get("minimum_ct_lag_score", 40))
    limit = max(0, int(lcfg.get("max_candidates_per_run", 20)))
    chosen = [
        r for r in core_rows
        if str(r.get("watch_priority") or "").upper() in priorities
        and _int(r.get("ct_lag_score")) >= min_lag
    ]
    priority_rank = {"A": 0, "B": 1, "C": 2}
    chosen.sort(key=lambda r: (
        priority_rank.get(str(r.get("watch_priority") or "").upper(), 9),
        -_int(r.get("ct_lag_score")),
        -(_float(r.get("net_spread_eur")) or -999999.0),
    ))
    return chosen[:limit]


def _validation_signal(live: dict, validated_landed: float | None, cfg: dict) -> tuple[str, float | None]:
    robust = _float(live.get("robust"))
    sellers = _int(live.get("sellers"))
    lcfg = cfg.get("cardmarket_live", {})
    min_sellers = int(lcfg.get("minimum_live_sellers", 2))
    stale_up = float(lcfg.get("stale_upward_pct", 10.0))
    cheaper_down = float(lcfg.get("cheaper_candidate_pct", 10.0))
    if robust is None:
        return "NO_LIVE_OFFERS", None
    if sellers < min_sellers:
        return "INSUFFICIENT_LIVE_DEPTH", None
    if validated_landed in (None, 0):
        return "LIVE_ARTICLE_PRICE_ONLY", None
    delta = round((robust / validated_landed - 1.0) * 100.0, 1)
    if delta >= stale_up:
        return "REVALIDATE_STALE_SOURCE", delta
    if delta <= -cheaper_down:
        return "LIVE_CHEAPER_VERIFY_SHIPPING", delta
    return "LIVE_ALIGNED", delta


def apply_live_validation_to_outputs(live_path: Path, route_path: Path, ct_path: Path) -> dict:
    live_rows, _ = _read_csv(live_path)
    live = {str(r.get("id_product") or ""): r for r in live_rows}
    changed_routes = changed_ct = 0

    route_rows, route_fields = _read_csv(route_path)
    for row in route_rows:
        evidence = live.get(str(row.get("id_product") or ""))
        if not evidence:
            continue
        row.update({
            "cm_live_provider": evidence.get("provider") or "",
            "cm_live_query_status": evidence.get("query_status") or "",
            "cm_live_article_floor_eur": evidence.get("live_article_floor_eur") or "",
            "cm_live_robust_floor_eur": evidence.get("live_robust_floor_eur") or "",
            "cm_live_sellers": evidence.get("live_sellers") or "",
            "cm_live_units": evidence.get("live_units") or "",
            "cm_live_delta_vs_validated_landed_pct": evidence.get("delta_vs_validated_landed_pct") or "",
            "cm_live_validation_signal": evidence.get("validation_signal") or "",
        })
        if evidence.get("validation_signal") == "REVALIDATE_STALE_SOURCE" and row.get("route_signal") in {"RESELL_TEST", "WATCH_ONLY"}:
            row["route_signal"] = "REVALIDATE_SOURCE"
            row["notes"] = (str(row.get("notes") or "") + "; live CM article floor moved above prior validated landed source").strip("; ")
            changed_routes += 1
    _write_csv(route_path, route_rows, _append_fields(route_fields, ROUTE_LIVE_FIELDS))

    ct_rows, ct_fields = _read_csv(ct_path)
    for row in ct_rows:
        evidence = live.get(str(row.get("id_product") or ""))
        if not evidence:
            continue
        row.update({
            "cm_live_provider": evidence.get("provider") or "",
            "cm_live_query_status": evidence.get("query_status") or "",
            "cm_live_article_floor_eur": evidence.get("live_article_floor_eur") or "",
            "cm_live_robust_floor_eur": evidence.get("live_robust_floor_eur") or "",
            "cm_live_sellers": evidence.get("live_sellers") or "",
            "cm_live_units": evidence.get("live_units") or "",
            "cm_live_delta_vs_validated_landed_pct": evidence.get("delta_vs_validated_landed_pct") or "",
            "cm_live_validation_signal": evidence.get("validation_signal") or "",
        })
        if evidence.get("validation_signal") == "REVALIDATE_STALE_SOURCE" and row.get("ct_signal") == "RESELL_TEST":
            row["ct_signal"] = "WATCH_ONLY"
            row["notes"] = (str(row.get("notes") or "") + "; live CM evidence requires source revalidation").strip("; ")
            changed_ct += 1
    _write_csv(ct_path, ct_rows, _append_fields(ct_fields, ROUTE_LIVE_FIELDS))
    return {"routes_downgraded": changed_routes, "ct_candidates_downgraded": changed_ct}


def validate_cardmarket_live(
    cfg: dict,
    core_watch_path: Path,
    output_path: Path,
    route_path: Path,
    ct_path: Path,
    *,
    api_key: str | None = None,
    client=None,
    today: date | None = None,
) -> dict:
    """Validate a small number of high-value CM/CT gap candidates against live CM offers.

    Live article prices remain verification evidence, not landed acquisition costs.
    Missing shipping-to-Ireland data can therefore never create a new BUY signal.
    """
    lcfg = cfg.get("cardmarket_live", {})
    today = today or date.today()
    enabled = bool(lcfg.get("enabled", True))
    if not enabled:
        _write_csv(output_path, [], LIVE_FIELDS)
        return {"enabled": False, "reason": "disabled", "queried": 0, "rows": 0}

    if client is None:
        if not api_key:
            _write_csv(output_path, [], LIVE_FIELDS)
            return {"enabled": False, "reason": "missing API key", "queried": 0, "rows": 0}
        provider = str(lcfg.get("provider") or "parsebot").lower()
        if provider != "parsebot":
            _write_csv(output_path, [], LIVE_FIELDS)
            return {"enabled": False, "reason": f"unsupported provider {provider}", "queried": 0, "rows": 0}
        client = ParseBotCardmarketClient(cfg, api_key)

    core_rows, _ = _read_csv(core_watch_path)
    candidates = _select_candidates(core_rows, cfg)
    sample_size = max(1, int(lcfg.get("robust_floor_sample_size", 3)))
    provider_name = str(lcfg.get("provider") or "parsebot")
    results: list[dict] = []
    failures = 0

    for card in candidates:
        pid = _int(card.get("id_product"))
        if pid <= 0:
            continue
        query_status = "OK"
        notes = []
        try:
            payload = client.listings(pid)
            listing_rows = _extract_listing_rows(payload)
            live = _summary(listing_rows, sample_size)
            if not listing_rows:
                query_status = "NO_LISTING_ROWS"
        except Exception as exc:
            failures += 1
            query_status = f"ERROR:{type(exc).__name__}"
            live = {"floor": None, "robust": None, "rows": 0, "sellers": 0, "units": 0}
            notes.append(str(exc)[:180])

        validated = _float(card.get("validated_buy_eur"))
        signal, delta = _validation_signal(live, validated, cfg)
        if signal == "LIVE_CHEAPER_VERIFY_SHIPPING":
            notes.append("live article price may be cheaper, but Ireland shipping/landed cost is not proven")
        elif signal == "REVALIDATE_STALE_SOURCE":
            notes.append("current live article floor is above prior validated landed source; do not auto-buy")

        confidence = "MEDIUM" if live["sellers"] >= int(lcfg.get("minimum_live_sellers", 2)) else "LOW"
        results.append({
            "snapshot_date": today.isoformat(),
            "id_product": pid,
            "name": card.get("name") or "",
            "expansion_name": card.get("expansion_name") or "",
            "number": card.get("number") or "",
            "watch_priority": card.get("watch_priority") or "",
            "provider": provider_name,
            "query_status": query_status,
            "live_article_floor_eur": live["floor"],
            "live_robust_floor_eur": live["robust"],
            "live_offer_rows": live["rows"],
            "live_sellers": live["sellers"],
            "live_units": live["units"],
            "validated_landed_eur": validated,
            "delta_vs_validated_landed_pct": delta,
            "validation_signal": signal,
            "confidence": confidence,
            "notes": "; ".join(notes),
        })

    _write_csv(output_path, results, LIVE_FIELDS)
    apply_status = apply_live_validation_to_outputs(output_path, route_path, ct_path) if results else {
        "routes_downgraded": 0, "ct_candidates_downgraded": 0
    }
    return {
        "enabled": True,
        "provider": provider_name,
        "selected_candidates": len(candidates),
        "queried": len(results),
        "failures": failures,
        "rows": len(results),
        "aligned": sum(1 for r in results if r["validation_signal"] == "LIVE_ALIGNED"),
        "cheaper_verify_shipping": sum(1 for r in results if r["validation_signal"] == "LIVE_CHEAPER_VERIFY_SHIPPING"),
        "revalidate_stale_source": sum(1 for r in results if r["validation_signal"] == "REVALIDATE_STALE_SOURCE"),
        **apply_status,
        "note": "Live Cardmarket offers are verification evidence only; article price without Ireland shipping cannot create a new BUY signal.",
    }
