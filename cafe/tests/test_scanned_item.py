import sqlite3

from modules.scanned_item import resolve_scanned_item


def test_generated_supplier_and_legacy_codes_resolve_consistently():
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, price REAL, stock REAL, type TEXT, cost REAL, barcode_value TEXT)")
        db.executemany("INSERT INTO items VALUES (?, ?, 10, 20, 'fixed', 2, ?)", [
            (1, "Generated", None), (2, "Supplier", "1"),
        ])
        cursor = db.cursor()
        for code, expected_id in [
            ("ITEM_ID:1", 1), ("ITEM_ID:2", 2), ("ITEM:Generated", 1),
            ("1", 2), ("2", 2), (" ITEM_ID:1\r\n", 1),
        ]:
            assert resolve_scanned_item(cursor, code)[0] == expected_id
        assert resolve_scanned_item(cursor, "ITEM_ID:invalid") is None
        assert resolve_scanned_item(cursor, "unknown") is None
    finally:
        db.close()
