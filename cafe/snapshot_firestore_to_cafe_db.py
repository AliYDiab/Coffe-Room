"""
One-time Firestore -> SQLite snapshot restore.

Run from the project folder:
    python snapshot_firestore_to_cafe_db.py

The script downloads the data shape produced by firebase_sync.py, builds a fresh
SQLite database, backs up the current cafe.db, then replaces cafe.db only after
the new database is created successfully.
"""

import argparse
import importlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cafe.db"
KEY_PATH = ROOT / "firebase_key.json"
WORK_DIR = ROOT / "_firestore_snapshot_work"


def init_firestore():
    if not KEY_PATH.exists():
        raise FileNotFoundError(f"Missing Firebase key: {KEY_PATH}")
    if not firebase_admin._apps:
        cred = credentials.Certificate(str(KEY_PATH))
        firebase_admin.initialize_app(cred)
    return firestore.client()


def normalize_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: normalize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_value(v) for v in value]
    return value


def doc_dict(doc):
    if not doc.exists:
        return {}
    return normalize_value(doc.to_dict() or {})


def bool_int(value, default=1):
    if value is None:
        return default
    return 1 if bool(value) else 0


def number(value, default=0):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def integer(value, default=None):
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def text(value, default=None):
    if value is None:
        return default
    return str(value)


def create_empty_db():
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir()

    previous_cwd = Path.cwd()
    sys.path.insert(0, str(ROOT))
    try:
        os.chdir(WORK_DIR)
        adb = importlib.import_module("adb")
        adb.init_db()
        importlib.import_module("modules.debt").init_debt_tables()
        importlib.import_module("modules.waste").init_waste_tables()
        adb.conn.close()
    finally:
        os.chdir(previous_cwd)
        if str(ROOT) in sys.path:
            sys.path.remove(str(ROOT))

    return WORK_DIR / "cafe.db"


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def insert_categories(cur, inventory):
    categories = inventory.get("categories") or []
    for category in categories:
        if category:
            cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (text(category),))

    for item in inventory.get("items") or []:
        category = item.get("category")
        if category:
            cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (text(category),))


def insert_inventory(cur, inventory):
    for item in inventory.get("items") or []:
        item_id = integer(item.get("id"))
        if item_id is None:
            continue
        cur.execute(
            """
            INSERT OR REPLACE INTO items
                (id, name, category, price, cost, stock, available, type, barcode_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                text(item.get("name"), f"item-{item_id}"),
                text(item.get("category"), "Uncategorized"),
                number(item.get("price")),
                number(item.get("cost")),
                integer(item.get("stock")),
                bool_int(item.get("available"), 1),
                text(item.get("type"), "fixed"),
                text(item.get("barcode_value")),
            ),
        )


def insert_ingredients(cur, ingredients_doc):
    for ingredient in ingredients_doc.get("list") or []:
        ing_id = integer(ingredient.get("id"))
        if ing_id is None:
            continue
        cur.execute(
            """
            INSERT OR REPLACE INTO ingredients (id, name, quantity, cost)
            VALUES (?, ?, ?, ?)
            """,
            (
                ing_id,
                text(ingredient.get("name"), f"ingredient-{ing_id}"),
                number(ingredient.get("quantity")),
                number(ingredient.get("cost")),
            ),
        )


def insert_receipts(cur, receipts_doc):
    for receipt in receipts_doc.get("list") or []:
        receipt_id = integer(receipt.get("id"))
        if receipt_id is None:
            continue
        cur.execute(
            """
            INSERT OR REPLACE INTO receipts
                (id, total, profit, date, status, customer, worker_id, session_id, shift_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_id,
                number(receipt.get("total")),
                number(receipt.get("profit")),
                text(receipt.get("date"), datetime.now().isoformat()),
                text(receipt.get("status"), "paid"),
                text(receipt.get("customer")),
                integer(receipt.get("worker_id")),
                integer(receipt.get("session_id")),
                text(receipt.get("shift_type")),
            ),
        )

        cur.execute("DELETE FROM receipt_items WHERE receipt_id = ?", (receipt_id,))
        for line in receipt.get("items") or []:
            cur.execute(
                """
                INSERT INTO receipt_items (receipt_id, item_id, name, qty, price, cost)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    integer(line.get("item_id")),
                    text(line.get("name"), ""),
                    number(line.get("qty")),
                    number(line.get("price")),
                    number(line.get("cost")),
                ),
            )


def backfill_shift_workers_from_receipts(cur):
    """Restore memberships for older shift documents from receipt ownership."""
    cur.execute(
        """
        INSERT OR IGNORE INTO shift_workers
            (session_id, worker_id, joined_at, last_joined_at)
        SELECT session_id, worker_id, MIN(date), MAX(date)
        FROM receipts
        WHERE session_id IS NOT NULL AND worker_id IS NOT NULL
        GROUP BY session_id, worker_id
        """
    )


def insert_debts(cur, debts_doc):
    for debt in debts_doc.get("list") or []:
        debt_id = integer(debt.get("id"))
        if debt_id is None:
            continue
        cur.execute(
            """
            INSERT OR REPLACE INTO debts
                (id, customer, amount, paid, note, created_at, receipt_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                debt_id,
                text(debt.get("customer"), ""),
                number(debt.get("amount")),
                number(debt.get("paid")),
                text(debt.get("note")),
                text(debt.get("created_at"), datetime.now().isoformat()),
                integer(debt.get("receipt_id")),
            ),
        )

        for payment in debt.get("payments") or []:
            cur.execute(
                """
                INSERT INTO debt_payments (debt_id, amount, paid_at, note)
                VALUES (?, ?, ?, ?)
                """,
                (
                    debt_id,
                    number(payment.get("amount")),
                    text(payment.get("paid_at"), datetime.now().isoformat()),
                    text(payment.get("note")),
                ),
            )


