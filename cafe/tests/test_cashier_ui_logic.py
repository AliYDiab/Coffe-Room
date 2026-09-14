import unittest

from app_config import owner_password
from modules.cart_layout import calculate_cart_layout, diff_cart_rows


class CashierUiLogicTests(unittest.TestCase):
    def test_cart_expands_left_into_multiple_columns_without_scrolling(self):
        layout = calculate_cart_layout(item_count=30, body_width=1600, body_height=850)

        self.assertGreaterEqual(layout.columns, 2)
        self.assertGreater(layout.width, 400)
        self.assertGreaterEqual(layout.rows * layout.columns, 30)
        self.assertLessEqual(layout.width, 1600)

    def test_cart_stays_compact_for_a_small_order(self):
        layout = calculate_cart_layout(item_count=3, body_width=1200, body_height=700)

        self.assertEqual(layout.columns, 1)
        self.assertEqual(layout.width, 400)

    def test_cart_diff_updates_only_changed_rows(self):
        before = {
            "Coffee": {"qty": 1, "price": 1000},
            "Tea": {"qty": 1, "price": 750},
        }
        after = {
            "Coffee": {"qty": 2, "price": 1000},
            "Water": {"qty": 1, "price": 500},
        }

        changes = diff_cart_rows(before, after)

        self.assertEqual(changes.added, ("Water",))
        self.assertEqual(changes.updated, ("Coffee",))
        self.assertEqual(changes.removed, ("Tea",))

    def test_owner_password_defaults_to_1986_and_allows_override(self):
        self.assertEqual(owner_password({}), "1986")
        self.assertEqual(owner_password({"CAFE_OWNER_PASSWORD": "secure"}), "secure")


if __name__ == "__main__":
    unittest.main()
