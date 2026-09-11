from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FIELDS = [
    "id_product", "name", "tcgplayer_product_id",
    "market_price_usd", "most_recent_sale_usd",
    "lowest_listing_price_usd", "lowest_listing_shipping_usd", "executable_floor_usd",
    "market_price_eur", "most_recent_sale_eur",
    "lowest_listing_price_eur", "lowest_listing_shipping_eur", "executable_floor_eur",
    "fx_usd_to_eur",
    "sales_30d", "sales_90d", "avg_daily_sold", "current_quantity", "current_sellers",
    # Legacy/provider-ambiguous fields are retained for backwards compatibility only.
    # They are not used as live order-book depth in the market-quality model.
    "low_price_usd", "low_price_eur", "listing_count",
    "reference_strength", "checked_at", "source", "notes",
]

CM_ID_RE = re.compile(r"(?:idProduct=|/Products/[^?#]*[?&]idProduct=)(\d+)", re.I)


def _pick(row: dict, *keys):
    for key in keys:
        if row.get(key) not in (None, ""):
            return row.get(key)
    return ""


def _num(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _sum_if_known(a, b):
    left = _num(a)
    right = _num(b)
    if left is None or right is None:
        return ""
    return round(left + right, 4)


def _cm_id(row: dict) -> str:
    explicit = _pick(row, "id_product", "cardmarket_product_id", "cardmarketProductId", "cm_product_id")
    if explicit:
        try:
            return str(int(explicit))
        except (TypeError, ValueError):
            pass
    for key in ("cardmarket_url", "cardmarketUrl", "cardmarket", "cm_url", "euUrl"):
        value = str(row.get(key) or "")
        match = CM_ID_RE.search(value)
        if match:
            return match.group(1)
    return ""


def _read_input(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            for key in ("items", "data", "results"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break
        if not isinstance(payload, list):
            raise ValueError("JSON input must be a list or contain items/data/results list")
        return [dict(x) for x in payload if isinstance(x, dict)]
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _normalize(row: dict, source: str, strength: str) -> dict | None:
    pid = _cm_id(row)
    if not pid:
        # Do not guess a Cardmarket mapping from collector number or name alone.
        return None

    item_usd = _pick(
        row,
        "lowest_listing_price_usd", "lowestListingPriceUsd", "currentLowestPriceUsd",
        "lowest_listing_price", "lowestListingPrice",
    )
    shipping_usd = _pick(
        row,
        "lowest_listing_shipping_usd", "lowestListingShippingUsd", "currentLowestShippingUsd",
        "lowest_listing_shipping", "lowestListingShipping",
    )
    executable_usd = _pick(
        row,
        "executable_floor_usd", "executableFloorUsd", "landedLowestUsd", "lowestDeliveredPriceUsd",
    )
    if executable_usd == "":
        executable_usd = _sum_if_known(item_usd, shipping_usd)

    item_eur = _pick(
        row,
        "lowest_listing_price_eur", "lowestListingPriceEur", "currentLowestPriceEur",
    )
    shipping_eur = _pick(
        row,
        "lowest_listing_shipping_eur", "lowestListingShippingEur", "currentLowestShippingEur",
    )
    executable_eur = _pick(
        row,
        "executable_floor_eur", "executableFloorEur", "landedLowestEur", "lowestDeliveredPriceEur",
    )
    if executable_eur == "":
        executable_eur = _sum_if_known(item_eur, shipping_eur)

    return {
        "id_product": pid,
        "name": _pick(row, "name", "card", "title"),
        "tcgplayer_product_id": _pick(row, "tcgplayer_product_id", "tcgplayerProductId", "productId", "product_id"),
        # Transaction-derived reference. This belongs in fair-value / PCS calculations,
        # not in the executable acquisition floor.
        "market_price_usd": _pick(row, "market_price_usd", "marketPrice", "usMarketUsd", "tcgplayerMarketUsd", "us_market_usd"),
        "most_recent_sale_usd": _pick(row, "most_recent_sale_usd", "mostRecentSaleUsd", "mostRecentSale", "recentSaleUsd"),
        # Current live order book. Item price and shipping are kept separate so a
        # domestic-US listing is never silently treated as an Ireland-landed buy.
        "lowest_listing_price_usd": item_usd,
        "lowest_listing_shipping_usd": shipping_usd,
        "executable_floor_usd": executable_usd,
        "market_price_eur": _pick(row, "market_price_eur", "usMarketEur", "tcgplayerMarketEur", "us_market_eur"),
        "most_recent_sale_eur": _pick(row, "most_recent_sale_eur", "mostRecentSaleEur", "recentSaleEur"),
        "lowest_listing_price_eur": item_eur,
        "lowest_listing_shipping_eur": shipping_eur,
        "executable_floor_eur": executable_eur,
        "fx_usd_to_eur": _pick(row, "fx_usd_to_eur", "usdToEur", "usd_to_eur"),
        # Velocity and depth are deliberately separate. A card can be highly liquid
        # even when only a few copies are currently offered.
        "sales_30d": _pick(row, "sales_30d", "sales30d", "sales_30_days", "monthlySales"),
        "sales_90d": _pick(row, "sales_90d", "sales90d", "sales_90_days", "total_sold_3m", "totalSold3Months", "totalSold90d"),
        "avg_daily_sold": _pick(row, "avg_daily_sold", "avgDailySold", "averageDailySold"),
        "current_quantity": _pick(row, "current_quantity", "currentQuantity", "current_qty", "quantityAvailable"),
        "current_sellers": _pick(row, "current_sellers", "currentSellers", "sellerCount", "currentSellerCount"),
        # Legacy values remain available for old provider exports but have ambiguous
        # semantics and are no longer interpreted as exact live listing depth.
        "low_price_usd": _pick(row, "low_price_usd", "lowestPrice", "lowPrice", "tcgplayerLowUsd", "us_low_usd"),
        "low_price_eur": _pick(row, "low_price_eur", "tcgplayerLowEur", "us_low_eur"),
        "listing_count": _pick(row, "listing_count", "totalListings", "listings", "offerCount"),
        "reference_strength": str(_pick(row, "reference_strength", "strength") or strength).upper(),
        "checked_at": _pick(row, "checked_at", "scrapedAt", "snapshot_date", "priceGuideDate", "date"),
        "source": _pick(row, "source") or source,
        "notes": _pick(row, "notes") or "imported exact Cardmarket-id-linked TCGplayer evidence; transaction price and live order book kept separate",
    }


def _read_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {str(r.get("id_product") or ""): dict(r) for r in csv.DictReader(f) if r.get("id_product")}


def main() -> int:
    ap = argparse.ArgumentParser(description="Normalize TCGplayer/provider output into the scanner reference CSV")
    ap.add_argument("input", type=Path, help="Provider JSON or CSV export")
    ap.add_argument("--output", type=Path, default=ROOT / "data" / "reference" / "tcgplayer_market_reference.csv")
    ap.add_argument("--source", default="external_provider")
    ap.add_argument("--strength", default="MEDIUM", choices=["STRONG", "MEDIUM", "WEAK", "VERY_WEAK"])
    ap.add_argument("--replace", action="store_true", help="Replace instead of merging with existing exact-id rows")
    args = ap.parse_args()

    input_rows = _read_input(args.input)
    normalized = []
    rejected = 0
    for row in input_rows:
        item = _normalize(row, args.source, args.strength)
        if item is None:
            rejected += 1
        else:
            normalized.append(item)

    merged = {} if args.replace else _read_existing(args.output)
    for row in normalized:
        pid = str(row["id_product"])
        old = merged.get(pid)
        if old is None or str(row.get("checked_at") or "") >= str(old.get("checked_at") or ""):
            merged[pid] = row

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(merged.values(), key=lambda r: int(r["id_product"])))

    print(json.dumps({
        "input_rows": len(input_rows),
        "accepted_exact_id_rows": len(normalized),
        "rejected_without_exact_cardmarket_id": rejected,
        "output_rows": len(merged),
        "output": str(args.output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
