from pathlib import Path


def test_fundamentals_script_uses_exact_tcgdex_ids():
    text = Path("scripts/refresh_card_fundamentals.py").read_text(encoding="utf-8")
    assert 'cards/{tcgdex_id}' in text
    assert 'str(card.get("id") or "") != tcgdex_id' in text
    assert "fuzzy" not in text.lower()


def test_fundamentals_cache_has_identity_columns():
    header = Path("data/reference/card_fundamentals.csv").read_text(encoding="utf-8").splitlines()[0]
    for field in ("id_product", "tcgdex_id", "release_date", "rarity", "illustrator", "status"):
        assert field in header.split(",")
