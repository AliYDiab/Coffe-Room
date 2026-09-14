"""
firebase_sync.py
────────────────
ضعه جنب CafeRoom.exe و firebase_key.json و cafe.db
بيشتغل بالخلفية ويرفع البيانات لـ Firestore كل 30 ثانية
+ بيرسل Push Notifications للمالك
"""

import os
import sys
import time
import sqlite3
import json
import traceback
from datetime import datetime, date, timedelta

import firebase_admin
from firebase_admin import credentials, firestore, messaging


# =====================================================
# PATHS
# =====================================================
def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR      = get_base_dir()
DB_PATH       = os.path.join(BASE_DIR, "cafe.db")
KEY_PATH      = os.path.join(BASE_DIR, "firebase_key.json")
TOKEN_PATH    = os.path.join(BASE_DIR, "device_token.txt")
SYNC_INTERVAL = 30   # seconds between each sync
SCHEMA_VERSION = 2
TOKEN_CACHE_SECONDS = 300
TOKEN_ERROR_BACKOFF_SECONDS = 300
_device_token_cache = None
_device_token_expires_at = 0
_device_token_retry_after = 0


# =====================================================
# INIT FIREBASE
# =====================================================
def init_firebase():
    if firebase_admin._apps:
        db = firestore.client()
        print("[OK] Firebase already connected")
        return db

    if not os.path.exists(KEY_PATH):
        print(f"[ERROR] firebase_key.json not found at: {KEY_PATH}")
        sys.exit(1)

    cred = credentials.Certificate(KEY_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("[OK] Firebase connected")
    return db


# =====================================================
# INIT SQLite
# =====================================================
def get_db():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] cafe.db not found at: {DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_sync_queue_and_triggers(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sync_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT,
            record_id INTEGER,
            action TEXT,
            status TEXT DEFAULT 'pending',
            retries INTEGER DEFAULT 0,
            notify_mobile INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("PRAGMA table_info(sync_queue)")
    if "notify_mobile" not in {column[1] for column in cur.fetchall()}:
        cur.execute(
            "ALTER TABLE sync_queue "
            "ADD COLUMN notify_mobile INTEGER NOT NULL DEFAULT 1"
        )

    trigger_tables = [
        "categories",
        "ingredients",
        "items",
        "item_ingredients",
        "receipts",
        "receipt_items",
        "workers",
        "worker_ratings",
        "worker_sessions",
        "shift_schedules",
        "shift_sessions",
        "shift_workers",
        "shift_handover",
        "debts",
        "debt_payments",
        "waste_log",
        "expenses",
    ]

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cur.fetchall()}

    for table_name in trigger_tables:
        if table_name not in existing_tables:
            continue
        for operation in ("INSERT", "UPDATE", "DELETE"):
            trigger_name = f"trg_sync_{table_name}_{operation.lower()}"
            record_expression = "NEW.id" if operation != "DELETE" else "OLD.id"
            cur.execute(f"""
                CREATE TRIGGER IF NOT EXISTS {trigger_name}
                AFTER {operation} ON {table_name}
                BEGIN
                    INSERT INTO sync_queue (table_name, record_id, action, status, created_at)
                    VALUES ('{table_name}', {record_expression}, '{operation.lower()}', 'pending', CURRENT_TIMESTAMP);
                END;
            """)

    conn.commit()


def sync_queue_watermark(conn):
    """Return the last queued change so one business action can be tagged."""
    try:
        row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM sync_queue").fetchone()
        return int(row[0] or 0)
    except sqlite3.OperationalError:
        return 0


def suppress_notifications_since(conn, watermark, keep_tables=()):
    """Suppress push for one action while leaving its Firestore sync queued."""
    columns = {
        column[1] for column in conn.execute("PRAGMA table_info(sync_queue)")
    }
    if "notify_mobile" not in columns:
        conn.execute(
            "ALTER TABLE sync_queue "
            "ADD COLUMN notify_mobile INTEGER NOT NULL DEFAULT 1"
        )

    params = [watermark]
    keep_clause = ""
    if keep_tables:
        placeholders = ",".join("?" for _ in keep_tables)
        keep_clause = f" AND table_name NOT IN ({placeholders})"
        params.extend(sorted(keep_tables))

    conn.execute(
        "UPDATE sync_queue SET notify_mobile=0 "
        f"WHERE id > ?{keep_clause}",
        params,
    )


def ensure_processed_mobile_requests(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_mobile_requests (
            operation_id TEXT PRIMARY KEY,
            collection_name TEXT NOT NULL,
            result_id INTEGER,
            processed_at TEXT NOT NULL
        )
    """)
    conn.commit()


def processed_mobile_result(conn, operation_id):
    row = conn.execute(
        "SELECT result_id FROM processed_mobile_requests WHERE operation_id=?",
        (operation_id,),
    ).fetchone()
    return row[0] if row else None


def record_processed_mobile_request(conn, operation_id, collection_name, result_id):
    conn.execute("""
        INSERT INTO processed_mobile_requests
            (operation_id, collection_name, result_id, processed_at)
        VALUES (?, ?, ?, ?)
    """, (operation_id, collection_name, result_id, datetime.now().isoformat()))


def mark_duplicate_request_synced(doc, result_field, result_id):
    doc.reference.set({
        'status': 'synced',
        'request_status': 'synced',
        'duplicate_prevented': True,
        'synced_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        result_field: result_id,
    }, merge=True)


# =====================================================
# LOAD DEVICE TOKEN (for push notifications)
# =====================================================
def load_device_token(db):
    global _device_token_cache, _device_token_expires_at, _device_token_retry_after

    now = time.time()
    if _device_token_cache and now < _device_token_expires_at:
        return _device_token_cache

    local_token = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "r") as f:
            local_token = f.read().strip() or None

    if now < _device_token_retry_after:
        return _device_token_cache or local_token

    # Try loading from Firestore first (where Flutter app saves it)
    if db is not None:
        try:
            doc = db.collection("cafe").document("device_token").get()
            if doc.exists:
                data = doc.to_dict()
                token = data.get("token")
                if token:
                    _device_token_cache = token
                    _device_token_expires_at = now + TOKEN_CACHE_SECONDS
                    try:
                        with open(TOKEN_PATH, "w") as f:
                            f.write(token)
                    except OSError:
                        pass
                    return token
        except Exception as e:
            _device_token_retry_after = now + TOKEN_ERROR_BACKOFF_SECONDS
            print(
                "[WARNING] Could not load token from Firestore; "
                f"using cached/local token for {TOKEN_ERROR_BACKOFF_SECONDS}s: {e}"
            )

    if local_token:
        _device_token_cache = local_token
        _device_token_expires_at = now + TOKEN_CACHE_SECONDS
        return local_token

    return _device_token_cache


# =====================================================
# SEND PUSH NOTIFICATION
# =====================================================
def send_notification(title, body, token=None, db=None):
    if not token:
        token = load_device_token(db)
    if not token:
        return

    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    channel_id="caferoom_alerts"
                )
            )
        )
        messaging.send(message)
        print(f"[NOTIF] Sent: {title}")
    except Exception as e:
        print(f"[NOTIF ERROR] {e}")


# =====================================================
# SYNC HELPERS
# =====================================================
def safe_val(v):
    """Convert sqlite values to Firestore-safe types."""
    if isinstance(v, (int, float, str, bool, type(None))):
        return v
    return str(v)

def row_to_dict(row):
    return {k: safe_val(row[k]) for k in row.keys()}


def ensure_receipt_columns(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(receipts)")
    cols = [c[1] for c in cur.fetchall()]

    if 'status' not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN status TEXT DEFAULT 'paid'")
    if 'customer' not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN customer TEXT")
    if 'worker_session_id' not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN worker_session_id INTEGER")
    if 'income_date' not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN income_date TEXT")

    conn.commit()


def ensure_category_exists(conn, category_name):
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (category_name,))


def ensure_expenses_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT DEFAULT CURRENT_TIMESTAMP,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            vendor TEXT,
            note TEXT,
            source TEXT DEFAULT 'desktop',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def upsert_item_from_mobile(conn, item_data):
    cur = conn.cursor()
    requested_item_id = item_data.get('item_id') or item_data.get('id')
    name = (item_data.get('name') or '').strip()
    category = (item_data.get('category') or '').strip()
    if not name or not category:
        return None

    ensure_category_exists(conn, category)

    price = safe_val(item_data.get('price'))
    cost = safe_val(item_data.get('cost', 0))
    stock = item_data.get('stock')
    available = 1 if item_data.get('available', True) else 0
    item_type = item_data.get('type') or 'fixed'
    barcode_value = item_data.get('barcode_value')

    existing = None
    if requested_item_id:
        cur.execute("SELECT id FROM items WHERE id=?", (requested_item_id,))
        existing = cur.fetchone()

    if not existing:
        cur.execute("SELECT id FROM items WHERE name=?", (name,))
        existing = cur.fetchone()

    if existing:
        item_id = existing[0]
        cur.execute("""
            UPDATE items
            SET category=?, price=?, cost=?, stock=?, available=?, type=?, barcode_value=?
            WHERE id=?
        """, (category, price, cost, stock, available, item_type, barcode_value, item_id))
    else:
        cur.execute("""
            INSERT INTO items (name, category, price, cost, stock, available, type, barcode_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, category, price, cost, stock, available, item_type, barcode_value))
        item_id = cur.lastrowid

    return item_id


def increment_item_stock_from_mobile(conn, item_data):
    """Atomically add stock without replacing a newer desktop quantity."""
    cur = conn.cursor()
    item_id = item_data.get('item_id') or item_data.get('id')
    try:
        quantity_delta = int(item_data.get('quantity_delta'))
    except (TypeError, ValueError):
        return None
    if not item_id or quantity_delta <= 0:
        return None

    cur.execute("""
        UPDATE items
        SET stock = COALESCE(stock, 0) + ?, available = 1
        WHERE id = ? AND type = 'fixed'
    """, (quantity_delta, item_id))
    if cur.rowcount == 0:
        return None

    return item_id


def delete_item_from_mobile(conn, item_data):
    cur = conn.cursor()
    item_id = item_data.get('item_id') or item_data.get('id')
    if not item_id:
        return None

    cur.execute("SELECT id FROM items WHERE id=?", (item_id,))
    if not cur.fetchone():
        return None

    cur.execute("DELETE FROM item_ingredients WHERE item_id=?", (item_id,))
    cur.execute("DELETE FROM items WHERE id=?", (item_id,))
    return item_id


def import_mobile_inventory_requests(conn, db):
    cur = conn.cursor()
    docs = db.collection('mobile_inventory_requests').where('status', '==', 'pending').get()

    imported = 0
    for doc in docs:
        data = doc.to_dict() or {}
        operation_id = data.get('operation_id') or doc.id
        previous_result = processed_mobile_result(conn, operation_id)
        if previous_result is not None:
            mark_duplicate_request_synced(doc, 'item_id', previous_result)
            continue
        action = data.get('action') or 'upsert'
        if action == 'delete':
            item_id = delete_item_from_mobile(conn, data)
        elif action == 'increment_stock':
            item_id = increment_item_stock_from_mobile(conn, data)
        else:
            item_id = upsert_item_from_mobile(conn, data)
        if item_id:
            record_processed_mobile_request(
                conn, operation_id, 'mobile_inventory_requests', item_id)
            conn.commit()
            doc.reference.set({
                'status': 'synced',
                'request_status': 'synced',
                'synced_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'item_id': item_id,
            }, merge=True)
            imported += 1
        else:
            doc.reference.set({
                'status': 'error',
                'request_status': 'error',
                'error_message': 'Inventory item was not found or the request was incomplete.',
                'error_message_ar': 'العنصر غير موجود أو بيانات الطلب غير مكتملة.',
                'updated_at': datetime.now().isoformat(),
            }, merge=True)

    if imported:
        print(f"[IMPORT] Synced {imported} mobile inventory item(s)")

    return imported


def import_mobile_receipt_requests(conn, db):
    cur = conn.cursor()
    ensure_receipt_columns(conn)

    docs = db.collection('mobile_receipt_requests').where('status', '==', 'pending').get()

    imported = 0
    for doc in docs:
        data = doc.to_dict() or {}
        operation_id = data.get('operation_id') or doc.id
        previous_result = processed_mobile_result(conn, operation_id)
        if previous_result is not None:
            mark_duplicate_request_synced(doc, 'receipt_id', previous_result)
            continue
        receipt_date = data.get('date') or datetime.now().isoformat()
        customer = data.get('customer')
        status = data.get('receipt_status') or 'paid'
        if status not in {'paid', 'debt', 'partial'}:
            status = 'paid'
        items = data.get('items') or []

        if status == 'debt' and not customer:
            doc.reference.set({
                'status': 'error',
                'request_status': 'error',
                'error_message': 'Debt receipts require a customer name.',
                'error_message_ar': 'فاتورة الدين تحتاج إلى اسم الزبون.',
                'updated_at': datetime.now().isoformat(),
            }, merge=True)
            print("[IMPORT] Rejected debt receipt without customer name")
            continue

        if not isinstance(items, list) or not items:
            continue

        total = 0.0
        normalized_items = []

        for item in items:
            if not isinstance(item, dict):
                continue

            qty = float(item.get('qty') or 0)
            if qty <= 0:
                continue

            item_id = item.get('item_id')
            item_name = (item.get('name') or '').strip()
            price = float(item.get('price') or 0)
            cost = float(item.get('cost') or 0)
            item_type = item.get('type') or 'fixed'

            if not item_id and item_name:
                cur.execute("SELECT id, type, cost, price FROM items WHERE name=?", (item_name,))
                matched = cur.fetchone()
                if matched:
                    item_id = matched[0]
                    item_type = matched[1] or item_type
                    cost = matched[2] or cost
                    price = matched[3] or price

            if not item_id:
                continue

            cur.execute("SELECT name, stock, type, cost, price FROM items WHERE id=?", (item_id,))
            current = cur.fetchone()
            if current:
                item_name = current[0] or item_name
                current_stock = current[1]
                item_type = current[2] or item_type
                cost = current[3] or cost
                price = current[4] or price
            else:
                current_stock = None

            subtotal = price * qty
            total += subtotal

            normalized_items.append((item_id, item_name, qty, price, cost, item_type))

        if not normalized_items:
            continue

        notification_watermark = sync_queue_watermark(conn)
        cur.execute("""
            INSERT INTO receipts (date, total, status, customer, income_date)
            VALUES (?, ?, ?, ?, ?)
        """, (receipt_date, 0, status, customer, receipt_date if status == 'paid' else None))
        receipt_id = cur.lastrowid

        for item_id, item_name, qty, price, cost, item_type in normalized_items:
            try:
                cur.execute("""
                    INSERT INTO receipt_items (receipt_id, item_id, name, qty, price, cost)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (receipt_id, item_id, item_name, qty, price, cost))
            except sqlite3.OperationalError:
                cur.execute("""
                    INSERT INTO receipt_items (receipt_id, name, qty, price)
                    VALUES (?, ?, ?, ?)
                """, (receipt_id, item_name, qty, price))

            try:
                from utils import handle_sale
                handle_sale(cur, item_id, item_type, qty)
            except Exception as exc:
                print(f"[IMPORT] Could not apply sale for item {item_id}: {exc}")

        cur.execute("UPDATE receipts SET total=? WHERE id=?", (total, receipt_id))

        if status == 'debt' and customer:
            try:
                cur.execute("""
                    INSERT INTO debts (customer, amount, paid, note, created_at, receipt_id)
                    VALUES (?, ?, 0, ?, ?, ?)
                """, (customer, total, 'إدخال يدوي من الهاتف', receipt_date, receipt_id))
            except sqlite3.OperationalError:
                pass

        # Do not echo a mobile-created receipt back to the phone as a push.
        suppress_notifications_since(conn, notification_watermark)
        conn.commit()
        doc.reference.set({
            'status': 'synced',
            'request_status': 'synced',
            'synced_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'receipt_id': receipt_id,
            'total': total,
        }, merge=True)
        imported += 1

    if imported:
        print(f"[IMPORT] Synced {imported} mobile receipt(s)")

    return imported


def import_mobile_expense_requests(conn, db):
    cur = conn.cursor()
    ensure_expenses_table(conn)

    docs = db.collection('mobile_expense_requests').where('status', '==', 'pending').get()

    imported = 0
    for doc in docs:
        data = doc.to_dict() or {}
        operation_id = data.get('operation_id') or doc.id
        previous_result = processed_mobile_result(conn, operation_id)
        if previous_result is not None:
            mark_duplicate_request_synced(doc, 'expense_id', previous_result)
            continue
        action = data.get('action') or 'create'
        expense_id = data.get('expense_id') or data.get('id')
        category = (data.get('category') or '').strip() or 'Other'
        try:
            amount = float(data.get('amount') or 0)
        except (TypeError, ValueError):
            amount = 0
        if amount <= 0:
            continue

        expense_date = data.get('date') or datetime.now().isoformat()
        vendor = (data.get('vendor') or '').strip() or None
        note = (data.get('note') or '').strip() or None

        if action == 'update' and expense_id:
            cur.execute("SELECT id FROM expenses WHERE id=?", (expense_id,))
            if not cur.fetchone():
                doc.reference.set({
                    'status': 'error',
                    'request_status': 'error',
                    'error_message': f'Expense #{expense_id} was not found.',
                    'error_message_ar': 'المصروف المطلوب تعديله غير موجود.',
                    'updated_at': datetime.now().isoformat(),
                }, merge=True)
                continue

            cur.execute("""
                UPDATE expenses
                SET date=?, category=?, amount=?, vendor=?, note=?, source='flutter'
                WHERE id=?
            """, (expense_date, category, amount, vendor, note, expense_id))
        else:
            cur.execute("""
                INSERT INTO expenses (date, category, amount, vendor, note, source, created_at)
                VALUES (?, ?, ?, ?, ?, 'flutter', ?)
            """, (expense_date, category, amount, vendor, note, datetime.now().isoformat()))
            expense_id = cur.lastrowid
        record_processed_mobile_request(
            conn, operation_id, 'mobile_receipt_requests', receipt_id)
        record_processed_mobile_request(
            conn, operation_id, 'mobile_expense_requests', expense_id)
        conn.commit()

        doc.reference.set({
            'status': 'synced',
            'request_status': 'synced',
            'synced_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'expense_id': expense_id,
        }, merge=True)
        imported += 1

    if imported:
        print(f"[IMPORT] Synced {imported} mobile expense(s)")

    return imported


def ensure_optional_tables():
    try:
        from modules.debt import init_debt_tables
        init_debt_tables()
    except Exception as exc:
        print(f"[WARN] debt tables not ready: {exc}")

    try:
        from modules.waste import init_waste_tables
        init_waste_tables()
    except Exception as exc:
        print(f"[WARN] waste tables not ready: {exc}")


SYNC_TARGETS = {
    "inventory": ["sync_inventory"],
    "receipts": ["sync_receipts"],
    "debts": ["sync_debts"],
    "waste": ["sync_waste"],
    "analytics": ["sync_analytics"],
    "ingredients": ["sync_ingredients"],
    "workers": ["sync_workers"],
    "worker_sessions": ["sync_worker_sessions"],
    "shift_schedules": ["sync_shift_schedules"],
    "shift_sessions": ["sync_shift_sessions"],
    "worker_ratings": ["sync_worker_ratings"],
    "dashboard": ["sync_dashboard"],
    "expenses": ["sync_expenses"],
}


TABLE_DOMAIN_MAP = {
    "categories": {"inventory", "analytics", "dashboard"},
    "ingredients": {"inventory", "ingredients", "analytics", "dashboard"},
    "items": {"inventory", "analytics", "dashboard"},
    "item_ingredients": {"inventory", "ingredients", "analytics", "dashboard"},
    "receipts": {"receipts", "analytics", "dashboard", "inventory"},
    "receipt_items": {"receipts", "analytics", "dashboard", "inventory"},
    "debts": {"debts", "dashboard"},
    "debt_payments": {"debts", "dashboard"},
    "waste_log": {"waste", "dashboard"},
    "expenses": {"expenses", "analytics", "dashboard"},
    "workers": {"workers"},
    "worker_sessions": {"worker_sessions", "workers"},
    "shift_schedules": {"shift_schedules"},
    "shift_sessions": {"shift_sessions"},
    "shift_workers": {"shift_sessions"},
    "shift_handover": set(),
    "worker_ratings": {"worker_ratings", "workers"},
}


def _change_action_label(action):
    return {
        "insert": "Added",
        "update": "Updated",
        "delete": "Deleted",
    }.get(action, "Changed")


def _record_label(cur, table_name, record_id):
    if not record_id:
        return None

    lookup = {
        "categories": ("categories", "name"),
        "ingredients": ("ingredients", "name"),
        "items": ("items", "name"),
        "workers": ("workers", "name"),
        "debts": ("debts", "customer"),
        "waste_log": ("waste_log", "item_name"),
        "expenses": ("expenses", "category"),
    }.get(table_name)

    if not lookup:
        return None

    source_table, label_column = lookup
    try:
        cur.execute(f"SELECT {label_column} FROM {source_table} WHERE id=?", (record_id,))
        row = cur.fetchone()
        if row and row[0]:
            return str(row[0])
    except Exception:
        return None

    return None


def build_change_notification(cur, rows):
    changes = []
    silent_tables = {"receipts", "receipt_items"}
    notification_rows = [
        row for row in rows
        if (len(row) < 5 or bool(row[4])) and row[1] not in silent_tables
    ]

    for row in notification_rows:
        table_name = row[1]
        record_id = row[2]
        action = row[3]

        if len(changes) >= 3:
            continue

        label = _record_label(cur, table_name, record_id)
        action_label = _change_action_label(action)
        friendly_table = table_name.replace("_", " ")
        if label:
            changes.append(f"{action_label} {friendly_table}: {label}")
        else:
            changes.append(f"{action_label} {friendly_table} #{record_id}")

    if not changes:
        return None

    total = len(notification_rows)
    title = "CafeRoom update"
    body = "; ".join(changes)
    if total > len(changes):
        body += f"; +{total - len(changes)} more"

    return title, body


def process_pending_queue(conn, db, prev_state):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, table_name, record_id, action, notify_mobile
        FROM sync_queue
        WHERE status = 'pending'
        ORDER BY id ASC
    """)
    rows = cur.fetchall()

    if not rows:
        return 0

    affected = set()
    queue_ids = []

    for row in rows:
        queue_ids.append(row[0])
        table_name = row[1]
        affected.update(TABLE_DOMAIN_MAP.get(table_name, set()))

    try:
        change_notification = build_change_notification(cur, rows)
        if affected:
            token = load_device_token(db)
            if "dashboard" in affected:
                sync_dashboard(conn, db, prev_state)
            if "inventory" in affected:
                sync_inventory(conn, db)
            if "receipts" in affected:
                sync_receipts(conn, db, prev_state, token)
            if "debts" in affected:
                sync_debts(conn, db, prev_state, token)
            if "waste" in affected:
                sync_waste(conn, db)
            if "analytics" in affected:
                sync_analytics(conn, db)
            if "ingredients" in affected:
                sync_ingredients(conn, db)
            if "workers" in affected:
                sync_workers(conn, db)
            if "worker_sessions" in affected:
                sync_worker_sessions(conn, db)
            if "shift_schedules" in affected:
                sync_shift_schedules(conn, db)
            if "shift_sessions" in affected:
                sync_shift_sessions(conn, db)
            if "worker_ratings" in affected:
                sync_worker_ratings(conn, db)
            if "expenses" in affected:
                sync_expenses(conn, db)

        if change_notification:
            token = load_device_token(db)
            send_notification(change_notification[0], change_notification[1], token, db)

        cur.executemany("DELETE FROM sync_queue WHERE id = ?", [(qid,) for qid in queue_ids])
        conn.commit()
        print(f"[SYNC] Processed {len(queue_ids)} queued change(s)")
        return len(queue_ids)
    except Exception as exc:
        print(f"[SYNC ERROR] Could not process queue: {exc}")
        conn.rollback()
        return 0


def initial_full_sync(conn, db, prev_state):
    token = load_device_token(db)
    sync_dashboard(conn, db, prev_state)
    sync_inventory(conn, db)
    sync_receipts(conn, db, prev_state, token)
    sync_debts(conn, db, prev_state, token)
    sync_waste(conn, db)
    sync_analytics(conn, db)
    sync_ingredients(conn, db)
    sync_workers(conn, db)
    sync_worker_sessions(conn, db)
    sync_shift_schedules(conn, db)
    sync_shift_sessions(conn, db)
    sync_worker_ratings(conn, db)
    sync_expenses(conn, db)


def push_all_database_to_firestore():
    """Run a manual full upload of the local SQLite data to Firestore."""
    if not firebase_admin._apps and not os.path.exists(KEY_PATH):
        raise FileNotFoundError(f"firebase_key.json not found at: {KEY_PATH}")

    db = init_firebase()
    conn = get_db()

    try:
        ensure_optional_tables()
        initial_full_sync(conn, db, {})
        return True
    finally:
        conn.close()


def wrap_doc(entity, data, ui_sections=None):
    payload = dict(data)
    payload["schema_version"] = SCHEMA_VERSION
    payload["entity"] = entity
    payload["ui_sections"] = ui_sections or []
    payload["last_updated"] = datetime.now().isoformat()
    return payload


# =====================================================
# SYNC: DASHBOARD SUMMARY
# =====================================================
def sync_dashboard(conn, db, prev_state):
    cur = conn.cursor()
    today = date.today().isoformat()

    # today sales
    cur.execute("""
        SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as revenue
        FROM receipts
        WHERE COALESCE(income_date, date) LIKE ? AND (status IS NULL OR status = 'paid')
    """, (f"{today}%",))
    today_row = cur.fetchone()

    # total
    cur.execute("SELECT COUNT(*), COALESCE(SUM(total), 0) FROM receipts WHERE status IS NULL OR status='paid'")
    total_row = cur.fetchone()

    cur.execute("""
        SELECT COALESCE(SUM(ri.qty * ri.price - ri.qty * COALESCE(ri.cost, i.cost, 0)), 0)
        FROM receipt_items ri
        JOIN receipts r ON r.id = ri.receipt_id
        LEFT JOIN items i ON i.id = ri.item_id
        WHERE COALESCE(r.income_date, r.date) LIKE ? AND (r.status IS NULL OR r.status = 'paid')
    """, (f"{today}%",))
    today_gross_profit = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COALESCE(SUM(ri.qty * ri.price - ri.qty * COALESCE(ri.cost, i.cost, 0)), 0)
        FROM receipt_items ri
        JOIN receipts r ON r.id = ri.receipt_id
        LEFT JOIN items i ON i.id = ri.item_id
        WHERE r.status IS NULL OR r.status = 'paid'
    """)
    total_gross_profit = cur.fetchone()[0] or 0

    ensure_expenses_table(conn)
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date LIKE ?", (f"{today}%",))
    today_expenses = cur.fetchone()[0] or 0

    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses")
    total_expenses = cur.fetchone()[0] or 0

    # debts
    cur.execute("SELECT COALESCE(SUM(amount-paid), 0) FROM debts")
    debt_remain = cur.fetchone()[0] or 0

    # low stock items
    cur.execute("""
        SELECT COUNT(*) FROM items
        WHERE type='fixed' AND stock IS NOT NULL AND stock <= 10 AND stock > 0
    """)
    low_stock_count = cur.fetchone()[0] or 0

    # out of stock
    cur.execute("""
        SELECT COUNT(*) FROM items
        WHERE type='fixed' AND stock IS NOT NULL AND stock = 0
    """)
    out_stock_count = cur.fetchone()[0] or 0

    # top 5 items today
    cur.execute("""
        SELECT ri.name, SUM(ri.qty) as qty, SUM(ri.qty * ri.price) as revenue
        FROM receipt_items ri
        JOIN receipts r ON r.id = ri.receipt_id
        WHERE COALESCE(r.income_date, r.date) LIKE ?
          AND (r.status IS NULL OR r.status = 'paid')
        GROUP BY ri.name
        ORDER BY qty DESC
        LIMIT 5
    """, (f"{today}%",))
    top_items = [row_to_dict(r) for r in cur.fetchall()]

    # waste today
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(quantity), 0)
        FROM waste_log WHERE logged_at LIKE ?
    """, (f"{today}%",))
    waste_row = cur.fetchone()

    data = {
        "today_orders":    today_row[0],
        "today_revenue":   round(today_row[1], 2),
        "total_orders":    total_row[0],
        "total_revenue":   round(total_row[1], 2),
        "today_gross_profit": round(today_gross_profit, 2),
        "today_expenses": round(today_expenses, 2),
        "today_net_profit": round(today_gross_profit - today_expenses, 2),
        "total_gross_profit": round(total_gross_profit, 2),
        "total_expenses": round(total_expenses, 2),
        "net_profit": round(total_gross_profit - total_expenses, 2),
        "debt_remaining":  round(debt_remain, 2),
        "low_stock_count": low_stock_count,
        "out_stock_count": out_stock_count,
        "top_items_today": top_items,
        "waste_today_count": waste_row[0],
        "waste_today_qty":   round(waste_row[1], 2),
        "last_updated":    datetime.now().isoformat(),
    }

    db.collection("cafe").document("dashboard").set(
        wrap_doc(
            "dashboard",
            data,
            [
                {"title": "ملخص", "type": "stats", "keys": ["today_orders", "today_revenue", "total_orders", "total_revenue", "debt_remaining", "low_stock_count", "out_stock_count", "waste_today_count", "waste_today_qty"]},
                {"title": "أفضل الأصناف اليوم", "type": "list", "key": "top_items_today"},
            ]
        )
    )

    # ── notifications ──
    token = load_device_token(db)

    # low stock alert (only when count changes)
    prev_low = prev_state.get("low_stock_count", -1)
    if low_stock_count > 0 and low_stock_count != prev_low:
        send_notification(
            "⚠️ تحذير مخزون",
            f"{low_stock_count} عنصر وصل للحد الأدنى!",
            token,
            db
        )

    # out of stock
    prev_out = prev_state.get("out_stock_count", -1)
    if out_stock_count > 0 and out_stock_count != prev_out:
        send_notification(
            "🚨 نفاد مخزون",
            f"{out_stock_count} عنصر نفد من المخزون!",
            token,
            db
        )

    prev_state["low_stock_count"] = low_stock_count
    prev_state["out_stock_count"] = out_stock_count

    return data


