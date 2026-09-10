import sqlite3
import unittest
from datetime import date

from firebase_sync import build_financial_periods


class FinancialPeriodTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE receipts (
                id INTEGER PRIMARY KEY,
                date TEXT,
                income_date TEXT,
                status TEXT
            );
            CREATE TABLE items (
                id INTEGER PRIMARY KEY,
                cost REAL
            );
            CREATE TABLE receipt_items (
                id INTEGER PRIMARY KEY,
                receipt_id INTEGER,
                item_id INTEGER,
                qty REAL,
                price REAL,
                cost REAL
            );
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY,
                date TEXT,
                category TEXT,
                amount REAL,
                vendor TEXT,
                note TEXT,
                source TEXT,
                created_at TEXT
            );
            INSERT INTO items VALUES (1, 30);
            INSERT INTO receipts VALUES (1, '2026-08-31T10:00:00', '2026-08-31T10:00:00', 'paid');
            INSERT INTO receipts VALUES (2, '2026-09-01T11:00:00', '2026-09-01T11:00:00', 'paid');
            INSERT INTO receipts VALUES (3, '2025-12-31T12:00:00', '2025-12-31T12:00:00', 'paid');
            INSERT INTO receipts VALUES (4, '2026-09-01T13:00:00', NULL, 'debt');
            INSERT INTO receipt_items VALUES (1, 1, 1, 2, 100, 40);
            INSERT INTO receipt_items VALUES (2, 2, 1, 1, 100, NULL);
            INSERT INTO receipt_items VALUES (3, 3, 1, 1, 50, 20);
            INSERT INTO receipt_items VALUES (4, 4, 1, 1, 999, 1);
            INSERT INTO expenses VALUES (1, '2026-08-31', 'Rent', 25, '', '', '', '');
            INSERT INTO expenses VALUES (2, '2026-09-01', 'Power', 10, '', '', '', '');
            INSERT INTO expenses VALUES (3, '2025-12-31', 'Old', 5, '', '', '', '');
        """)

    def tearDown(self):
        self.conn.close()

    def test_builds_daily_monthly_and_yearly_actual_profit(self):
        periods = build_financial_periods(self.conn, today=date(2026, 9, 3))

        daily = {row["period"]: row for row in periods["last_90_days"]}
        self.assertEqual(daily["2026-08-31"], {
            "period": "2026-08-31", "day": "2026-08-31", "orders": 1,
            "revenue": 200.0, "cost": 80.0, "gross_profit": 120.0,
            "expenses": 25.0, "net_profit": 95.0,
        })
        self.assertEqual(daily["2026-09-01"]["cost"], 30.0)
        self.assertEqual(daily["2026-09-01"]["net_profit"], 60.0)

        monthly = {row["period"]: row for row in periods["monthly"]}
        self.assertEqual(monthly["2026-08"]["net_profit"], 95.0)
        self.assertEqual(monthly["2026-09"]["net_profit"], 60.0)

        yearly = {row["period"]: row for row in periods["yearly"]}
        self.assertEqual(yearly["2025"]["revenue"], 50.0)
        self.assertEqual(yearly["2025"]["net_profit"], 25.0)
        self.assertEqual(yearly["2026"]["revenue"], 300.0)

    def test_excludes_unpaid_debt_from_income(self):
        periods = build_financial_periods(self.conn, today=date(2026, 9, 3))
        september = next(row for row in periods["monthly"] if row["period"] == "2026-09")
        self.assertEqual(september["orders"], 1)
        self.assertEqual(september["revenue"], 100.0)


if __name__ == "__main__":
    unittest.main()
