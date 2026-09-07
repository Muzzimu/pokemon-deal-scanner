import pytest

from deal_scanner.local_cherry_pick import evaluate_local_cherry_pick


def test_single_cherry_pick_when_landed_still_beats_reference():
    result = evaluate_local_cherry_pick(
        ask_eur=5.0,
        reference_en_nm_eur=10.0,
        postage_eur=1.0,
        postage_up_to_cards=10,
        listing_language="English",
        listing_condition="NM",
    )
    assert result.decision == "SINGLE_CHERRY_PICK"
    assert result.single_landed_eur == 6.0
    assert result.single_discount_pct == 40.0


def test_basket_cherry_pick_when_combined_postage_is_required():
    result = evaluate_local_cherry_pick(
        ask_eur=2.0,
        reference_en_nm_eur=4.95,
        postage_eur=2.0,
        postage_up_to_cards=10,
        listing_language="English",
        listing_condition="NM",
    )
    assert result.decision == "BASKET_CHERRY_PICK"
    assert result.single_discount_pct < 20.0
    assert result.basket_discount_pct > 20.0


def test_unknown_condition_requires_verification_before_buy():
    result = evaluate_local_cherry_pick(
        ask_eur=6.0,
        reference_en_nm_eur=8.0,
        postage_eur=2.0,
        postage_up_to_cards=10,
        listing_language="English",
    )
    assert result.decision == "VERIFY_CONDITION"
    assert result.condition_check_required is True


def test_non_english_listing_is_rejected():
    result = evaluate_local_cherry_pick(
        ask_eur=1.0,
        reference_en_nm_eur=10.0,
        listing_language="Italian",
        listing_condition="NM",
    )
    assert result.decision == "REJECT_LANGUAGE"


def test_bad_inputs_raise():
    with pytest.raises(ValueError):
        evaluate_local_cherry_pick(ask_eur=-1.0, reference_en_nm_eur=5.0)
