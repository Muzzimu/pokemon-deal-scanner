from __future__ import annotations

import time
from typing import Iterable

import requests


POKEMON_GAME_ID = 5


class CardTraderError(RuntimeError):
    pass


class CardTraderClient:
    def __init__(self, base_url: str, token: str, *, other_delay: float = 0.08,
                 marketplace_delay: float = 1.05, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.other_delay = other_delay
        self.marketplace_delay = marketplace_delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": "pokemon-deal-scanner/0.3 (+personal research)",
            "Accept": "application/json",
        })

    def _get(self, path: str, params: dict | None = None, *, marketplace: bool = False):
        delay = self.marketplace_delay if marketplace else self.other_delay
        last_exc = None
        for attempt in range(3):
            try:
                r = self.session.get(self.base_url + path, params=params, timeout=self.timeout)
                if r.status_code == 429:
                    wait = float(r.headers.get("Retry-After", max(delay, 2.0)))
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                data = r.json()
                if delay:
                    time.sleep(delay)
                return data
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise CardTraderError(f"GET {path} failed: {last_exc}")

    def expansions(self):
        return self._get("/expansions")

    def blueprints(self, expansion_id: int):
        return self._get("/blueprints/export", params={"expansion_id": expansion_id})

    def marketplace(self, expansion_id: int, *, language: str = "en"):
        return self._get(
            "/marketplace/products",
            params={"expansion_id": expansion_id, "language": language},
            marketplace=True,
        )


def _rows(payload) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("array", "data", "results", "expansions", "blueprints"):
            if isinstance(payload.get(k), list):
                return [x for x in payload[k] if isinstance(x, dict)]
    return []


def pokemon_expansions(payload) -> list[dict]:
    """Return only Pokémon expansions.

    CardTrader's current Pokémon game_id is 5. Previous v0.2 code incorrectly
    treated game_id 6 as Pokémon, which populated Blueprints for the wrong game
    and therefore produced zero Cardmarket mappings.
    """
    exps = _rows(payload)
    out = []
    saw_game_signal = False
    for e in exps:
        game = e.get("game") or e.get("game_name") or e.get("gameName")
        if isinstance(game, dict):
            game = game.get("name")
        game_id = e.get("game_id") or e.get("gameId")
        if game is not None or game_id is not None:
            saw_game_signal = True
        if game and "pokemon" in str(game).lower():
            out.append(e)
        elif str(game_id) == str(POKEMON_GAME_ID):
            out.append(e)
    # Only fall back when the payload genuinely contains no game discriminator.
    return out if saw_game_signal else exps


def expansion_id(e: dict) -> int | None:
    for k in ("id", "expansion_id", "expansionId"):
        if e.get(k) is not None:
            try:
                return int(e[k])
            except (TypeError, ValueError):
                pass
    return None


def expansion_name(e: dict) -> str:
    return str(e.get("name") or e.get("expansion_name") or e.get("code") or "")


def blueprint_rows(payload) -> list[dict]:
    return _rows(payload)


def _prop_value(props, *names):
    if not isinstance(props, dict):
        return None
    normalized = {str(k).lower().replace(" ", "_"): v for k, v in props.items()}
    for n in names:
        key = n.lower().replace(" ", "_")
        if key in normalized:
            value = normalized[key]
            if isinstance(value, dict):
                return value.get("value") or value.get("name") or value.get("label")
            return value
    return None


def _seller(product: dict) -> dict:
    s = product.get("seller") or product.get("user") or {}
    return s if isinstance(s, dict) else {}


def _price_eur(product: dict) -> float | None:
    """Return EUR marketplace price while respecting CardTrader's Money shape."""
    price = product.get("price")
    if isinstance(price, dict):
        cents = price.get("cents")
        currency = str(price.get("currency") or "EUR").upper()
        if currency != "EUR":
            return None
        try:
            return None if cents is None else float(cents) / 100.0
        except (TypeError, ValueError):
            return None

    # Export-style payloads can expose price_cents + price_currency.
    for key in ("price_cents", "priceCents"):
        if product.get(key) is not None:
            currency = str(product.get("price_currency") or product.get("priceCurrency") or "EUR").upper()
            if currency != "EUR":
                return None
            try:
                return float(product[key]) / 100.0
            except (TypeError, ValueError):
                pass

    # Older/simple wrappers may expose numeric price in cents.
    if price is not None:
        try:
            return float(price) / 100.0
        except (TypeError, ValueError):
            pass

    for key in ("price_eur", "priceEuro", "price_euro"):
        if product.get(key) is not None:
            try:
                return float(product[key])
            except (TypeError, ValueError):
                pass
    return None


