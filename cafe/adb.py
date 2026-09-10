import sqlite3
from datetime import datetime

conn = sqlite3.connect("cafe.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=WAL")
cur.execute("PRAGMA synchronous=NORMAL")
cur.execute("PRAGMA temp_store=MEMORY")
cur.execute("PRAGMA cache_size=-20000")
_sync_triggers_log_printed = False

# ========================
# CATEGORIES
# ========================
def get_cur():
    return cur
def get_conn():
    return conn


def ensure_barcode_column():

    cur.execute("PRAGMA table_info(items)")
    cols = [c[1] for c in cur.fetchall()]

    if "barcode_value" not in cols:

        cur.execute("""
            ALTER TABLE items
            ADD COLUMN barcode_value TEXT
        """)

        conn.commit()

        print("barcode_value column added")

def ensure_shift_columns():
    """إضافة أعمدة نظام الورديات إلى جدول الفواتير"""
    cur.execute("PRAGMA table_info(receipts)")
    cols = [c[1] for c in cur.fetchall()]

    if 'worker_id' not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN worker_id INTEGER")
        print("worker_id column added to receipts")

    if 'session_id' not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN session_id INTEGER")
        print("session_id column added to receipts")

    if 'shift_type' not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN shift_type TEXT")
        print("shift_type column added to receipts")

    conn.commit()

def create_indexes():
    """إنشاء فهارس لتحسين الأداء"""
    indexes = [
        ("idx_receipts_worker", "receipts", "worker_id"),
        ("idx_receipts_worker_session", "receipts", "worker_session_id"),
        ("idx_receipts_status", "receipts", "status"),
        ("idx_receipts_income_date", "receipts", "income_date"),
        ("idx_receipts_date", "receipts", "date"),
        ("idx_receipt_items_receipt", "receipt_items", "receipt_id"),
        ("idx_receipt_items_item", "receipt_items", "item_id"),
        ("idx_receipt_items_name", "receipt_items", "name"),
        ("idx_items_category", "items", "category"),
        ("idx_items_name", "items", "name"),
        ("idx_items_category_name", "items", "category, name"),
        ("idx_items_barcode", "items", "barcode_value"),
        ("idx_item_ingredients_item", "item_ingredients", "item_id"),
        ("idx_item_ingredients_ingredient", "item_ingredients", "ingredient_id"),
        ("idx_debts_customer", "debts", "customer"),
        ("idx_worker_sessions_worker", "worker_sessions", "worker_id"),
        ("idx_worker_sessions_date", "worker_sessions", "work_date"),
        ("idx_worker_sessions_status", "worker_sessions", "status"),
    ]

    for idx_name, table, column in indexes:
        try:
            cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    print("Database indexes ready")


def _create_sync_trigger(table_name, operation, action=None, record_expression=None):
    trigger_name = f"trg_sync_{table_name}_{operation.lower()}"
    action_name = action or operation.lower()
    record_expression = record_expression or ("NEW.id" if operation != "DELETE" else "OLD.id")

    try:
        cur.execute(f"""
        CREATE TRIGGER IF NOT EXISTS {trigger_name}
        AFTER {operation} ON {table_name}
        BEGIN
            INSERT INTO sync_queue (table_name, record_id, action, status, created_at)
            VALUES ('{table_name}', {record_expression}, '{action_name}', 'pending', CURRENT_TIMESTAMP);
        END;
        """)
    except sqlite3.OperationalError:
        pass


def create_sync_triggers():
    global _sync_triggers_log_printed

    """إنشاء triggers لتجميع التغييرات وإرسالها إلى Firestore عند حدوثها."""
    trigger_tables = [
        "categories",
        "ingredients",
        "items",
        "item_ingredients",
        "receipts",
        "receipt_items",
        "debts",
        "debt_payments",
        "waste_log",
        "workers",
        "worker_ratings",
        "worker_sessions",
        "shift_schedules",
        "shift_sessions",
        "shift_workers",
        "shift_handover",
        "expenses",
    ]

    for table_name in trigger_tables:
        for operation in ("INSERT", "UPDATE", "DELETE"):
            _create_sync_trigger(table_name, operation)

    conn.commit()
    if not _sync_triggers_log_printed:
        print("Sync triggers ready")
        _sync_triggers_log_printed = True