# =====================================================
# SYNC: INVENTORY
# =====================================================
def sync_inventory(conn, db):
    cur = conn.cursor()
    cur.execute("""
        SELECT i.id, i.name, i.category, i.price, i.cost,
               i.stock, i.type, i.available, i.barcode_value,
               COALESCE(SUM(ri.qty), 0) as total_sold
        FROM items i
        LEFT JOIN receipt_items ri ON i.id = ri.item_id
        GROUP BY i.id
        ORDER BY i.name
    """)
    items = [row_to_dict(r) for r in cur.fetchall()]

    # categories
    cur.execute("SELECT name FROM categories ORDER BY name")
    categories = [r[0] for r in cur.fetchall()]

    db.collection("cafe").document("inventory").set(
        wrap_doc(
            "inventory",
            {
                "items": items,
                "categories": categories,
                "count": len(items),
            },
            [
                {"title": "الفئات", "type": "chips", "key": "categories"},
                {"title": "العناصر", "type": "cards", "key": "items", "primary_label": "name", "fields": ["category", "price", "cost", "stock", "type", "available", "barcode_value", "total_sold"]},
            ]
        )
    )


# =====================================================
# SYNC: RECEIPTS (last 100)
# =====================================================
def sync_receipts(conn, db, prev_state, token):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, total, profit, date, status, customer,
               worker_id, worker_session_id, income_date
        FROM receipts
        ORDER BY id DESC
        LIMIT 100
    """)
    receipts = []
    for r in cur.fetchall():
        receipt = row_to_dict(r)
        # fetch items for this receipt
        cur.execute("""
            SELECT item_id, name, qty, price, cost
            FROM receipt_items WHERE receipt_id=?
        """, (r["id"],))
        receipt["items"] = [row_to_dict(i) for i in cur.fetchall()]
        receipts.append(receipt)

    db.collection("cafe").document("receipts").set(
        wrap_doc(
            "receipts",
            {"list": receipts},
            [
                {"title": "الفواتير", "type": "cards", "key": "list", "primary_label": "id", "fields": ["total", "date", "status", "customer", "worker_id", "worker_session_id", "income_date", "items"]},
            ]
        )
    )

    # New receipts are intentionally synced without a push notification.


# =====================================================
# SYNC: DEBTS
# =====================================================
def sync_debts(conn, db, prev_state, token):
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.customer, d.amount, d.paid,
               (d.amount - d.paid) as remaining,
               d.note, d.created_at, d.receipt_id
        FROM debts d
        ORDER BY remaining DESC
    """)
    debts = []
    for d in cur.fetchall():
        debt = row_to_dict(d)
        # payment history
        cur.execute("""
            SELECT amount, paid_at, note
            FROM debt_payments WHERE debt_id=?
            ORDER BY paid_at DESC
        """, (d["id"],))
        debt["payments"] = [row_to_dict(p) for p in cur.fetchall()]
        debts.append(debt)

    total_remaining = sum(d["remaining"] for d in debts if d["remaining"] > 0)

    db.collection("cafe").document("debts").set(
        wrap_doc(
            "debts",
            {
                "list": debts,
                "total_remaining": round(total_remaining, 2),
                "count": len(debts),
            },
            [
                {"title": "الديون", "type": "cards", "key": "list", "primary_label": "customer", "fields": ["amount", "paid", "remaining", "note", "created_at", "receipt_id", "payments"]},
            ]
        )
    )

    # notify on new debt
    prev_debt_count = prev_state.get("debt_count", 0)
    if len(debts) > prev_debt_count and prev_debt_count > 0:
        newest = max(debts, key=lambda item: item.get("id") or 0) if debts else None
        if newest:
            send_notification(
                "💳 دين جديد",
                f"{newest['customer']}  —  {newest['amount']:,.0f} SYP",
                token,
                db
            )
    prev_state["debt_count"] = len(debts)


