from deal_scanner.arbitrage import evaluate_gumtree_listing
from deal_scanner.db import connect
from deal_scanner.market_observatory import ensure_ebay_schema


def _cfg():
    return {
        "arbitrage": {
            "minimum_net_spread_eur": 8.0,
            "minimum_net_roi_pct": 25.0,
            "exit_cost_pct": 8.0,
            "require_english": True,
            "require_nm": True,
            "regions": {
                "NORTHERN_IRELAND": {"fixed_friction_eur": 2.0, "friction_pct": 2.0},
                "GREAT_BRITAIN": {"fixed_friction_eur": 7.0, "friction_pct": 10.0},
            },
        }
    }


def _db(tmp_path):
    conn = connect(tmp_path / "arb.sqlite")
    ensure_ebay_schema(conn)
    conn.execute(
        """INSERT INTO products(id_product,name,category_name,expansion_name,number,rarity,date_added,last_seen_catalog)
           VALUES(691947,'Origin Forme Palkia VSTAR','Pokemon','Crown Zenith','GG67','Ultra Rare','2023-01-20','2026-09-11')"""
    )
    conn.execute(
        """INSERT INTO cardmarket_en_nm_overrides(id_product,en_nm_floor_eur,checked_at,source,notes)
           VALUES(691947,100.0,'2026-09-11','test','validated')"""
    )
    conn.commit()
    return conn


def _listing(region="NORTHERN_IRELAND", price=60.0, exact=1, language="EN_CONFIRMED", condition="NM_CLAIMED"):
    return {
        "listing_id": "1491234567",
        "url": "https://www.gumtree.com/p/hobbies-collectibles/palkia/1491234567",
        "title": "Origin Forme Palkia VSTAR GG67 Crown Zenith English NM",
        "description": "Pack fresh",
        "price_gbp": price,
        "location": "Belfast" if region == "NORTHERN_IRELAND" else "Manchester",
        "region": region,
        "id_product": 691947 if exact else "",
        "product_name": "Origin Forme Palkia VSTAR",
        "exact_match": exact,
        "language_status": language,
        "condition_status": condition,
    }


def test_ni_friction_can_make_arbitrage_actionable(tmp_path):
    conn = _db(tmp_path)
    fx = {"rates": {"GBP": 1.15, "EUR": 1.0}, "source": "LIVE:test", "live": True, "error": ""}
    row = evaluate_gumtree_listing(conn, _listing(), _cfg(), fx, "2026-09-11")
    assert row["arbitrage_signal"] == "STRONG_ARBITRAGE"
    assert row["landed_eur"] == 72.38
    assert row["net_roi_pct"] >= 25.0


def test_mainland_friction_can_remove_same_price_edge(tmp_path):
    conn = _db(tmp_path)
    fx = {"rates": {"GBP": 1.15, "EUR": 1.0}, "source": "LIVE:test", "live": True, "error": ""}
    row = evaluate_gumtree_listing(
        conn, _listing(region="GREAT_BRITAIN"), _cfg(), fx, "2026-09-11"
    )
    assert row["landed_eur"] == 82.9
    assert row["arbitrage_signal"] == "NO_EDGE"


def test_exact_print_and_language_condition_gates_precede_price(tmp_path):
    conn = _db(tmp_path)
    fx = {"rates": {"GBP": 1.15, "EUR": 1.0}, "source": "LIVE:test", "live": True, "error": ""}

    uncertain = evaluate_gumtree_listing(conn, _listing(price=20, exact=0), _cfg(), fx, "2026-09-11")
    assert uncertain["arbitrage_signal"] == "VERIFY_VARIANT"

    unknown_condition = evaluate_gumtree_listing(
        conn, _listing(price=20, condition="UNKNOWN"), _cfg(), fx, "2026-09-11"
    )
    assert unknown_condition["arbitrage_signal"] == "VERIFY_CONDITION_LANGUAGE"

    unknown_language = evaluate_gumtree_listing(
        conn, _listing(price=20, language="UNKNOWN"), _cfg(), fx, "2026-09-11"
    )
    assert unknown_language["arbitrage_signal"] == "VERIFY_CONDITION_LANGUAGE"


def test_fallback_fx_cannot_produce_strong_arbitrage(tmp_path):
    conn = _db(tmp_path)
    fx = {"rates": {"GBP": 1.15, "EUR": 1.0}, "source": "CONFIG_FALLBACK", "live": False, "error": "offline"}
    row = evaluate_gumtree_listing(conn, _listing(price=20), _cfg(), fx, "2026-09-11")
    assert row["arbitrage_signal"] == "POSSIBLE_ARBITRAGE"