def insert_waste(cur, waste_doc):
    for entry in waste_doc.get("log") or []:
        cur.execute(
            """
            INSERT INTO waste_log (item_name, quantity, reason, logged_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                text(entry.get("item_name"), ""),
                number(entry.get("quantity")),
                text(entry.get("reason")),
                text(entry.get("logged_at"), datetime.now().isoformat()),
            ),
        )


def insert_workers(cur, db):
    for doc in db.collection("workers").stream():
        data = normalize_value(doc.to_dict() or {})
        worker_id = integer(doc.id) or integer(data.get("id"))
        if worker_id is None:
            continue
        cur.execute(
            """
            INSERT OR REPLACE INTO workers
                (id, name, active, rating, total_ratings, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                worker_id,
                text(data.get("name"), f"worker-{worker_id}"),
                bool_int(data.get("active"), 1),
                number(data.get("rating")),
                integer(data.get("total_ratings"), 0),
                text(data.get("created_at"), datetime.now().isoformat()),
            ),
        )


def insert_shift_schedules(cur, db):
    for doc in db.collection("shift_schedules").stream():
        data = normalize_value(doc.to_dict() or {})
        schedule_id = integer(doc.id) or integer(data.get("id"))
        if schedule_id is None:
            continue
        cur.execute(
            """
            INSERT OR REPLACE INTO shift_schedules
                (id, name, shift_type, start_hour, end_hour, allowed_workers, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule_id,
                text(data.get("name"), f"schedule-{schedule_id}"),
                text(data.get("shift_type"), "morning"),
                integer(data.get("start_hour"), 6),
                integer(data.get("end_hour"), 16),
                text(data.get("allowed_workers")),
                bool_int(data.get("is_active"), 1),
                text(data.get("created_at"), datetime.now().isoformat()),
                text(data.get("updated_at"), datetime.now().isoformat()),
            ),
        )


def insert_shift_sessions(cur, db):
    for doc in db.collection("shift_sessions").stream():
        data = normalize_value(doc.to_dict() or {})
        session_id = integer(doc.id) or integer(data.get("id"))
        if session_id is None:
            continue
        cur.execute(
            """
            INSERT OR REPLACE INTO shift_sessions
                (id, schedule_id, worker_id, date, start_time, end_time, status,
                 total_sales, total_revenue, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                integer(data.get("schedule_id")),
                integer(data.get("worker_id")),
                text(data.get("date"), datetime.now().date().isoformat()),
                text(data.get("start_time"), datetime.now().isoformat()),
                text(data.get("end_time")),
                text(data.get("status"), "completed"),
                number(data.get("total_sales")),
                number(data.get("total_revenue")),
                text(data.get("created_at"), datetime.now().isoformat()),
                text(data.get("updated_at"), datetime.now().isoformat()),
            ),
        )

        joined_at = text(data.get("start_time"), datetime.now().isoformat())
        opened_by_worker_id = integer(data.get("worker_id"))
        if opened_by_worker_id is not None:
            cur.execute(
                """
                INSERT OR IGNORE INTO shift_workers
                    (session_id, worker_id, joined_at, last_joined_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, opened_by_worker_id, joined_at, joined_at),
            )

        for worker in data.get("workers") or []:
            member_id = integer(worker.get("worker_id"))
            if member_id is None:
                continue
            cur.execute(
                """
                INSERT OR IGNORE INTO shift_workers
                    (session_id, worker_id, joined_at, last_joined_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, member_id, joined_at, joined_at),
            )