# =====================================================
# SYNC: WASTE
# =====================================================
def sync_waste(conn, db):
    cur = conn.cursor()
    cur.execute("""
        SELECT item_name, quantity, reason, logged_at
        FROM waste_log
        ORDER BY logged_at DESC
        LIMIT 200
    """)
    waste_log = [row_to_dict(r) for r in cur.fetchall()]

    # stats: top wasted items
    cur.execute("""
        SELECT item_name,
               COUNT(*)      as entries,
               SUM(quantity) as total_qty
        FROM waste_log
        GROUP BY item_name
        ORDER BY total_qty DESC
        LIMIT 10
    """)
    top_waste = [row_to_dict(r) for r in cur.fetchall()]

    # by reason
    cur.execute("""
        SELECT COALESCE(reason,'بدون سبب') as reason,
               COUNT(*) as count,
               SUM(quantity) as total_qty
        FROM waste_log
        GROUP BY reason
        ORDER BY count DESC
    """)
    by_reason = [row_to_dict(r) for r in cur.fetchall()]

    db.collection("cafe").document("waste").set(
        wrap_doc(
            "waste",
            {
                "log": waste_log,
                "top_items": top_waste,
                "by_reason": by_reason,
            },
            [
                {"title": "السجل", "type": "cards", "key": "log", "primary_label": "item_name", "fields": ["quantity", "reason", "logged_at"]},
                {"title": "الأسباب", "type": "list", "key": "by_reason"},
            ]
        )
    )


