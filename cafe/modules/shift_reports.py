import json
from pathlib import Path
from uuid import uuid4


def session_receipts(db, session_id, start, end):
    return db.execute("""
        SELECT id, date, total, COALESCE(status, 'paid')
        FROM receipts WHERE worker_session_id = ?
          AND datetime(date) BETWEEN datetime(?) AND datetime(?)
        ORDER BY date DESC, id DESC
    """, (session_id, start, end)).fetchall()


def session_sales(db, session_id, start, end):
    return db.execute("""
        SELECT r.id, r.date, ri.name, ri.qty, ri.price, COALESCE(r.status, 'paid')
        FROM receipts r JOIN receipt_items ri ON ri.receipt_id = r.id
        WHERE r.worker_session_id = ?
          AND datetime(r.date) BETWEEN datetime(?) AND datetime(?)
        ORDER BY r.date, r.id, ri.id
    """, (session_id, start, end)).fetchall()


def drinks_sold(db, session_id, start, end):
    return db.execute("""
        SELECT COALESCE(SUM(ri.qty), 0)
        FROM receipts r JOIN receipt_items ri ON ri.receipt_id = r.id
        JOIN items i ON i.id = ri.item_id
        WHERE r.worker_session_id = ?
          AND datetime(r.date) BETWEEN datetime(?) AND datetime(?)
          AND TRIM(i.category) IN ('مشروبات', 'مشاريب')
          AND COALESCE(r.status, 'paid') IN ('paid', 'debt')
    """, (session_id, start, end)).fetchone()[0]


def close_report(db, session_id, end, export_dir):
    """Stage the report in the same SQLite transaction as worker-session close."""
    from xlsxwriter import Workbook

    worker, start = db.execute("""
        SELECT w.name, s.start_time FROM worker_sessions s
        JOIN workers w ON w.id=s.worker_id WHERE s.id=?
    """, (session_id,)).fetchone()
    receipts = [list(row) for row in session_receipts(db, session_id, start, end)]
    rows = session_sales(db, session_id, start, end)
    sections = {
        'receipts': receipts,
        'sales': [[rid, date, name, qty, price, (qty or 0) * (price or 0)]
                  for rid, date, name, qty, price, _ in rows],
    }
    for key, table, stamp, fields in (
        ('expenses', 'expenses', 'created_at', 'created_at, category, amount, note'),
        ('waste', 'waste_log', 'logged_at', 'logged_at, item_name, quantity, reason'),
        ('debt_payments', 'debt_payments', 'paid_at', 'paid_at, debt_id, amount, note'),
    ):
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            sections[key] = [list(row) for row in db.execute(
                f'SELECT {fields} FROM {table} WHERE datetime({stamp}) BETWEEN datetime(?) AND datetime(?) ORDER BY {stamp}',
                (start, end))]

    key = uuid4().hex
    db.execute("""CREATE TABLE IF NOT EXISTS shift_report_outbox (
        id TEXT PRIMARY KEY, payload TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0
    )""")
    payload = dict(
        worker=worker, start=start, end=end,
        drinks=drinks_sold(db, session_id, start, end),
        receipt_count=len(receipts),
        paid_total=sum(total or 0 for _, _, total, status in receipts if status == 'paid'),
        debt_total=sum(total or 0 for _, _, total, status in receipts if status == 'debt'),
        sections=sections,
    )
    db.execute('INSERT INTO shift_report_outbox (id, payload) VALUES (?, ?)',
               (key, json.dumps(payload, ensure_ascii=False)))
    export_dir = Path(export_dir).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f'sales-{session_id}-{key[:8]}.xlsx'
    with Workbook(path, {'strings_to_formulas': False, 'strings_to_urls': False}) as workbook:
        sheet = workbook.add_worksheet('المبيعات')
        sheet.right_to_left()
        sheet.freeze_panes(1, 0)
        sheet.set_column('A:A', 13)
        sheet.set_column('B:B', 38)
        sheet.set_column('C:D', 18)
        header = workbook.add_format({'bold': True, 'bg_color': '#EFE3CE'})
        sheet.write_row(0, 0, ['الفاتورة', 'الصنف', 'الكمية', 'سعر الوحدة'], header)
        sold_lines = (row for row in rows if row[-1] in {'paid', 'debt'})
        for index, (rid, _, name, qty, price, _) in enumerate(sold_lines, 1):
            sheet.write_row(index, 0, [rid, name, qty, price])
    return path


def pending_reports(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='shift_report_outbox'").fetchone():
        return []
    return [(key, json.loads(payload)) for key, payload in db.execute(
        'SELECT id, payload FROM shift_report_outbox WHERE sent=0 ORDER BY rowid LIMIT 3')]
