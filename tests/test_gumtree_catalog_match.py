from deal_scanner.db import connect
from deal_scanner.gumtree_catalog_match import match_catalog_exact


def test_catalog_match_requires_number_name_and_set(tmp_path):
    conn = connect(tmp_path / "catalog.sqlite")
    conn.execute(
        """INSERT INTO products(id_product,name,category_name,expansion_name,number,rarity,date_added,last_seen_catalog)
           VALUES(691947,'Origin Forme Palkia VSTAR','Pokemon','Crown Zenith','GG67','Ultra Rare','2023-01-20','2026-09-11')"""
    )
    conn.commit()

    assert match_catalog_exact(
        conn,
        "Origin Forme Palkia VSTAR GG67/GG70 Crown Zenith English NM",
    ) == 691947
    assert match_catalog_exact(conn, "Origin Forme Palkia VSTAR Crown Zenith") is None
    assert match_catalog_exact(conn, "Palkia GG67/GG70") is None