def migrate_existing_receipts():
    """ترحيل الفواتير الموجودة لتعمل مع نظام الورديات الجديد"""
    cur.execute("SELECT COUNT(*) FROM workers")
    if cur.fetchone()[0] == 0:
        # إنشاء عامل افتراضي إذا لم يوجد
        cur.execute("INSERT INTO workers (name, active) VALUES ('عامل افتراضي', 1)")
        default_worker_id = cur.lastrowid
        print("Default worker created")
    else:
        cur.execute("SELECT id FROM workers LIMIT 1")
        default_worker_id = cur.fetchone()[0]

    # إنشاء جداول ورديات افتراضية إذا لم توجد
    morning_schedule_id, night_schedule_id = ensure_fixed_shift_schedules()
    if False:
        # إنشاء جدول وردية صباحية
        cur.execute("""
            INSERT INTO shift_schedules (name, shift_type, start_hour, end_hour, is_active)
            VALUES ('وردية صباحية', 'morning', 6, 14, 1)
        """)
        morning_schedule_id = cur.lastrowid

        # إنشاء جدول وردية ليلية
        cur.execute("""
            INSERT INTO shift_schedules (name, shift_type, start_hour, end_hour, is_active)
            VALUES ('وردية ليلية', 'night', 14, 22, 1)
        """)
        night_schedule_id = cur.lastrowid
        print("Default shift schedules created")
    else:
        cur.execute("SELECT id FROM shift_schedules WHERE shift_type='morning' LIMIT 1")
        morning = cur.fetchone()
        morning_schedule_id = morning[0] if morning else None

        cur.execute("SELECT id FROM shift_schedules WHERE shift_type='night' LIMIT 1")
        night = cur.fetchone()
        night_schedule_id = night[0] if night else None

    # تحديث الفواتير التي لا تحتوي على معلومات الوردية
    cur.execute("SELECT id, date FROM receipts WHERE worker_id IS NULL")
    existing_receipts = cur.fetchall()

    updated_count = 0
    for receipt_id, receipt_date in existing_receipts:
        try:
            dt = datetime.fromisoformat(receipt_date) if receipt_date else datetime.now()
            hour = dt.hour
            date_str = dt.date().isoformat()

            # تحديد نوع الوردية بناءً على الوقت
            if 6 <= hour < 16:
                shift_type = 'morning'
                schedule_id = morning_schedule_id
            else:
                shift_type = 'night'
                schedule_id = night_schedule_id  # افتراضي

            if not schedule_id:
                continue

            # البحث عن جلسة وردية موجودة أو إنشاء جديدة
            cur.execute("""
                SELECT id FROM shift_sessions
                WHERE schedule_id = ? AND date = ? AND status = 'active'
                ORDER BY id DESC LIMIT 1
            """, (schedule_id, date_str))
            session = cur.fetchone()

            if not session:
                cur.execute("""
                    INSERT INTO shift_sessions (schedule_id, worker_id, date, start_time, status)
                    VALUES (?, ?, ?, ?, 'completed')
                """, (schedule_id, default_worker_id, date_str, receipt_date or datetime.now().isoformat()))
                session_id = cur.lastrowid
            else:
                session_id = session[0]

            # تحديث الفاتورة
            cur.execute("""
                UPDATE receipts
                SET worker_id = ?, session_id = ?, shift_type = ?
                WHERE id = ?
            """, (default_worker_id, session_id, shift_type, receipt_id))
            updated_count += 1

        except Exception as e:
            print(f"خطأ في ترحيل الفاتورة {receipt_id}: {e}")

    if updated_count > 0:
        conn.commit()
        print(f"تم ترحيل {updated_count} فاتورة إلى نظام الورديات الجديد")

# =====================================================
# دوال العمال (Workers Functions)
# =====================================================
def get_all_workers():
    """الحصول على جميع العمال"""
    cur.execute("SELECT id, name, active FROM workers ORDER BY name")
    return cur.fetchall()

def create_worker(name):
    """إنشاء عامل جديد"""
    cur.execute("INSERT INTO workers (name, active) VALUES (?, 1)", (name,))
    conn.commit()
    return cur.lastrowid

def get_active_workers():
    """الحصول على العمال النشطين"""
    cur.execute("SELECT id, name FROM workers WHERE active = 1 ORDER BY name")
    return cur.fetchall()


