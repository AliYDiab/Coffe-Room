import sqlite3
import unittest

from firebase_sync import (
    build_change_notification,
    ensure_processed_mobile_requests,
    increment_item_stock_from_mobile,
    processed_mobile_result,
    record_processed_mobile_request,
    suppress_notifications_since,
    sync_queue_watermark,
)


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE items (
                id INTEGER PRIMARY KEY,
                stock INTEGER,
                available INTEGER,
                type TEXT
            )
        """)
        self.conn.execute("INSERT INTO items VALUES (1, 7, 0, 'fixed')")
        self.conn.execute("INSERT INTO items VALUES (2, 4, 1, 'recipe')")
        ensure_processed_mobile_requests(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_stock_increment_is_atomic_and_validated(self):
        result = increment_item_stock_from_mobile(
            self.conn, {"item_id": 1, "quantity_delta": 5}
        )
        self.assertEqual(result, 1)
        self.assertEqual(
            self.conn.execute(
                "SELECT stock, available FROM items WHERE id=1"
            ).fetchone(),
            (12, 1),
        )
        self.assertIsNone(increment_item_stock_from_mobile(
            self.conn, {"item_id": 1, "quantity_delta": -1}
        ))
        self.assertIsNone(increment_item_stock_from_mobile(
            self.conn, {"item_id": 2, "quantity_delta": 5}
        ))

    def test_processed_operation_is_detected_before_retry(self):
        record_processed_mobile_request(
            self.conn, "operation-1", "mobile_inventory_requests", 1
        )
        self.conn.commit()
        self.assertEqual(processed_mobile_result(self.conn, "operation-1"), 1)
        self.assertIsNone(processed_mobile_result(self.conn, "operation-2"))

    def test_new_receipt_changes_can_sync_without_push(self):
        self.conn.execute("""
            CREATE TABLE sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT,
                record_id INTEGER,
                action TEXT
            )
        """)
        watermark = sync_queue_watermark(self.conn)
        self.conn.executemany(
            "INSERT INTO sync_queue (table_name, record_id, action) VALUES (?, ?, ?)",
            [
                ("receipts", 10, "insert"),
                ("receipt_items", 20, "insert"),
                ("items", 1, "update"),
            ],
        )

        suppress_notifications_since(self.conn, watermark)

        rows = self.conn.execute("""
            SELECT id, table_name, record_id, action, notify_mobile
            FROM sync_queue ORDER BY id
        """).fetchall()
        self.assertTrue(rows)
        self.assertTrue(all(row[4] == 0 for row in rows))
        self.assertIsNone(build_change_notification(self.conn.cursor(), rows))

    def test_debt_remains_notifyable_when_its_receipt_is_suppressed(self):
        self.conn.execute("""
            CREATE TABLE sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT,
                record_id INTEGER,
                action TEXT,
                notify_mobile INTEGER NOT NULL DEFAULT 1
            )
        """)
        watermark = sync_queue_watermark(self.conn)
        self.conn.executemany(
            "INSERT INTO sync_queue (table_name, record_id, action) VALUES (?, ?, ?)",
            [("receipts", 11, "insert"), ("debts", 4, "insert")],
        )

        suppress_notifications_since(
            self.conn, watermark, keep_tables={"debts"}
        )

        rows = self.conn.execute("""
            SELECT id, table_name, record_id, action, notify_mobile
            FROM sync_queue ORDER BY id
        """).fetchall()
        self.assertEqual([row[4] for row in rows], [0, 1])
        notification = build_change_notification(self.conn.cursor(), rows)
        self.assertIsNotNone(notification)
        self.assertIn("Added debts #4", notification[1])
        self.assertNotIn("receipts", notification[1])

    def test_receipt_rows_never_generate_generic_mobile_notifications(self):
        rows = [
            (1, "receipts", 51, "insert", 1),
            (2, "receipt_items", 52, "insert", 1),
        ]

        self.assertIsNone(build_change_notification(self.conn.cursor(), rows))

    def test_receipt_rows_are_ignored_when_an_important_change_is_present(self):
        rows = [
            (1, "receipts", 51, "insert", 1),
            (2, "receipt_items", 52, "insert", 1),
            (3, "debts", 7, "insert", 1),
        ]

        notification = build_change_notification(self.conn.cursor(), rows)

        self.assertIsNotNone(notification)
        self.assertIn("Added debts #7", notification[1])
        self.assertNotIn("receipt", notification[1])


if __name__ == "__main__":
    unittest.main()