def insert_worker_ratings(cur, db):
    for doc in db.collection("worker_ratings").stream():
        data = normalize_value(doc.to_dict() or {})
        rating_id = integer(doc.id) or integer(data.get("id"))
        if rating_id is None:
            continue
        cur.execute(
            """
            INSERT OR REPLACE INTO worker_ratings
                (id, worker_id, session_id, rating, notes, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rating_id,
                integer(data.get("worker_id")),
                integer(data.get("session_id")),
                integer(data.get("rating"), 1),
                text(data.get("notes")),
                text(data.get("created_by")),
                text(data.get("created_at"), datetime.now().isoformat()),
            ),
        )


def clear_restore_artifacts(cur):
    cur.execute("DELETE FROM sync_queue")


def backup_current_db():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "_restore_points" / f"before_firestore_snapshot_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in ("cafe.db", "cafe.db-wal", "cafe.db-shm"):
        source = ROOT / name
        if source.exists():
            shutil.copy2(source, backup_dir / name)
    return backup_dir


def replace_db(new_db_path, dry_run=False):
    if dry_run:
        print(f"[DRY RUN] Built snapshot at: {new_db_path}")
        return None

    backup_dir = backup_current_db()
    for name in ("cafe.db-wal", "cafe.db-shm"):
        path = ROOT / name
        if path.exists():
            path.unlink()
    shutil.copy2(new_db_path, DB_PATH)
    return backup_dir


def restore(dry_run=False):
    print("[1/5] Connecting to Firestore...")
    db = init_firestore()

    print("[2/5] Reading Firestore snapshot...")
    cafe = db.collection("cafe")
    docs = {
        "inventory": doc_dict(cafe.document("inventory").get()),
        "ingredients": doc_dict(cafe.document("ingredients").get()),
        "receipts": doc_dict(cafe.document("receipts").get()),
        "debts": doc_dict(cafe.document("debts").get()),
        "waste": doc_dict(cafe.document("waste").get()),
    }

    print("[3/5] Creating new SQLite database...")
    new_db = create_empty_db()
    conn = connect(new_db)
    cur = conn.cursor()

    try:
        insert_categories(cur, docs["inventory"])
        insert_inventory(cur, docs["inventory"])
        insert_ingredients(cur, docs["ingredients"])
        insert_workers(cur, db)
        insert_shift_schedules(cur, db)
        insert_shift_sessions(cur, db)
        insert_worker_ratings(cur, db)
        insert_receipts(cur, docs["receipts"])
        backfill_shift_workers_from_receipts(cur)
        insert_debts(cur, docs["debts"])
        insert_waste(cur, docs["waste"])
        clear_restore_artifacts(cur)
        conn.commit()
    finally:
        conn.close()

    print("[4/5] Snapshot summary:")
    check = connect(new_db)
    try:
        summary = {}
        for table in (
            "categories",
            "items",
            "ingredients",
            "receipts",
            "receipt_items",
            "debts",
            "workers",
            "shift_schedules",
            "shift_sessions",
            "shift_workers",
            "worker_ratings",
            "waste_log",
        ):
            summary[table] = check.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    finally:
        check.close()

    print("[5/5] Replacing cafe.db...")
    backup_dir = replace_db(new_db, dry_run=dry_run)
    if backup_dir:
        print(f"[OK] Previous database backup: {backup_dir}")
        print(f"[OK] New database saved as: {DB_PATH}")
    else:
        print("[OK] Dry run completed. cafe.db was not replaced.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Build the DB but do not replace cafe.db")
    args = parser.parse_args()
    restore(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
