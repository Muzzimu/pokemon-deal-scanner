from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CherryPickResult:
    ask_eur: float
    reference_en_nm_eur: float
    ask_discount_eur: float
    ask_discount_pct: float
    single_landed_eur: float
    single_discount_pct: float
    basket_landed_eur: float
    basket_discount_pct: float
    decision: str
    condition_check_required: bool


def _discount_pct(reference: float, cost: float) -> float:
    if reference <= 0:
        return 0.0
    return ((reference - cost) / reference) * 100.0


def evaluate_local_cherry_pick(
    *,
    ask_eur: float,
    reference_en_nm_eur: float,
    postage_eur: float = 2.0,
    postage_up_to_cards: int = 10,
    minimum_discount_pct: float = 20.0,
    minimum_absolute_discount_eur: float = 1.50,
    watch_discount_pct: float = 10.0,
    listing_language: str | None = None,
    listing_condition: str | None = None,
) -> CherryPickResult:
    """Evaluate a local listing against a *verified* English/NM reference.

    The local ask is evaluated three ways:
    - article-only discount, useful for candidate discovery;
    - single-card landed discount, using all postage on one card;
    - basket-landed discount, allocating postage evenly across the seller's
      stated combined-postage capacity.

    Unknown condition does not silently become NM: a qualifying result is marked
    as requiring a condition check before purchase.
    """
    if ask_eur < 0 or reference_en_nm_eur <= 0:
        raise ValueError("ask_eur must be >= 0 and reference_en_nm_eur must be > 0")
    if postage_eur < 0 or postage_up_to_cards < 1:
        raise ValueError("postage_eur must be >= 0 and postage_up_to_cards must be >= 1")

    language = (listing_language or "").strip().lower()
    if language and language not in {"en", "eng", "english"}:
        decision = "REJECT_LANGUAGE"
    else:
        decision = "PASS"

    condition = (listing_condition or "").strip().upper()
    condition_check_required = not condition
    if condition and condition not in {"NM", "MT", "MINT"}:
        decision = "REJECT_CONDITION"

    ask_discount_eur = reference_en_nm_eur - ask_eur
    ask_discount_pct = _discount_pct(reference_en_nm_eur, ask_eur)
    single_landed = ask_eur + postage_eur
    basket_landed = ask_eur + (postage_eur / postage_up_to_cards)
    single_discount_pct = _discount_pct(reference_en_nm_eur, single_landed)
    basket_discount_pct = _discount_pct(reference_en_nm_eur, basket_landed)

    if decision == "PASS":
        qualifies_article = (
            ask_discount_pct >= minimum_discount_pct
            and ask_discount_eur >= minimum_absolute_discount_eur
        )
        qualifies_single = (
            single_discount_pct >= minimum_discount_pct
            and (reference_en_nm_eur - single_landed) >= minimum_absolute_discount_eur
        )
        qualifies_basket = (
            basket_discount_pct >= minimum_discount_pct
            and (reference_en_nm_eur - basket_landed) >= minimum_absolute_discount_eur
        )

        if qualifies_single:
            decision = "SINGLE_CHERRY_PICK"
        elif qualifies_basket:
            decision = "BASKET_CHERRY_PICK"
        elif qualifies_article:
            decision = "CHERRY_PICK_CANDIDATE"
        elif ask_discount_pct >= watch_discount_pct:
            decision = "WATCH"

        if condition_check_required and decision in {
            "SINGLE_CHERRY_PICK",
            "BASKET_CHERRY_PICK",
            "CHERRY_PICK_CANDIDATE",
        }:
            decision = "VERIFY_CONDITION"

    return CherryPickResult(
        ask_eur=round(ask_eur, 2),
        reference_en_nm_eur=round(reference_en_nm_eur, 2),
        ask_discount_eur=round(ask_discount_eur, 2),
        ask_discount_pct=round(ask_discount_pct, 1),
        single_landed_eur=round(single_landed, 2),
        single_discount_pct=round(single_discount_pct, 1),
        basket_landed_eur=round(basket_landed, 2),
        basket_discount_pct=round(basket_discount_pct, 1),
        decision=decision,
        condition_check_required=condition_check_required,
    )