# =====================================================
# DAILY WORKER SESSIONS (one permanent log per worker/day)
# =====================================================
def _worker_session_totals(session_id):
    cur.execute("SELECT COUNT(*) FROM receipts WHERE worker_session_id = ?", (session_id,))
    receipt_count = cur.fetchone()[0] or 0
    cur.execute("""
        SELECT COALESCE(SUM(ri.qty), 0)
        FROM receipts r
        JOIN receipt_items ri ON ri.receipt_id = r.id
        WHERE r.worker_session_id = ?
    """, (session_id,))
    item_quantity = cur.fetchone()[0] or 0
    cur.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN status IS NULL OR status = 'paid' THEN total ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN status IN ('debt', 'partial') THEN total ELSE 0 END), 0)
        FROM receipts
        WHERE worker_session_id = ?
    """, (session_id,))
    revenue, held_revenue = cur.fetchone()
    return {
        "receipts": receipt_count or 0,
        "items": item_quantity or 0,
        "revenue": revenue or 0,
        "held_revenue": held_revenue or 0,
    }


def get_worker_session_totals(session_id):
    return _worker_session_totals(session_id)


def close_stale_worker_sessions(now=None):
    """Complete active logs from older days; their history is never deleted."""
    now = now or datetime.now()
    today = now.date().isoformat()
    cur.execute("""
        SELECT id, work_date
        FROM worker_sessions
        WHERE status = 'active' AND work_date < ?
    """, (today,))
    stale = cur.fetchall()
    for session_id, work_date in stale:
        totals = _worker_session_totals(session_id)
        cur.execute("""
            UPDATE worker_sessions
            SET end_time = ?, status = 'completed', total_receipts = ?,
                total_items = ?, total_revenue = ?, held_revenue = ?, updated_at = ?
            WHERE id = ?
        """, (
            f"{work_date}T23:59:59", totals["receipts"], totals["items"],
            totals["revenue"], totals["held_revenue"], now.isoformat(), session_id,
        ))
    conn.commit()
    return len(stale)


def start_worker_session(worker_id, now=None):
    """Start or resume this worker's single log for the current calendar day."""
    now = now or datetime.now()
    close_stale_worker_sessions(now)
    work_date = now.date().isoformat()
    cur.execute("""
        SELECT id, start_time
        FROM worker_sessions
        WHERE worker_id = ? AND work_date = ?
        LIMIT 1
    """, (worker_id, work_date))
    existing = cur.fetchone()
    if existing:
        session_id, start_time = existing
        cur.execute("""
            UPDATE worker_sessions
            SET status = 'active', end_time = NULL, last_login_at = ?, updated_at = ?
            WHERE id = ?
        """, (now.isoformat(), now.isoformat(), session_id))
        conn.commit()
        return session_id, start_time, work_date

    cur.execute("""
        INSERT INTO worker_sessions (
            worker_id, work_date, start_time, last_login_at, status, updated_at
        ) VALUES (?, ?, ?, ?, 'active', ?)
    """, (worker_id, work_date, now.isoformat(), now.isoformat(), now.isoformat()))
    conn.commit()
    return cur.lastrowid, now.isoformat(), work_date


def end_worker_session(session_id, now=None):
    """Close today's worker log and persist its final totals."""
    now = now or datetime.now()
    totals = _worker_session_totals(session_id)
    cur.execute("""
        UPDATE worker_sessions
        SET end_time = ?, status = 'completed', total_receipts = ?,
            total_items = ?, total_revenue = ?, held_revenue = ?, updated_at = ?
        WHERE id = ?
    """, (
        now.isoformat(), totals["receipts"], totals["items"], totals["revenue"],
        totals["held_revenue"], now.isoformat(), session_id,
    ))
    conn.commit()
    return cur.rowcount > 0


def get_worker_logs(limit=200):
    """Return recent permanent daily logs with live totals."""
    close_stale_worker_sessions()
    cur.execute("""
        SELECT ws.id, ws.work_date, ws.start_time, ws.end_time, ws.status,
               w.id, w.name
        FROM worker_sessions ws
        JOIN workers w ON w.id = ws.worker_id
        ORDER BY ws.work_date DESC, w.name, ws.id DESC
        LIMIT ?
    """, (limit,))
    rows = []
    for session_id, work_date, start_time, end_time, status, worker_id, worker_name in cur.fetchall():
        rows.append({
            "id": session_id,
            "work_date": work_date,
            "start_time": start_time,
            "end_time": end_time,
            "status": status,
            "worker_id": worker_id,
            "worker_name": worker_name,
            **_worker_session_totals(session_id),
        })
    return rows