# =====================================================
# SYNC: EXPENSES
# =====================================================
def sync_expenses(conn, db):
    cur = conn.cursor()
    ensure_expenses_table(conn)

    cur.execute("""
        SELECT id, date, category, amount, vendor, note, source, created_at
        FROM expenses
        ORDER BY date DESC, id DESC
        LIMIT 200
    """)
    expenses = [row_to_dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT DATE(date) as day,
               COALESCE(SUM(amount), 0) as amount
        FROM expenses
        WHERE date >= DATE('now', '-30 days')
        GROUP BY day
        ORDER BY day ASC
    """)
    last_30_days = [row_to_dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT category,
               COALESCE(SUM(amount), 0) as amount
        FROM expenses
        GROUP BY category
        ORDER BY amount DESC
    """)
    by_category = [row_to_dict(r) for r in cur.fetchall()]

    db.collection("cafe").document("expenses").set(
        wrap_doc(
            "expenses",
            {
                "list": expenses,
                "last_30_days": last_30_days,
                "by_category": by_category,
                "total": round(sum((e.get("amount") or 0) for e in expenses), 2),
            },
            [
                {"title": "Expenses", "type": "cards", "key": "list", "primary_label": "category", "fields": ["amount", "date", "vendor", "note", "source"]},
                {"title": "Expense categories", "type": "chart", "key": "by_category"},
            ]
        )
    )


