"""
Clean profit-related data without deleting receipts.

Default mode is report-only:
    python clean_profit_data.py

Apply fixes with a database backup:
    python clean_profit_data.py --apply

What it fixes:
- Relinks receipt_items.item_id by matching item names.
- Corrects obvious extra-zero costs, such as price 100 / cost 950 -> cost 95.
- Recalculates receipts.profit from receipt_items.
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cafe.db"


def norm_name(value):
    return " ".join((value or "").strip().split())


def infer_extra_zero_cost(price, cost):
    if price is None or cost is None:
        return None
    try:
        price = float(price)
        cost = float(cost)
    except (TypeError, ValueError):
        return None
    if price <= 0 or cost <= price:
        return None

    original = cost
    while cost > price and cost >= 10:
        cost = cost / 10

    if cost <= price and original / max(price, 1) >= 2:
        return round(cost, 4)
    return None


def backup_db():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "_restore_points" / f"before_profit_cleanup_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in ("cafe.db", "cafe.db-wal", "cafe.db-shm"):
        source = ROOT / name
        if source.exists():
            shutil.copy2(source, backup_dir / name)
    return backup_dir


def load_item_matches(cur):
    rows = cur.execute("SELECT id, name, price, cost FROM items").fetchall()
    by_name = {}
    duplicates = set()
    for item_id, name, price, cost in rows:
        key = norm_name(name)
        if key in by_name:
            duplicates.add(key)
        by_name[key] = (item_id, name, price, cost)
    for key in duplicates:
        by_name.pop(key, None)
    return by_name, duplicates


def analyze(conn):
    cur = conn.cursor()
    by_name, duplicate_names = load_item_matches(cur)

    item_cost_fixes = []
    for item_id, name, price, cost in cur.execute(
        "SELECT id, name, price, cost FROM items WHERE COALESCE(cost, 0) > COALESCE(price, 0)"
    ):
        fixed = infer_extra_zero_cost(price, cost)
        if fixed is not None:
            item_cost_fixes.append((item_id, name, price, cost, fixed))

    relinks = []
    line_cost_fixes = []
    for row in cur.execute(
        """
        SELECT id, receipt_id, item_id, name, qty, price, cost
        FROM receipt_items
        ORDER BY id
        """
    ):
        line_id, receipt_id, item_id, name, qty, price, cost = row
        match = by_name.get(norm_name(name))
        if item_id is None and match:
            relinks.append((line_id, match[0], name, match[1]))

        corrected_cost = None
        if cost is not None:
            corrected_cost = infer_extra_zero_cost(price, cost)

        if corrected_cost is None and match:
            _, _, item_price, item_cost = match
            if item_cost is not None and float(item_cost) <= float(price or 0) and float(cost or 0) > float(price or 0):
                corrected_cost = float(item_cost)

        if corrected_cost is not None:
            line_cost_fixes.append((line_id, receipt_id, name, price, cost, corrected_cost))

    negative_products = cur.execute(
        """
        SELECT name,
               SUM(qty) AS qty,
               SUM(qty * price) AS revenue,
               SUM(qty * cost) AS cost,
               SUM(qty * price - qty * cost) AS profit
        FROM receipt_items
        GROUP BY name
        HAVING profit < 0
        ORDER BY profit ASC
        """
    ).fetchall()

    totals = cur.execute(
        """
        SELECT COALESCE(SUM(qty * price), 0),
               COALESCE(SUM(qty * cost), 0),
               COALESCE(SUM(qty * price - qty * cost), 0)
        FROM receipt_items
        """
    ).fetchone()

    return {
        "duplicate_names": duplicate_names,
        "item_cost_fixes": item_cost_fixes,
        "relinks": relinks,
        "line_cost_fixes": line_cost_fixes,
        "negative_products": negative_products,
        "totals": totals,
    }


def print_report(report):
    revenue, cost, profit = report["totals"]
    print("Current receipt-item totals:")
    print(f"  revenue: {revenue:.2f}")
    print(f"  cost   : {cost:.2f}")
    print(f"  profit : {profit:.2f}")
    print()

    print(f"Receipt lines that can be relinked to inventory: {len(report['relinks'])}")
    print(f"Receipt line cost fixes: {len(report['line_cost_fixes'])}")
    print(f"Inventory item cost fixes: {len(report['item_cost_fixes'])}")
    if report["duplicate_names"]:
        print(f"Duplicate item names skipped for relink: {len(report['duplicate_names'])}")
    print()

    if report["line_cost_fixes"]:
        print("Receipt cost fixes preview:")
        for line_id, receipt_id, name, price, old_cost, new_cost in report["line_cost_fixes"][:20]:
            print(f"  line #{line_id} receipt #{receipt_id}: {name} price={price} cost {old_cost} -> {new_cost}")
        if len(report["line_cost_fixes"]) > 20:
            print(f"  ... {len(report['line_cost_fixes']) - 20} more")
        print()

    if report["item_cost_fixes"]:
        print("Inventory cost fixes preview:")
        for item_id, name, price, old_cost, new_cost in report["item_cost_fixes"][:20]:
            print(f"  item #{item_id}: {name} price={price} cost {old_cost} -> {new_cost}")
        if len(report["item_cost_fixes"]) > 20:
            print(f"  ... {len(report['item_cost_fixes']) - 20} more")
        print()

    if report["negative_products"]:
        print("Products currently negative before cleanup:")
        for name, qty, revenue, cost, profit in report["negative_products"][:20]:
            print(f"  {name}: qty={qty}, revenue={revenue}, cost={cost}, profit={profit}")


def apply_cleanup(conn, report):
    cur = conn.cursor()
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'trg_sync_%'")
    sync_triggers = cur.fetchall()
    for trigger_name, _sql in sync_triggers:
        cur.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")

    for item_id, _name, _price, _old_cost, new_cost in report["item_cost_fixes"]:
        cur.execute("UPDATE items SET cost = ? WHERE id = ?", (new_cost, item_id))

    for line_id, item_id, _line_name, _item_name in report["relinks"]:
        cur.execute("UPDATE receipt_items SET item_id = ? WHERE id = ?", (item_id, line_id))

    for line_id, _receipt_id, _name, _price, _old_cost, new_cost in report["line_cost_fixes"]:
        cur.execute("UPDATE receipt_items SET cost = ? WHERE id = ?", (new_cost, line_id))

    cur.execute(
        """
        UPDATE receipts
        SET profit = COALESCE((
            SELECT SUM(ri.qty * ri.price - ri.qty * COALESCE(ri.cost, 0))
            FROM receipt_items ri
            WHERE ri.receipt_id = receipts.id
        ), 0)
        """
    )
    for _trigger_name, trigger_sql in sync_triggers:
        if trigger_sql:
            cur.execute(trigger_sql)
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply fixes after creating a backup")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    try:
        report = analyze(conn)
        print_report(report)

        if not args.apply:
            print()
            print("Report only. Run with --apply to create a backup and fix the database.")
            return

        backup_dir = backup_db()
        apply_cleanup(conn, report)
        print()
        print(f"Applied cleanup. Backup saved to: {backup_dir}")

        after = analyze(conn)
        revenue, cost, profit = after["totals"]
        print("After cleanup receipt-item totals:")
        print(f"  revenue: {revenue:.2f}")
        print(f"  cost   : {cost:.2f}")
        print(f"  profit : {profit:.2f}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