def record_debt_payment(debt_id, amount, note=None, paid_at=None):
    """Record a payment; linked sale income remains held until fully settled."""
    paid_at = paid_at or datetime.now().isoformat()
    cur.execute("SELECT amount, paid, receipt_id FROM debts WHERE id = ?", (debt_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError("Debt not found")
    debt_amount, already_paid, receipt_id = row
    remaining = debt_amount - already_paid
    if amount <= 0 or amount > remaining:
        raise ValueError("Invalid payment amount")

    cur.execute("UPDATE debts SET paid = paid + ? WHERE id = ?", (amount, debt_id))
    cur.execute("""
        INSERT INTO debt_payments (debt_id, amount, paid_at, note)
        VALUES (?, ?, ?, ?)
    """, (debt_id, amount, paid_at, note))
    fully_paid = already_paid + amount >= debt_amount
    if receipt_id:
        cur.execute("""
            UPDATE receipts
            SET status = ?, income_date = ?
            WHERE id = ?
        """, ("paid" if fully_paid else "partial", paid_at if fully_paid else None, receipt_id))
    conn.commit()
    return fully_paid

# =====================================================
# دوال جداول الورديات (Shift Schedules Functions)
# =====================================================
def get_all_schedules():
    """الحصول على جميع جداول الورديات"""
    cur.execute("""
        SELECT id, name, shift_type, start_hour, end_hour, is_active
        FROM shift_schedules
        WHERE is_active = 1
        ORDER BY start_hour
    """)
    return cur.fetchall()

def ensure_fixed_shift_schedules():
    """Keep only the required shift definitions active: 06-16 and 16-06."""
    fixed = {
        "morning": ("Morning shift", 6, 16),
        "night": ("Night shift", 16, 6),
    }
    ids = {}
    now = datetime.now().isoformat()

    for shift_type, (name, start_hour, end_hour) in fixed.items():
        cur.execute("""
            SELECT id
            FROM shift_schedules
            WHERE shift_type = ?
            ORDER BY id
            LIMIT 1
        """, (shift_type,))
        row = cur.fetchone()

        if row:
            schedule_id = row[0]
            cur.execute("""
                UPDATE shift_schedules
                SET name = ?, start_hour = ?, end_hour = ?, is_active = 1, updated_at = ?
                WHERE id = ?
            """, (name, start_hour, end_hour, now, schedule_id))
        else:
            cur.execute("""
                INSERT INTO shift_schedules (name, shift_type, start_hour, end_hour, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (name, shift_type, start_hour, end_hour))
            schedule_id = cur.lastrowid

        ids[shift_type] = schedule_id

    cur.execute("""
        UPDATE shift_schedules
        SET is_active = 0, updated_at = ?
        WHERE id NOT IN (?, ?)
    """, (now, ids["morning"], ids["night"]))
    conn.commit()
    return ids["morning"], ids["night"]


def ensure_worker_accounting_columns():
    """Add worker-day and cash-income fields without changing old receipts."""
    cur.execute("PRAGMA table_info(receipts)")
    cols = {c[1] for c in cur.fetchall()}
    additions = {
        "worker_id": "INTEGER",
        "worker_session_id": "INTEGER",
        "status": "TEXT DEFAULT 'paid'",
        "customer": "TEXT",
        "income_date": "TEXT",
    }
    for column, definition in additions.items():
        if column not in cols:
            cur.execute(f"ALTER TABLE receipts ADD COLUMN {column} {definition}")

    cur.execute("""
        UPDATE receipts
        SET income_date = date
        WHERE income_date IS NULL
          AND (status IS NULL OR status = 'paid')
    """)
    conn.commit()


def migrate_receipts_to_worker_days():
    """Backfill existing worker sales into permanent day logs without deleting history."""
    cur.execute("""
        SELECT worker_id, DATE(date), MIN(date), MAX(date)
        FROM receipts
        WHERE worker_id IS NOT NULL
          AND date IS NOT NULL
          AND worker_session_id IS NULL
        GROUP BY worker_id, DATE(date)
    """)
    groups = cur.fetchall()
    for worker_id, work_date, first_sale, last_sale in groups:
        if not work_date:
            continue
        cur.execute("""
            INSERT OR IGNORE INTO worker_sessions (
                worker_id, work_date, start_time, last_login_at, end_time, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'completed', ?)
        """, (worker_id, work_date, first_sale, last_sale, last_sale, datetime.now().isoformat()))
        cur.execute("""
            SELECT id FROM worker_sessions
            WHERE worker_id = ? AND work_date = ?
        """, (worker_id, work_date))
        session_id = cur.fetchone()[0]
        cur.execute("""
            UPDATE receipts
            SET worker_session_id = ?
            WHERE worker_id = ? AND DATE(date) = ? AND worker_session_id IS NULL
        """, (session_id, worker_id, work_date))
    conn.commit()
    return len(groups)

def create_schedule(name, shift_type, start_hour, end_hour, allowed_workers=None):
    """إنشاء جدول وردية جديد"""
    cur.execute("""
        INSERT INTO shift_schedules (name, shift_type, start_hour, end_hour, allowed_workers, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (name, shift_type, start_hour, end_hour, allowed_workers))
    conn.commit()
    return cur.lastrowid

def update_schedule(schedule_id, name=None, shift_type=None, start_hour=None, end_hour=None, allowed_workers=None, is_active=None):
    """تحديث جدول وردية"""
    updates = []
    params = []

    if name:
        updates.append("name = ?")
        params.append(name)
    if shift_type:
        updates.append("shift_type = ?")
        params.append(shift_type)
    if start_hour is not None:
        updates.append("start_hour = ?")
        params.append(start_hour)
    if end_hour is not None:
        updates.append("end_hour = ?")
        params.append(end_hour)
    if allowed_workers is not None:
        updates.append("allowed_workers = ?")
        params.append(allowed_workers)
    if is_active is not None:
        updates.append("is_active = ?")
        params.append(is_active)

    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(schedule_id)

        query = f"UPDATE shift_schedules SET {', '.join(updates)} WHERE id = ?"
        cur.execute(query, params)
        conn.commit()

def delete_schedule(schedule_id):
    """حذف جدول وردية"""
    cur.execute("DELETE FROM shift_schedules WHERE id = ?", (schedule_id,))
    conn.commit()

# =====================================================
# دوال جلسات الورديات (Shift Sessions Functions)
# =====================================================
def get_active_session():
    """الحصول على الجلسة النشطة"""
    cur.execute("""
        SELECT ss.id, ss.schedule_id, ss.worker_id, w.name,
               s.name as schedule_name, s.shift_type, ss.start_time, ss.date
        FROM shift_sessions ss
        JOIN workers w ON ss.worker_id = w.id
        JOIN shift_schedules s ON ss.schedule_id = s.id
        WHERE ss.status = 'active'
        ORDER BY ss.id DESC LIMIT 1
    """)
    return cur.fetchone()


def get_active_session_for_schedule(schedule_id):
    """Return the active shared shift for a schedule, if one exists."""
    cur.execute("""
        SELECT ss.id, ss.schedule_id, ss.worker_id, ss.start_time,
               s.name, s.shift_type
        FROM shift_sessions ss
        JOIN shift_schedules s ON ss.schedule_id = s.id
        WHERE ss.schedule_id = ? AND ss.status = 'active'
        ORDER BY ss.id DESC
        LIMIT 1
    """, (schedule_id,))
    return cur.fetchone()

def get_worker_active_session(worker_id):
    """Get an active shared shift previously joined by this worker."""

    cur.execute("""
        SELECT ss.id,
               ss.schedule_id,
               ss.worker_id,
               ss.start_time,
               s.name,
               s.shift_type
        FROM shift_sessions ss
        JOIN shift_workers sw
            ON sw.session_id = ss.id
        JOIN shift_schedules s
            ON ss.schedule_id = s.id
        WHERE sw.worker_id = ?
        AND ss.status = 'active'
        ORDER BY ss.id DESC
        LIMIT 1
    """, (worker_id,))

    return cur.fetchone()


def attach_worker_to_shift(session_id, worker_id):
    """Remember that a worker joined a shift without resetting prior sales."""
    current_time = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO shift_workers (
            session_id, worker_id, joined_at, last_joined_at
        ) VALUES (?, ?, ?, ?)
        ON CONFLICT(session_id, worker_id) DO UPDATE SET
            last_joined_at = excluded.last_joined_at
    """, (session_id, worker_id, current_time, current_time))
    conn.commit()


def get_shift_sales_totals(session_id, worker_id=None):
    """Return receipt count, item quantity, and revenue for a shift or worker."""
    params = [session_id]
    worker_filter = ""
    if worker_id is not None:
        worker_filter = " AND r.worker_id = ?"
        params.append(worker_id)

    cur.execute(f"""
        SELECT COUNT(DISTINCT r.id),
               COALESCE(SUM(ri.qty), 0),
               COALESCE(SUM(ri.qty * ri.price), 0)
        FROM receipts r
        LEFT JOIN receipt_items ri ON ri.receipt_id = r.id
        WHERE r.session_id = ?{worker_filter}
    """, params)
    receipt_count, item_quantity, revenue = cur.fetchone()
    return {
        "receipts": receipt_count or 0,
        "items": item_quantity or 0,
        "revenue": revenue or 0,
    }

def ensure_worker_columns():

    cur.execute("PRAGMA table_info(workers)")
    cols = [c[1] for c in cur.fetchall()]

    if "rating" not in cols:
        cur.execute("""
            ALTER TABLE workers
            ADD COLUMN rating REAL DEFAULT 0
        """)
        print("rating column added to workers")

    if "total_ratings" not in cols:
        cur.execute("""
            ALTER TABLE workers
            ADD COLUMN total_ratings INTEGER DEFAULT 0
        """)
        print("total_ratings column added to workers")

    conn.commit()

def start_shift_session(schedule_id, worker_id):
    """Join the schedule's active shared shift, or create it once."""

    existing = get_active_session_for_schedule(schedule_id)
    if existing:
        session_id = existing[0]
        attach_worker_to_shift(session_id, worker_id)
        return session_id

    date_str = datetime.now().date().isoformat()
    current_time = datetime.now().isoformat()

    cur.execute("""
        INSERT INTO shift_sessions (
            schedule_id,
            worker_id,
            date,
            start_time,
            status
        )
        VALUES (?, ?, ?, ?, 'active')
    """, (
        schedule_id,
        worker_id,
        date_str,
        current_time
    ))

    conn.commit()
    session_id = cur.lastrowid
    attach_worker_to_shift(session_id, worker_id)
    return session_id


def ensure_shift_worker_memberships():
    """Create/backfill the many-workers-to-one-shift relationship."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shift_workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            worker_id INTEGER NOT NULL,
            joined_at TEXT NOT NULL,
            last_joined_at TEXT NOT NULL,
            UNIQUE(session_id, worker_id),
            FOREIGN KEY(session_id) REFERENCES shift_sessions(id),
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
    """)

    # Every legacy shift at least contains the worker who originally opened it.
    cur.execute("""
        INSERT OR IGNORE INTO shift_workers (
            session_id, worker_id, joined_at, last_joined_at
        )
        SELECT id, worker_id, start_time, COALESCE(updated_at, start_time)
        FROM shift_sessions
        WHERE worker_id IS NOT NULL
    """)

    # Receipts are the source of truth for any additional legacy workers.
    cur.execute("""
        INSERT OR IGNORE INTO shift_workers (
            session_id, worker_id, joined_at, last_joined_at
        )
        SELECT r.session_id, r.worker_id, MIN(r.date), MAX(r.date)
        FROM receipts r
        WHERE r.session_id IS NOT NULL AND r.worker_id IS NOT NULL
        GROUP BY r.session_id, r.worker_id
    """)
    conn.commit()

def end_shift_session(session_id):
    """إنهاء جلسة وردية مع حساب التقييم الآلي"""
    cur.execute("SELECT status FROM shift_sessions WHERE id = ?", (session_id,))
    session_row = cur.fetchone()
    if not session_row or session_row[0] != "active":
        return False

    current_time = datetime.now().isoformat()

    # Persist all item quantities/revenue on the shared shift.
    shift_totals = get_shift_sales_totals(session_id)
    total_sales = shift_totals["items"]
    total_revenue = shift_totals["revenue"]

    cur.execute("""
        UPDATE shift_sessions
        SET end_time = ?, status = 'completed',
            total_sales = ?, total_revenue = ?, updated_at = ?
        WHERE id = ?
    """, (current_time, total_sales, total_revenue, current_time, session_id))
    conn.commit()

    # Rate each worker only from receipts attributed to that worker.
    cur.execute("""
        SELECT DISTINCT worker_id
        FROM receipts
        WHERE session_id = ? AND worker_id IS NOT NULL
    """, (session_id,))
    for worker_id, in cur.fetchall():
        try:
            calculate_automatic_worker_rating(session_id, worker_id)
            print(f"Automatic rating calculated for worker {worker_id} in session {session_id}")
        except Exception as e:
            print(f"Error calculating automatic rating: {e}")
    return True


def get_session_duration(session_id):
    """حساب مدة الجلسة بالثواني"""

    cur.execute("""
        SELECT start_time, end_time
        FROM shift_sessions
        WHERE id = ?
    """, (session_id,))

    row = cur.fetchone()

    if not row:
        return 0

    start_time, end_time = row

    if not end_time:
        end_time = datetime.now().isoformat()

    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)

    return int(
        (end_dt - start_dt).total_seconds()
    )

def get_sessions_by_date(date_str):
    """الحصول على جلسات يوم محدد"""
    cur.execute("""
        SELECT ss.id, ss.schedule_id, ss.worker_id,
               COALESCE(
                   (
                       SELECT GROUP_CONCAT(member_name, '، ')
                       FROM (
                           SELECT DISTINCT w2.name AS member_name
                           FROM shift_workers sw2
                           JOIN workers w2 ON w2.id = sw2.worker_id
                           WHERE sw2.session_id = ss.id
                           ORDER BY w2.name
                       )
                   ),
                   w.name
               ) AS worker_names,
               s.name as schedule_name, s.shift_type,
               ss.start_time, ss.end_time, ss.status, ss.total_sales, ss.total_revenue
        FROM shift_sessions ss
        JOIN workers w ON ss.worker_id = w.id
        JOIN shift_schedules s ON ss.schedule_id = s.id
        WHERE ss.date = ?
        ORDER BY ss.id
    """, (date_str,))
    return cur.fetchall()

def get_available_schedules_for_current_time():
    """الحصول على جداول الورديات المتاحة للوقت الحالي"""
    ensure_fixed_shift_schedules()
    current_hour = datetime.now().hour

    cur.execute("""
        SELECT id, name, shift_type, start_hour, end_hour, is_active
        FROM shift_schedules
        WHERE (
            is_active = 1
            AND (
                (start_hour < end_hour AND start_hour <= ? AND end_hour > ?)
                OR
                (start_hour > end_hour AND (start_hour <= ? OR end_hour > ?))
            )
        ) OR EXISTS (
            SELECT 1
            FROM shift_sessions ss
            WHERE ss.schedule_id = shift_schedules.id
              AND ss.status = 'active'
        )
        ORDER BY start_hour
    """, (current_hour, current_hour, current_hour, current_hour))
    return cur.fetchall()

def is_worker_allowed_in_schedule(worker_id, schedule_id):
    """التحقق من أن العامل مسموح له في جدول الوردية"""
    cur.execute("SELECT allowed_workers FROM shift_schedules WHERE id = ?", (schedule_id,))
    result = cur.fetchone()

    if not result or not result[0]:
        return True  # إذا لم يتم تحديد عمال، الجميع مسموح

    allowed = result[0].split(',') if result[0] else []
    return str(worker_id) in allowed


# =====================================================
# دوال تقييم العمال (Worker Rating Functions)
# =====================================================
def add_worker_rating(worker_id, rating, notes=None, session_id=None, created_by=None):
    """إضافة تقييم لعامل"""
    cur.execute("""
        INSERT INTO worker_ratings (worker_id, session_id, rating, notes, created_by)
        VALUES (?, ?, ?, ?, ?)
    """, (worker_id, session_id, rating, notes, created_by))
    conn.commit()

    # تحديث متوسط التقييم للعامل
    update_worker_average_rating(worker_id)
    return cur.lastrowid


def update_worker_average_rating(worker_id):
    """تحديث متوسط تقييم العامل"""
    cur.execute("""
        SELECT AVG(rating), COUNT(*)
        FROM worker_ratings
        WHERE worker_id = ?
    """, (worker_id,))
    avg_rating, count = cur.fetchone()

    if avg_rating:
        cur.execute("""
            UPDATE workers
            SET rating = ?, total_ratings = ?
            WHERE id = ?
        """, (avg_rating, count, worker_id))
        conn.commit()


def get_worker_ratings(worker_id):
    """الحصول على تقييمات عامل محدد"""
    cur.execute("""
        SELECT wr.id, wr.rating, wr.notes, wr.created_by, wr.created_at,
               ss.date, s.name as schedule_name
        FROM worker_ratings wr
        LEFT JOIN shift_sessions ss ON wr.session_id = ss.id
        LEFT JOIN shift_schedules s ON ss.schedule_id = s.id
        WHERE wr.worker_id = ?
        ORDER BY wr.created_at DESC
    """, (worker_id,))
    return cur.fetchall()


def get_all_workers_with_ratings():
    """الحصول على جميع العمال مع تقييماتهم"""
    cur.execute("""
        SELECT id, name, active, rating, total_ratings
        FROM workers
        ORDER BY rating DESC, name
    """)
    return cur.fetchall()


def get_worker_performance_stats(worker_id):
    """الحصول على إحصائيات أداء العامل"""
    cur.execute("SELECT COUNT(*) FROM worker_sessions WHERE worker_id = ?", (worker_id,))
    total_sessions = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(ri.qty), 0),
               COALESCE(SUM(CASE WHEN r.status IS NULL OR r.status = 'paid'
                                 THEN ri.qty * ri.price ELSE 0 END), 0)
        FROM receipts r
        LEFT JOIN receipt_items ri ON ri.receipt_id = r.id
        WHERE r.worker_id = ?
    """, (worker_id,))
    total_sales, total_revenue = cur.fetchone()

    # متوسط التقييم
    cur.execute("SELECT rating, total_ratings FROM workers WHERE id = ?", (worker_id,))
    rating_data = cur.fetchone()

    return {
        "total_sessions": total_sessions,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "average_rating": rating_data[0] if rating_data else 0,
        "total_ratings": rating_data[1] if rating_data else 0
    }


def calculate_automatic_worker_rating(session_id, worker_id=None):
    """حساب تقييم آلي للعامل بناءً على أداء الجلسة"""
    if worker_id is None:
        cur.execute("SELECT worker_id FROM shift_sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            return None
        worker_id = row[0]

    # Calculate only the selected worker's receipts inside the shared shift.
    cur.execute("""
        SELECT
            COALESCE(SUM(ri.qty), 0),
            COALESCE(SUM(ri.qty * ri.price), 0),
            COUNT(DISTINCT r.id),
            ss.start_time,
            ss.end_time
        FROM shift_sessions ss
        LEFT JOIN receipts r
          ON r.session_id = ss.id AND r.worker_id = ?
        LEFT JOIN receipt_items ri ON ri.receipt_id = r.id
        WHERE ss.id = ?
        GROUP BY ss.id
    """, (worker_id, session_id))
    session_data = cur.fetchone()

    if not session_data:
        return None

    total_sales, total_revenue, transaction_count, start_time, end_time = session_data

    # إذا لم تنته الجلسة بعد، لا تحسب التقييم
    if not end_time:
        return None

    # حساب المؤشرات
    rating_score = 0
    max_score = 100

    # 1. إجمالي المبيعات (30 نقطة كحد أقصى)
    # كل 10000 ليرة سورية = 10 نقاط
    sales_score = min(30, (total_revenue / 10000) * 10)
    rating_score += sales_score

    # 2. عدد المعاملات (25 نقطة كحد أقصى)
    # كل معاملة = 2.5 نقطة، بحد أقصى 10 معاملات
    transaction_score = min(25, transaction_count * 2.5)
    rating_score += transaction_score

    # 3. متوسط قيمة المعاملة (20 نقطة كحد أقصى)
    if transaction_count > 0:
        avg_transaction = total_revenue / transaction_count
        # المتوسط الأمثل بين 5000 و 20000
        if 5000 <= avg_transaction <= 20000:
            avg_score = 20
        elif avg_transaction > 20000:
            avg_score = 15
        elif avg_transaction >= 3000:
            avg_score = 10
        else:
            avg_score = 5
    else:
        avg_score = 0
    rating_score += avg_score

    # 4. الكفاءة الزمنية (25 نقطة كحد أقصى)
    # بناءً على مدة الجلسة وعدد المعاملات
    if transaction_count > 0:
        try:
            from datetime import datetime
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time)
            duration_hours = (end_dt - start_dt).total_seconds() / 3600

            if duration_hours > 0:
                transactions_per_hour = transaction_count / duration_hours
                # المثالي: أكثر من 10 معاملات في الساعة
                efficiency_score = min(25, (transactions_per_hour / 10) * 25)
                rating_score += efficiency_score
        except Exception:
            rating_score += 10  # نقاط افتراضية إذا فشل الحساب
    else:
        rating_score += 0

    # تحويل النتيجة إلى تقييم من 1 إلى 5
    if rating_score >= 80:
        star_rating = 5
    elif rating_score >= 65:
        star_rating = 4
    elif rating_score >= 50:
        star_rating = 3
    elif rating_score >= 35:
        star_rating = 2
    else:
        star_rating = 1

    # حفظ التقييم تلقائياً
    notes = f"تقييم آلي - درجة: {rating_score:.1f}/100 - مبيعات: {total_revenue:.0f}، معاملات: {transaction_count}"
    add_worker_rating(worker_id, star_rating, notes, session_id, created_by="النظام الآلي")

    return {
        "rating_score": rating_score,
        "star_rating": star_rating,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "transaction_count": transaction_count,
        "breakdown": {
            "sales_score": sales_score,
            "transaction_score": transaction_score,
            "avg_score": avg_score,
            "efficiency_score": rating_score - sales_score - transaction_score - avg_score
        }
    }

def init_db():
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    # ========================
    # INGREDIENTS
    # ========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        quantity REAL DEFAULT 0,
        cost REAL DEFAULT 0
    )
    """)

    # ========================
    # ITEMS
    # ========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        cost REAL DEFAULT 0,
        available BOOLEAN,
        type TEXT NOT NULL,   -- fixed | recipe
        stock INTEGER
    )
    """)

    # ========================
    # ITEM INGREDIENTS (M2M)
    # ========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS item_ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        ingredient_id INTEGER,
        qty REAL NOT NULL,

        FOREIGN KEY(item_id) REFERENCES items(id),
        FOREIGN KEY(ingredient_id) REFERENCES ingredients(id)
    )
    """)

    # ========================
    # RECEIPTS
    # ========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        total REAL,
        profit REAL,
        date TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ========================
    # RECEIPT ITEMS
    # ========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS receipt_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_id INTEGER,
        item_id INTEGER,
        name TEXT,
        qty REAL,
        price REAL,
        cost REAL,

        FOREIGN KEY(receipt_id) REFERENCES receipts(id),
        FOREIGN KEY(item_id) REFERENCES items(id)
    )
    """)
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
    cur.execute("""