# =====================================================
# SYNC: ANALYTICS
# =====================================================
def _financial_rows(conn, period_sql, since_date=None, include_day=False):
    """Aggregate paid income and expenses for one SQLite calendar period."""
    sales_params = []
    sales_filter = ""
    if since_date is not None:
        sales_filter = " AND DATE(COALESCE(r.income_date, r.date)) >= DATE(?)"
        sales_params.append(since_date.isoformat())

    sales = conn.execute(f"""
        SELECT {period_sql.format(value='COALESCE(r.income_date, r.date)')} AS period,
               COUNT(DISTINCT r.id) AS orders,
               COALESCE(SUM(ri.qty * ri.price), 0) AS revenue,
               COALESCE(SUM(ri.qty * COALESCE(ri.cost, i.cost, 0)), 0) AS cost
        FROM receipts r
        LEFT JOIN receipt_items ri ON ri.receipt_id = r.id
        LEFT JOIN items i ON i.id = ri.item_id
        WHERE (r.status IS NULL OR r.status = 'paid')
          AND COALESCE(r.income_date, r.date) IS NOT NULL
          {sales_filter}
        GROUP BY period
        ORDER BY period ASC
    """, sales_params).fetchall()

    expense_params = []
    expense_filter = ""
    if since_date is not None:
        expense_filter = " WHERE DATE(date) >= DATE(?)"
        expense_params.append(since_date.isoformat())
    expenses = conn.execute(f"""
        SELECT {period_sql.format(value='date')} AS period,
               COALESCE(SUM(amount), 0) AS expenses
        FROM expenses
        {expense_filter}
        GROUP BY period
        ORDER BY period ASC
    """, expense_params).fetchall()

    combined = {}
    for row in sales:
        period = row["period"]
        if not period:
            continue
        revenue = float(row["revenue"] or 0)
        cost = float(row["cost"] or 0)
        combined[period] = {
            "period": period,
            "orders": int(row["orders"] or 0),
            "revenue": round(revenue, 2),
            "cost": round(cost, 2),
            "gross_profit": round(revenue - cost, 2),
            "expenses": 0.0,
            "net_profit": round(revenue - cost, 2),
        }

    for row in expenses:
        period = row["period"]
        if not period:
            continue
        entry = combined.setdefault(period, {
            "period": period,
            "orders": 0,
            "revenue": 0.0,
            "cost": 0.0,
            "gross_profit": 0.0,
            "expenses": 0.0,
            "net_profit": 0.0,
        })
        entry["expenses"] = round(float(row["expenses"] or 0), 2)
        entry["net_profit"] = round(
            float(entry["gross_profit"]) - entry["expenses"], 2
        )

    rows = [combined[key] for key in sorted(combined)]
    if include_day:
        for row in rows:
            row["day"] = row["period"]
    return rows


