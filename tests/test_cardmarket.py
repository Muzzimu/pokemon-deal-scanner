from deal_scanner.cardmarket import filter_price_rows_to_catalog


def test_filter_price_rows_to_current_catalog():
    rows = [
        {"idProduct": 100, "low": 1.0},
        {"idProduct": 200, "low": 2.0},
        {"idProduct": 999, "low": 9.0},
        {"idProduct": None, "low": 5.0},
    ]
    kept, skipped = filter_price_rows_to_catalog(rows, {100, 200})
    assert [r["idProduct"] for r in kept] == [100, 200]
    assert skipped == 2
