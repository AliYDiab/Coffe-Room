import sqlite3
import unittest
from datetime import datetime

import adb


class DailyWorkerLogTests(unittest.TestCase):
    def setUp(self):
        self.original_conn = adb.conn
        self.original_cur = adb.cur
        adb.conn = sqlite3.connect(":memory:")
        adb.cur = adb.conn.cursor()
        adb.cur.executescript("""
            CREATE TABLE workers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                rating REAL DEFAULT 0,
                total_ratings INTEGER DEFAULT 0
            );
            CREATE TABLE worker_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER NOT NULL,
                work_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                last_login_at TEXT NOT NULL,
                end_time TEXT,
                status TEXT DEFAULT 'active',
                total_receipts INTEGER DEFAULT 0,
                total_items REAL DEFAULT 0,
                total_revenue REAL DEFAULT 0,
                held_revenue REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(worker_id, work_date)
            );
            CREATE TABLE receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total REAL,
                date TEXT,
                status TEXT DEFAULT 'paid',
                worker_id INTEGER,
                worker_session_id INTEGER,
                income_date TEXT
            );
            CREATE TABLE receipt_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id INTEGER,
                qty REAL,
                price REAL
            );
            CREATE TABLE debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer TEXT,
                amount REAL,
                paid REAL DEFAULT 0,
                note TEXT,
                created_at TEXT,
                receipt_id INTEGER
            );
            CREATE TABLE debt_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                debt_id INTEGER,
                amount REAL,
                paid_at TEXT,
                note TEXT
            );
            INSERT INTO workers (id, name) VALUES (1, 'Worker A');
            INSERT INTO workers (id, name) VALUES (2, 'Worker B');
        """)

    def tearDown(self):
        adb.conn.close()
        adb.conn = self.original_conn
        adb.cur = self.original_cur

    def add_receipt(self, session_id, worker_id, total, status="paid"):
        sold_at = "2026-08-19T10:00:00"
        income_date = sold_at if status == "paid" else None
        adb.cur.execute("""
            INSERT INTO receipts (total, date, status, worker_id, worker_session_id, income_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (total, sold_at, status, worker_id, session_id, income_date))
        receipt_id = adb.cur.lastrowid
        adb.cur.execute(
            "INSERT INTO receipt_items (receipt_id, qty, price) VALUES (?, 1, ?)",
            (receipt_id, total),
        )
        adb.conn.commit()
        return receipt_id

    def test_each_worker_has_one_resumable_log_per_day(self):
        day = datetime(2026, 8, 19, 8, 0)
        first_id, first_start, _ = adb.start_worker_session(1, day)
        resumed_id, resumed_start, _ = adb.start_worker_session(1, datetime(2026, 8, 19, 12, 0))
        second_worker_id, _, _ = adb.start_worker_session(2, day)

        self.assertEqual(first_id, resumed_id)
        self.assertEqual(first_start, resumed_start)
        self.assertNotEqual(first_id, second_worker_id)
        self.assertEqual(adb.cur.execute("SELECT COUNT(*) FROM worker_sessions").fetchone()[0], 2)

        next_day_id, _, next_day = adb.start_worker_session(1, datetime(2026, 8, 20, 7, 0))
        self.assertNotEqual(first_id, next_day_id)
        self.assertEqual(next_day, "2026-08-20")
        old_status = adb.cur.execute("SELECT status FROM worker_sessions WHERE id = ?", (first_id,)).fetchone()[0]
        self.assertEqual(old_status, "completed")

    def test_debt_is_held_until_full_payment(self):
        session_id, _, _ = adb.start_worker_session(1, datetime(2026, 8, 19, 8, 0))
        receipt_id = self.add_receipt(session_id, 1, 100, status="debt")
        adb.cur.execute("""
            INSERT INTO debts (customer, amount, paid, created_at, receipt_id)
            VALUES ('Customer', 100, 0, '2026-08-19T10:00:00', ?)
        """, (receipt_id,))
        debt_id = adb.cur.lastrowid
        adb.conn.commit()

        totals = adb.get_worker_session_totals(session_id)
        self.assertEqual(totals["revenue"], 0)
        self.assertEqual(totals["held_revenue"], 100)

        self.assertFalse(adb.record_debt_payment(debt_id, 40, paid_at="2026-08-20T09:00:00"))
        status, income_date = adb.cur.execute(
            "SELECT status, income_date FROM receipts WHERE id = ?", (receipt_id,)
        ).fetchone()
        self.assertEqual(status, "partial")
        self.assertIsNone(income_date)

        self.assertTrue(adb.record_debt_payment(debt_id, 60, paid_at="2026-08-21T11:30:00"))
        status, income_date = adb.cur.execute(
            "SELECT status, income_date FROM receipts WHERE id = ?", (receipt_id,)
        ).fetchone()
        self.assertEqual(status, "paid")
        self.assertEqual(income_date, "2026-08-21T11:30:00")
        totals = adb.get_worker_session_totals(session_id)
        self.assertEqual(totals["revenue"], 100)
        self.assertEqual(totals["held_revenue"], 0)


if __name__ == "__main__":
    unittest.main()