CREATE TABLE IF NOT EXISTS sync_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT,
    record_id INTEGER,
    action TEXT,   -- insert | update | delete
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

    # ========================
    # WORKERS - العمال
    # ========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        active BOOLEAN DEFAULT 1,
        rating REAL DEFAULT 0,
        total_ratings INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # One permanent work log per worker per calendar day.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS worker_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER NOT NULL,
        work_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        last_login_at TEXT NOT NULL,
        end_time TEXT,
        status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed')),
        total_receipts INTEGER DEFAULT 0,
        total_items REAL DEFAULT 0,
        total_revenue REAL DEFAULT 0,
        held_revenue REAL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(worker_id, work_date),
        FOREIGN KEY(worker_id) REFERENCES workers(id)
    )
    """)

    # ========================
    # WORKER RATINGS - تقييمات العمال
    # ========================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS worker_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER NOT NULL,
        session_id INTEGER,
        rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
        notes TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(worker_id) REFERENCES workers(id),
        FOREIGN KEY(session_id) REFERENCES worker_sessions(id)
    )
    """)

    ensure_worker_accounting_columns()
    migrate_receipts_to_worker_days()
    ensure_barcode_column()
    ensure_worker_columns()
    create_indexes()
    create_sync_triggers()
    close_stale_worker_sessions()

    conn.commit()
    conn.commit()