def _blueprint_id(product: dict, fallback_blueprint_id: int | None = None) -> int | None:
    value = product.get("blueprint_id") or product.get("blueprintId")
    if value is None and isinstance(product.get("blueprint"), dict):
        value = product["blueprint"].get("id")
    if value is None:
        value = fallback_blueprint_id
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _offer_id(product: dict) -> int | None:
    value = product.get("id") or product.get("product_id") or product.get("productId")
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _bool(product: dict, *keys, default=False) -> bool:
    for k in keys:
        if k in product:
            return bool(product[k])
    return default


def normalize_marketplace(payload, blueprint_to_products: dict[int, list[int]]) -> list[dict]:
    """Flatten CardTrader's grouped marketplace response into comparable offers."""
    pairs: list[tuple[int | None, dict]] = []
    if isinstance(payload, dict):
        grouped = False
        for k, v in payload.items():
            if isinstance(v, list) and str(k).isdigit():
                grouped = True
                for p in v:
                    if isinstance(p, dict):
                        pairs.append((int(k), p))
        if not grouped:
            for p in _rows(payload):
                pairs.append((None, p))
    else:
        for p in _rows(payload):
            pairs.append((None, p))

    out = []
    for fallback_bid, p in pairs:
        bid = _blueprint_id(p, fallback_bid)
        oid = _offer_id(p)
        if bid is None or oid is None:
            continue
        mapped = blueprint_to_products.get(bid, [])
        if not mapped:
            mapped = [None]

        # Live marketplace uses properties_hash. Keep properties as a fallback.
        props = p.get("properties_hash") or p.get("properties") or {}
        language = _prop_value(props, "pokemon_language", "language", "mtg_language") or p.get("language")
        condition = _prop_value(props, "condition") or p.get("condition")
        graded = _prop_value(props, "graded")
        if graded is None:
            graded = p.get("graded", False)

        s = _seller(p)
        seller_id = s.get("id") or p.get("seller_id")
        seller_username = s.get("username") or s.get("name") or p.get("seller_username")
        seller_country = s.get("country_code") or s.get("country") or p.get("seller_country")
        quantity = p.get("quantity") or p.get("qty") or 1
        on_vacation = p.get("on_vacation", s.get("on_vacation", False))
        ct_zero = bool(s.get("can_sell_via_hub")) or _bool(p, "cardtrader_zero", "ct_zero", "zero", default=False)
        if isinstance(p.get("shipping_method"), dict):
            ct_zero = ct_zero or bool(p["shipping_method"].get("cardtrader_zero"))

        for pid in mapped:
            out.append({
                "offer_id": oid,
                "blueprint_id": bid,
                "id_product": pid,
                "seller_id": None if seller_id is None else int(seller_id),
                "seller_username": seller_username,
                "seller_country": seller_country,
                "quantity": int(quantity or 1),
                "price_eur": _price_eur(p),
                "language": str(language).lower() if language is not None else None,
                "condition": str(condition) if condition is not None else None,
                "graded": str(graded).lower() in ("true", "1", "yes", "graded"),
                "on_vacation": bool(on_vacation),
                "ct_zero": bool(ct_zero),
            })
    return out


def near_mint_english(offers: Iterable[dict]) -> list[dict]:
    out = []
    for o in offers:
        cond = (o.get("condition") or "").strip().lower().replace("_", " ")
        lang = (o.get("language") or "").strip().lower()
        if lang in ("en", "english") and cond in ("near mint", "nm") and not o.get("graded") and not o.get("on_vacation"):
            out.append(o)
    return out