def build_financial_periods(conn, today=None):
    """Return compact daily/monthly/yearly financial aggregates for reports."""
    today = today or date.today()
    daily_since = today - timedelta(days=89)
    return {
        "last_90_days": _financial_rows(
            conn, "DATE({value})", since_date=daily_since, include_day=True
        ),
        "monthly": _financial_rows(conn, "strftime('%Y-%m', {value})"),
        "yearly": _financial_rows(conn, "strftime('%Y', {value})"),
    }


def sync_analytics(conn, db):
    cur = conn.cursor()
    ensure_expenses_table(conn)
    financial = build_financial_periods(conn)
    cutoff_7 = (date.today() - timedelta(days=6)).isoformat()
    cutoff_30 = (date.today() - timedelta(days=29)).isoformat()
    last_90_days = financial["last_90_days"]
    last_7_days = [row for row in last_90_days if row["period"] >= cutoff_7]
    last_30_days = [row for row in last_90_days if row["period"] >= cutoff_30]

    # top selling items (all time)
    cur.execute("""
        SELECT ri.name,
               SUM(ri.qty)           as total_qty,
               SUM(ri.qty * ri.price) as total_revenue,
               SUM(ri.qty * ri.cost)  as total_cost
        FROM receipt_items ri
        JOIN receipts r ON r.id = ri.receipt_id
        WHERE r.status IS NULL OR r.status = 'paid'
        GROUP BY ri.name
        ORDER BY total_qty DESC
        LIMIT 10
    """)
    top_items = [row_to_dict(r) for r in cur.fetchall()]

    # hourly distribution (peak hours)
    cur.execute("""
        SELECT CAST(strftime('%H', COALESCE(income_date, date)) AS INTEGER) as hour,
               COUNT(*) as orders
        FROM receipts
        WHERE COALESCE(income_date, date) >= DATE('now', '-30 days')
          AND (status IS NULL OR status = 'paid')
        GROUP BY hour
        ORDER BY hour ASC
    """)
    hourly = [row_to_dict(r) for r in cur.fetchall()]

    # category revenue
    cur.execute("""
        SELECT i.category,
               SUM(ri.qty * ri.price) as revenue
        FROM receipt_items ri
        JOIN receipts r ON r.id = ri.receipt_id
        JOIN items i ON i.id = ri.item_id
        WHERE r.status IS NULL OR r.status = 'paid'
        GROUP BY i.category
        ORDER BY revenue DESC
    """)
    by_category = [row_to_dict(r) for r in cur.fetchall()]

    db.collection("cafe").document("analytics").set(
        wrap_doc(
            "analytics",
            {
                "last_7_days": last_7_days,
                "last_30_days": last_30_days,
                "last_90_days": last_90_days,
                "monthly": financial["monthly"],
                "yearly": financial["yearly"],
                "top_items": top_items,
                "hourly": hourly,
                "by_category": by_category,
            },
            [
                {"title": "المبيعات اليومية", "type": "chart", "key": "last_7_days"},
                {"title": "الأصناف الأفضل", "type": "cards", "key": "top_items", "primary_label": "name", "fields": ["total_qty", "total_revenue", "total_cost"]},
            ]
        )
    )


