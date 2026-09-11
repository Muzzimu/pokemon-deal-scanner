from deal_scanner.gumtree import (
    classify_region,
    infer_condition_status,
    infer_language_status,
    parse_search_html,
)


def test_gumtree_parser_extracts_listing_without_css_classes():
    html = """
    <html><body>
      <a href="/p/hobbies-collectibles/origin-forme-palkia-vstar/1491234567">
        <div>3</div>
        <h2>Origin Forme Palkia VSTAR GG67 Crown Zenith English NM</h2>
        <p>Pack fresh, sleeved immediately.</p>
        <span>Belfast, County Antrim</span>
        <strong>£60</strong>
      </a>
    </body></html>
    """
    rows = parse_search_html(html)
    assert len(rows) == 1
    row = rows[0]
    assert row["listing_id"] == "1491234567"
    assert row["title"] == "Origin Forme Palkia VSTAR GG67 Crown Zenith English NM"
    assert row["location"] == "Belfast, County Antrim"
    assert row["price_gbp"] == 60.0
    assert "Pack fresh" in row["description"]


def test_gumtree_classification_and_claims_are_conservative():
    assert classify_region("Belfast, County Antrim") == "NORTHERN_IRELAND"
    assert classify_region("Manchester, Greater Manchester") == "GREAT_BRITAIN"
    assert infer_language_status("English Near Mint") == "EN_CONFIRMED"
    assert infer_language_status("Japanese Pokemon card") == "NON_ENGLISH"
    assert infer_language_status("Pokemon card, great condition") == "UNKNOWN"
    assert infer_condition_status("English NM, pack fresh") == "NM_CLAIMED"
    assert infer_condition_status("lightly played") == "NOT_NM"
    assert infer_condition_status("great condition") == "UNKNOWN"