# =====================================================
# SYNC: INGREDIENTS
# =====================================================
def sync_ingredients(conn, db):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, quantity, cost
        FROM ingredients
        ORDER BY name
    """)
    ingredients = [row_to_dict(r) for r in cur.fetchall()]

    db.collection("cafe").document("ingredients").set(
        wrap_doc(
            "ingredients",
            {"list": ingredients},
            [
                {"title": "المكونات", "type": "cards", "key": "list", "primary_label": "name", "fields": ["quantity", "cost"]},
            ]
        )
    )

# =====================================================
# WORKERS SYNC
# =====================================================
def sync_workers(conn, db):
    cur = conn.cursor()

    cur.execute("SELECT * FROM workers")
    workers = cur.fetchall()

    for worker in workers:
        worker_id = worker[0]
        doc_ref = db.collection('workers').document(str(worker_id))

        doc_ref.set({
            'name': worker[1],
            'active': bool(worker[2]),
            'rating': worker[3] if len(worker) > 3 else 0,
            'total_ratings': worker[4] if len(worker) > 4 else 0,
            'created_at': worker[5] if len(worker) > 5 else datetime.now().isoformat(),
            'schema_version': SCHEMA_VERSION,
            'entity': 'worker',
            'ui_sections': [
                {'title': 'البيانات الأساسية', 'type': 'details', 'fields': ['name', 'active']},
                {'title': 'التقييم', 'type': 'stats', 'fields': ['rating', 'total_ratings']},
            ],
            'last_updated': datetime.now().isoformat(),
        }, merge=True)


def sync_shift_schedules(conn, db):
    cur = conn.cursor()

    cur.execute("SELECT * FROM shift_schedules")
    schedules = cur.fetchall()

    for schedule in schedules:
        schedule_id = schedule[0]
        doc_ref = db.collection('shift_schedules').document(str(schedule_id))

        doc_ref.set({
            'name': schedule[1],
            'shift_type': schedule[2],
            'start_hour': schedule[3],
            'end_hour': schedule[4],
            'allowed_workers': schedule[5],
            'is_active': bool(schedule[6]),
            'created_at': schedule[7] if len(schedule) > 7 else datetime.now().isoformat(),
            'updated_at': schedule[8] if len(schedule) > 8 else datetime.now().isoformat(),
            'schema_version': SCHEMA_VERSION,
            'entity': 'shift_schedule',
            'ui_sections': [
                {'title': 'الجدول', 'type': 'details', 'fields': ['name', 'shift_type', 'start_hour', 'end_hour', 'is_active']},
                {'title': 'الصلاحيات', 'type': 'details', 'fields': ['allowed_workers']},
            ],
            'last_updated': datetime.now().isoformat(),
        }, merge=True)


def sync_shift_sessions(conn, db):
    cur = conn.cursor()

    cur.execute("""
        SELECT ss.id, ss.schedule_id, ss.worker_id, ss.date,
               ss.start_time, ss.end_time, ss.status,
               ss.total_sales, ss.total_revenue,
               ss.created_at, ss.updated_at,
               w.name AS opened_by_worker_name,
               s.name AS schedule_name
        FROM shift_sessions ss
        LEFT JOIN workers w ON ss.worker_id = w.id
        LEFT JOIN shift_schedules s ON ss.schedule_id = s.id
    """)
    sessions = cur.fetchall()

    for session in sessions:
        session_id = session["id"]
        cur.execute("""
            SELECT w.id AS worker_id, w.name AS worker_name,
                   COUNT(DISTINCT r.id) AS receipts,
                   COALESCE(SUM(ri.qty), 0) AS items,
                   COALESCE(SUM(ri.qty * ri.price), 0) AS revenue
            FROM shift_workers sw
            JOIN workers w ON w.id = sw.worker_id
            LEFT JOIN receipts r
              ON r.session_id = sw.session_id AND r.worker_id = sw.worker_id
            LEFT JOIN receipt_items ri ON ri.receipt_id = r.id
            WHERE sw.session_id = ?
            GROUP BY w.id, w.name
            ORDER BY w.name
        """, (session_id,))
        worker_sales = [row_to_dict(row) for row in cur.fetchall()]
        doc_ref = db.collection('shift_sessions').document(str(session_id))

        doc_ref.set({
            'schedule_id': str(session["schedule_id"]),
            'schedule_name': session["schedule_name"] or '',
            # Kept for compatibility: this is the worker who opened the shift.
            'worker_id': str(session["worker_id"]),
            'worker_name': session["opened_by_worker_name"] or '',
            'workers': worker_sales,
            'date': session["date"],
            'start_time': session["start_time"],
            'end_time': session["end_time"],
            'status': session["status"],
            'total_sales': session["total_sales"] or 0,
            'total_revenue': session["total_revenue"] or 0,
            'created_at': session["created_at"],
            'updated_at': session["updated_at"] or datetime.now().isoformat(),
            'schema_version': SCHEMA_VERSION,
            'entity': 'shift_session',
            'ui_sections': [
                {'title': 'الجلسة', 'type': 'details', 'fields': ['schedule_name', 'worker_name', 'date', 'status']},
                {'title': 'العمال', 'type': 'cards', 'key': 'workers', 'primary_label': 'worker_name', 'fields': ['receipts', 'items', 'revenue']},
                {'title': 'الأرقام', 'type': 'stats', 'fields': ['total_sales', 'total_revenue']},
            ],
            'last_updated': datetime.now().isoformat(),
        }, merge=True)


def sync_worker_ratings(conn, db):
    cur = conn.cursor()

    cur.execute("""
        SELECT wr.*, w.name as worker_name
        FROM worker_ratings wr
        LEFT JOIN workers w ON wr.worker_id = w.id
    """)
    ratings = cur.fetchall()

    for rating in ratings:
        rating_id = rating[0]
        doc_ref = db.collection('worker_ratings').document(str(rating_id))

        doc_ref.set({
            'worker_id': str(rating[1]),
            'worker_name': rating[7] if len(rating) > 7 else '',
            'session_id': str(rating[2]) if rating[2] else None,
            'rating': rating[3],
            'notes': rating[4],
            'created_by': rating[5],
            'created_at': rating[6],
            'schema_version': SCHEMA_VERSION,
            'entity': 'worker_rating',
            'ui_sections': [
                {'title': 'التقييم', 'type': 'details', 'fields': ['worker_name', 'rating', 'created_by', 'notes']},
            ],
            'last_updated': datetime.now().isoformat(),
        }, merge=True)


def sync_worker_sessions(conn, db):
    """Sync permanent per-worker daily logs (the replacement for shifts)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT ws.*, w.name AS worker_name
        FROM worker_sessions ws
        JOIN workers w ON w.id = ws.worker_id
        ORDER BY ws.work_date DESC, ws.id DESC
    """)
    for session in cur.fetchall():
        session_id = session["id"]
        cur.execute("""
            SELECT COUNT(*) AS receipts,
                   COALESCE(SUM(CASE WHEN status IS NULL OR status = 'paid' THEN total ELSE 0 END), 0) AS revenue,
                   COALESCE(SUM(CASE WHEN status IN ('debt', 'partial') THEN total ELSE 0 END), 0) AS held_revenue
            FROM receipts
            WHERE worker_session_id = ?
        """, (session_id,))
        totals = row_to_dict(cur.fetchone())
        cur.execute("""
            SELECT COALESCE(SUM(ri.qty), 0) AS items
            FROM receipts r
            JOIN receipt_items ri ON ri.receipt_id = r.id
            WHERE r.worker_session_id = ?
        """, (session_id,))
        totals.update(row_to_dict(cur.fetchone()))
        db.collection("worker_sessions").document(str(session_id)).set({
            "worker_id": str(session["worker_id"]),
            "worker_name": session["worker_name"],
            "work_date": session["work_date"],
            "start_time": session["start_time"],
            "end_time": session["end_time"],
            "status": session["status"],
            **totals,
            "schema_version": SCHEMA_VERSION,
            "entity": "worker_session",
            "ui_sections": [
                {"title": "اليوم", "type": "details", "fields": ["worker_name", "work_date", "start_time", "end_time", "status"]},
                {"title": "العمل", "type": "stats", "fields": ["receipts", "items", "revenue", "held_revenue"]},
            ],
            "last_updated": datetime.now().isoformat(),
        }, merge=True)


def publish_sync_health(db, conn, status='online', error=None):
    """Publish a heartbeat consumed by the Arabic mobile status indicator."""
    pending_count = 0
    failed_count = 0
    for collection in (
        'mobile_inventory_requests',
        'mobile_receipt_requests',
        'mobile_expense_requests',
    ):
        pending_count += len(
            db.collection(collection).where('status', '==', 'pending').get())
        failed_count += len(
            db.collection(collection).where('status', '==', 'error').get())

    local_pending = conn.execute(
        "SELECT COUNT(*) FROM sync_queue WHERE status='pending'"
    ).fetchone()[0]
    db.collection('cafe').document('sync_health').set({
        'status': status,
        'last_seen': datetime.now().isoformat(),
        'pending_count': pending_count,
        'failed_count': failed_count,
        'local_pending_count': local_pending,
        'error_message_ar': str(error) if error else None,
        'schema_version': SCHEMA_VERSION,
    }, merge=True)


# =====================================================
# MAIN SYNC LOOP
# =====================================================
def main():
    print("=" * 55)
    print("  CafeRoom Firebase Sync")
    print("=" * 55)
    print(f"  DB   : {DB_PATH}")
    print(f"  Key  : {KEY_PATH}")
    print(f"  Sync : every {SYNC_INTERVAL}s")
    print("=" * 55)

    db   = init_firebase()
    conn = get_db()

    ensure_optional_tables()
    ensure_expenses_table(conn)
    ensure_sync_queue_and_triggers(conn)
    ensure_processed_mobile_requests(conn)

    prev_state = {}
    bootstrap_done = False

    if not bootstrap_done:
        try:
            initial_full_sync(conn, db, prev_state)
            publish_sync_health(db, conn)
            bootstrap_done = True
            print("[SYNC] Initial Firestore bootstrap completed")
        except Exception as exc:
            print(f"[SYNC] Initial bootstrap failed: {exc}")

    while True:
        try:
            did_work = False
            now = time.time()

            if "next_mobile_poll_at" not in prev_state or now >= prev_state["next_mobile_poll_at"]:
                did_work |= bool(import_mobile_inventory_requests(conn, db))
                did_work |= bool(import_mobile_receipt_requests(conn, db))
                did_work |= bool(import_mobile_expense_requests(conn, db))
                prev_state["next_mobile_poll_at"] = now + SYNC_INTERVAL

            did_work |= bool(process_pending_queue(conn, db, prev_state))

            if "next_health_at" not in prev_state or now >= prev_state["next_health_at"]:
                publish_sync_health(db, conn)
                prev_state["next_health_at"] = now + SYNC_INTERVAL

            if not did_work:
                time.sleep(1)

        except Exception as exc:
            conn.rollback()
            print(f"[ERROR]\n{traceback.format_exc()}")
            try:
                publish_sync_health(db, conn, status='error', error=exc)
            except Exception:
                pass


if __name__ == "__main__":
    main()
