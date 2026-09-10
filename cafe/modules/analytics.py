from collections import defaultdict
from datetime import datetime, date

import customtkinter as ctk

from adb import cur
from utils import clear


def _money(value):
    return f"{value or 0:,.0f} ل.س"


def _number(value):
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.2f}"
    return f"{value or 0:,.0f}"


def _percent(value):
    return f"{value * 100:.1f}%"


def _safe_datetime(value):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _metric(parent, title, value, color="#fff8e8"):
    card = ctk.CTkFrame(parent, fg_color="#2f2517", corner_radius=10)
    card.pack(side="right", fill="both", expand=True, padx=5, pady=5)
    ctk.CTkLabel(card, text=title, text_color="#e8dcc0", font=("Tahoma", 13), anchor="e").pack(
        anchor="e", padx=12, pady=(10, 2)
    )
    ctk.CTkLabel(card, text=value, text_color=color, font=("Tahoma", 18, "bold"), anchor="e").pack(
        anchor="e", padx=12, pady=(0, 10)
    )
    return card


def _section(parent, title):
    frame = ctk.CTkFrame(parent, fg_color="#241c11", corner_radius=8)
    frame.pack(fill="x", padx=8, pady=8)
    ctk.CTkLabel(frame, text=title, font=("Tahoma", 20, "bold"), anchor="e").pack(
        anchor="e", padx=14, pady=(12, 8)
    )
    return frame


def _row(parent, values, colors=None, widths=None, height=40):
    colors = colors or {}
    widths = widths or [120] * len(values)
    row = ctk.CTkFrame(parent, fg_color="#2f2517", corner_radius=6, height=height)
    row.pack(fill="x", padx=10, pady=3)
    row.pack_propagate(False)
    for idx, value in enumerate(values):
        ctk.CTkLabel(
            row,
            text=str(value),
            text_color=colors.get(idx, "#fff8e8"),
            font=("Tahoma", 11, "bold" if idx == 0 else "normal"),
            anchor="e",
            justify="right",
            width=widths[idx] if idx < len(widths) else 120,
            wraplength=max((widths[idx] if idx < len(widths) else 120) - 12, 60),
        ).pack(side="right", padx=4)
    return row


def _header_row(parent, values):
    return _row(
        parent,
        values,
        colors={idx: "#e8dcc0" for idx in range(len(values))},
        height=30,
    )


def _load_receipt_summaries():
    cur.execute("PRAGMA table_info(receipts)")
    receipt_cols = {col[1] for col in cur.fetchall()}
    sale_date_expr = "COALESCE(r.date, r.time)" if "time" in receipt_cols else "r.date"
    date_expr = f"COALESCE(r.income_date, {sale_date_expr})" if "income_date" in receipt_cols else sale_date_expr
    cur.execute(
        f"""
        SELECT
            r.id,
            {date_expr},
            r.status,
            r.customer,
            r.worker_id,
            r.session_id,
            r.shift_type,
            COALESCE(SUM(ri.qty * ri.price), r.total, 0) AS revenue,
            COALESCE(SUM(ri.qty * COALESCE(ri.cost, i.cost, 0)), 0) AS cost,
            COALESCE(SUM(ri.qty), 0) AS qty,
            COUNT(ri.id) AS lines
        FROM receipts r
        LEFT JOIN receipt_items ri ON ri.receipt_id = r.id
        LEFT JOIN items i ON i.id = ri.item_id
        WHERE r.status IS NULL OR r.status = 'paid'
        GROUP BY r.id
        ORDER BY r.date DESC
        """
    )
    rows = []
    for row in cur.fetchall():
        (
            receipt_id,
            receipt_date,
            status,
            customer,
            worker_id,
            session_id,
            shift_type,
            revenue,
            cost,
            qty,
            lines,
        ) = row
        dt = _safe_datetime(receipt_date)
        if not dt:
            continue
        revenue = revenue or 0
        cost = cost or 0
        rows.append(
            {
                "id": receipt_id,
                "datetime": dt,
                "status": status or "paid",
                "customer": customer,
                "worker_id": worker_id,
                "session_id": session_id,
                "shift_type": shift_type,
                "revenue": revenue,
                "cost": cost,
                "profit": revenue - cost,
                "qty": qty or 0,
                "lines": lines or 0,
            }
        )
    return rows


def _load_product_stats():
    cur.execute(
        """
        SELECT
            COALESCE(ri.name, i.name) AS name,
            COALESCE(i.category, 'غير مصنف') AS category,
            SUM(ri.qty) AS qty,
            SUM(ri.qty * ri.price) AS revenue,
            SUM(ri.qty * COALESCE(ri.cost, i.cost, 0)) AS cost
        FROM receipt_items ri
        JOIN receipts r ON r.id = ri.receipt_id
        LEFT JOIN items i ON i.id = ri.item_id
        WHERE r.status IS NULL OR r.status = 'paid'
        GROUP BY COALESCE(ri.name, i.name), COALESCE(i.category, 'غير مصنف')
        ORDER BY revenue DESC
        """
    )
    stats = []
    for name, category, qty, revenue, cost in cur.fetchall():
        revenue = revenue or 0
        cost = cost or 0
        stats.append(
            {
                "name": name or "غير معروف",
                "category": category or "غير مصنف",
                "qty": qty or 0,
                "revenue": revenue,
                "cost": cost,
                "profit": revenue - cost,
            }
        )
    return stats


def _load_expenses():
    try:
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
        cur.execute("SELECT date, category, amount FROM expenses")
    except Exception:
        return []

    rows = []
    for expense_date, category, amount in cur.fetchall():
        dt = _safe_datetime(expense_date)
        if not dt:
            continue
        rows.append({
            "datetime": dt,
            "category": category or "أخرى",
            "amount": amount or 0,
        })
    return rows


def _load_shift_stats(receipts):
    receipt_by_session = defaultdict(
        lambda: {"revenue": 0, "cost": 0, "profit": 0, "receipts": 0, "qty": 0}
    )
    for receipt in receipts:
        key = receipt["session_id"]
        if not key:
            key = f"no-session-{receipt['shift_type'] or 'غير معروف'}-{receipt['datetime'].date()}"
        item = receipt_by_session[key]
        item["revenue"] += receipt["revenue"]
        item["cost"] += receipt["cost"]
        item["profit"] += receipt["profit"]
        item["receipts"] += 1
        item["qty"] += receipt["qty"]

    cur.execute(
        """
        SELECT
            ss.id,
            ss.date,
            ss.start_time,
            ss.end_time,
            ss.status,
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
            s.name,
            s.shift_type
        FROM shift_sessions ss
        LEFT JOIN workers w ON w.id = ss.worker_id
        LEFT JOIN shift_schedules s ON s.id = ss.schedule_id
        ORDER BY ss.date DESC, ss.id DESC
        """
    )
    sessions = {}
    for session_id, day, start_time, end_time, status, worker, schedule, shift_type in cur.fetchall():
        start_dt = _safe_datetime(start_time)
        end_dt = _safe_datetime(end_time) if end_time else datetime.now()
        hours = 0
        if start_dt and end_dt:
            hours = max((end_dt - start_dt).total_seconds() / 3600, 0)
        totals = receipt_by_session.pop(
            session_id,
            {"revenue": 0, "cost": 0, "profit": 0, "receipts": 0, "qty": 0},
        )
        sessions[session_id] = {
            "label": f"#{session_id} {schedule or shift_type or 'وردية'}",
            "day": day or "",
            "worker": worker or "غير معروف",
            "type": shift_type or "غير معروف",
            "status": status or "",
            "hours": hours,
            **totals,
        }

    synthetic = []
    for key, totals in receipt_by_session.items():
        synthetic.append(
            {
                "label": str(key).replace("no-session-", ""),
                "day": "",
                "worker": "بدون وردية",
                "type": "غير معروف",
                "status": "",
                "hours": 0,
                **totals,
            }
        )

    return list(sessions.values()) + synthetic


def _load_shift_stats_fast():
    cur.execute(
        """
        SELECT
            ss.id,
            ss.date,
            ss.start_time,
            ss.end_time,
            ss.status,
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
            s.name,
            s.shift_type,
            COALESCE(COUNT(DISTINCT r.id), 0) AS receipt_count,
            COALESCE(SUM(ri.qty), 0) AS qty,
            COALESCE(SUM(ri.qty * ri.price), 0) AS revenue,
            COALESCE(SUM(ri.qty * COALESCE(ri.cost, i.cost, 0)), 0) AS cost
        FROM shift_sessions ss
        LEFT JOIN workers w ON w.id = ss.worker_id
        LEFT JOIN shift_schedules s ON s.id = ss.schedule_id
        LEFT JOIN receipts r ON r.session_id = ss.id
        LEFT JOIN receipt_items ri ON ri.receipt_id = r.id
        LEFT JOIN items i ON i.id = ri.item_id
        GROUP BY ss.id
        ORDER BY ss.date DESC, ss.id DESC
        """
    )
    rows = []
    for session_id, day, start_time, end_time, status, worker, schedule, shift_type, receipt_count, qty, revenue, cost in cur.fetchall():
        start_dt = _safe_datetime(start_time)
        end_dt = _safe_datetime(end_time) if end_time else datetime.now()
        hours = max((end_dt - start_dt).total_seconds() / 3600, 0) if start_dt and end_dt else 0
        revenue = revenue or 0
        cost = cost or 0
        rows.append({
            "label": f"#{session_id} {schedule or shift_type or 'وردية'}",
            "day": day or "",
            "worker": worker or "غير معروف",
            "type": shift_type or "غير معروف",
            "status": status or "",
            "hours": hours,
            "revenue": revenue,
            "cost": cost,
            "profit": revenue - cost,
            "receipts": receipt_count or 0,
            "qty": qty or 0,
        })

    cur.execute(
        """
        SELECT
            COALESCE(r.shift_type, 'unknown') || '-' || DATE(r.date) AS label,
            DATE(r.date) AS day,
            COALESCE(r.shift_type, 'unknown') AS shift_type,
            COUNT(DISTINCT r.id) AS receipt_count,
            COALESCE(SUM(ri.qty), 0) AS qty,
            COALESCE(SUM(ri.qty * ri.price), 0) AS revenue,
            COALESCE(SUM(ri.qty * COALESCE(ri.cost, i.cost, 0)), 0) AS cost
        FROM receipts r
        LEFT JOIN receipt_items ri ON ri.receipt_id = r.id
        LEFT JOIN items i ON i.id = ri.item_id
        WHERE r.session_id IS NULL
        GROUP BY DATE(r.date), r.shift_type
        ORDER BY DATE(r.date) DESC
        """
    )
    for label, day, shift_type, receipt_count, qty, revenue, cost in cur.fetchall():
        revenue = revenue or 0
        cost = cost or 0
        rows.append({
            "label": label,
            "day": day or "",
            "worker": "بدون وردية",
            "type": shift_type or "غير معروف",
            "status": "",
            "hours": 0,
            "revenue": revenue,
            "cost": cost,
            "profit": revenue - cost,
            "receipts": receipt_count or 0,
            "qty": qty or 0,
        })

    return rows


def _load_worker_day_stats():
    """Daily worker logs: all work counts, but only received money is income."""
    cur.execute("""
        SELECT
            ws.id,
            ws.work_date,
            ws.start_time,
            ws.end_time,
            ws.status,
            w.name,
            (SELECT COUNT(*) FROM receipts r WHERE r.worker_session_id = ws.id) AS receipt_count,
            COALESCE((
                SELECT SUM(ri.qty)
                FROM receipts r
                JOIN receipt_items ri ON ri.receipt_id = r.id
                WHERE r.worker_session_id = ws.id
            ), 0) AS qty,
            COALESCE((
                SELECT SUM(r.total)
                FROM receipts r
                WHERE r.worker_session_id = ws.id
                  AND (r.status IS NULL OR r.status = 'paid')
            ), 0) AS revenue,
            COALESCE((
                SELECT SUM(ri.qty * COALESCE(ri.cost, i.cost, 0))
                FROM receipts r
                JOIN receipt_items ri ON ri.receipt_id = r.id
                LEFT JOIN items i ON i.id = ri.item_id
                WHERE r.worker_session_id = ws.id
                  AND (r.status IS NULL OR r.status = 'paid')
            ), 0) AS cost
        FROM worker_sessions ws
        JOIN workers w ON w.id = ws.worker_id
        ORDER BY ws.work_date DESC, w.name
    """)
    rows = []
    for session_id, day, start_time, end_time, status, worker, receipt_count, qty, revenue, cost in cur.fetchall():
        start_dt = _safe_datetime(start_time)
        end_dt = _safe_datetime(end_time) if end_time else datetime.now()
        hours = max((end_dt - start_dt).total_seconds() / 3600, 0) if start_dt and end_dt else 0
        rows.append({
            "label": f"سجل #{session_id}",
            "day": day or "",
            "worker": worker or "غير معروف",
            "type": "عمل يومي",
            "status": status or "",
            "hours": hours,
            "revenue": revenue or 0,
            "cost": cost or 0,
            "profit": (revenue or 0) - (cost or 0),
            "receipts": receipt_count or 0,
            "qty": qty or 0,
        })
    return rows


def _aggregate_by_period(receipts, period):
    data = defaultdict(lambda: {"revenue": 0, "cost": 0, "profit": 0, "receipts": 0, "qty": 0})
    for receipt in receipts:
        dt = receipt["datetime"]
        if period == "day":
            key = dt.date().isoformat()
        elif period == "month":
            key = dt.strftime("%Y-%m")
        else:
            key = dt.strftime("%Y")
        item = data[key]
        item["revenue"] += receipt["revenue"]
        item["cost"] += receipt["cost"]
        item["profit"] += receipt["profit"]
        item["receipts"] += 1
        item["qty"] += receipt["qty"]
    return sorted(data.items(), reverse=True)


def _aggregate_by_period_and_worker(receipts, period):
    worker_ids = sorted({r["worker_id"] for r in receipts if r["worker_id"]})
    names = {}
    if worker_ids:
        placeholders = ",".join("?" for _ in worker_ids)
        cur.execute(f"SELECT id, name FROM workers WHERE id IN ({placeholders})", worker_ids)
        names = {worker_id: name for worker_id, name in cur.fetchall()}

    grouped = defaultdict(lambda: defaultdict(lambda: {
        "revenue": 0, "cost": 0, "profit": 0, "receipts": 0, "qty": 0
    }))
    for receipt in receipts:
        dt = receipt["datetime"]
        if period == "day":
            period_key = dt.date().isoformat()
        elif period == "month":
            period_key = dt.strftime("%Y-%m")
        else:
            period_key = dt.strftime("%Y")
        worker_name = names.get(receipt["worker_id"], "بدون عامل")
        item = grouped[period_key][worker_name]
        for field in ("revenue", "cost", "profit", "qty"):
            item[field] += receipt[field]
        item["receipts"] += 1

    return {
        period_key: sorted(workers.items(), key=lambda row: row[1]["revenue"], reverse=True)
        for period_key, workers in grouped.items()
    }


def _aggregate_hourly(receipts):
    hourly = defaultdict(lambda: {"revenue": 0, "profit": 0, "receipts": 0})
    for receipt in receipts:
        key = receipt["datetime"].hour
        hourly[key]["revenue"] += receipt["revenue"]
        hourly[key]["profit"] += receipt["profit"]
        hourly[key]["receipts"] += 1
    return hourly


def _aggregate_by_worker(receipts):
    worker_ids = sorted({r["worker_id"] for r in receipts if r["worker_id"]})
    worker_names = {}
    if worker_ids:
        placeholders = ",".join("?" for _ in worker_ids)
        cur.execute(f"SELECT id, name FROM workers WHERE id IN ({placeholders})", worker_ids)
        worker_names = {worker_id: name for worker_id, name in cur.fetchall()}

    data = defaultdict(lambda: {"revenue": 0, "cost": 0, "profit": 0, "receipts": 0, "qty": 0})
    for receipt in receipts:
        key = receipt["worker_id"] or "no-worker"
        item = data[key]
        item["revenue"] += receipt["revenue"]
        item["cost"] += receipt["cost"]
        item["profit"] += receipt["profit"]
        item["receipts"] += 1
        item["qty"] += receipt["qty"]

    rows = []
    for worker_id, item in data.items():
        label = worker_names.get(worker_id, "بدون عامل")
        rows.append((label, item))
    return sorted(rows, key=lambda row: row[1]["profit"], reverse=True)


def show_analytics(main):
    clear(main)

    root = ctk.CTkFrame(main, fg_color="#15100a")
    root.pack(fill="both", expand=True)

    sidebar = ctk.CTkFrame(root, width=210, fg_color="#241c11", corner_radius=0)
    sidebar.pack(side="right", fill="y")
    sidebar.pack_propagate(False)

    content = ctk.CTkScrollableFrame(root, fg_color="#15100a")
    content.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    cache = {}

    def get_receipts():
        if "receipts" not in cache:
            cache["receipts"] = _load_receipt_summaries()
        return cache["receipts"]

    def get_products():
        if "products" not in cache:
            cache["products"] = _load_product_stats()
        return cache["products"]

    def get_expenses():
        if "expenses" not in cache:
            cache["expenses"] = _load_expenses()
        return cache["expenses"]

    def get_shifts():
        if "shifts" not in cache:
            cache["shifts"] = _load_worker_day_stats()
        return cache["shifts"]

    def get_period(period):
        key = f"period_{period}"
        if key not in cache:
            cache[key] = _aggregate_by_period(get_receipts(), period)
        return cache[key]

    def get_period_workers(period):
        key = f"period_workers_{period}"
        if key not in cache:
            cache[key] = _aggregate_by_period_and_worker(get_receipts(), period)
        return cache[key]

    def get_workers():
        if "workers" not in cache:
            cache["workers"] = _aggregate_by_worker(get_receipts())
        return cache["workers"]

    def get_hourly():
        if "hourly" not in cache:
            cache["hourly"] = _aggregate_hourly(get_receipts())
        return cache["hourly"]

    def get_overview_stats():
        if "overview_stats" in cache:
            return cache["overview_stats"]
        receipts = get_receipts()
        today = date.today()
        month_key = today.strftime("%Y-%m")
        today_receipts = [r for r in receipts if r["datetime"].date() == today]
        month_receipts = [r for r in receipts if r["datetime"].strftime("%Y-%m") == month_key]
        expenses = get_expenses()
        month_expenses = sum(e["amount"] for e in expenses if e["datetime"].strftime("%Y-%m") == month_key)
        total_revenue = sum(r["revenue"] for r in receipts)
        total_cost = sum(r["cost"] for r in receipts)
        gross_profit = sum(r["profit"] for r in receipts)
        total_receipts = len(receipts)
        cache["overview_stats"] = {
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "gross_profit": gross_profit,
            "month_expenses": month_expenses,
            "total_profit": gross_profit,
            "total_receipts": total_receipts,
            "avg_ticket": total_revenue / total_receipts if total_receipts else 0,
            "margin": gross_profit / total_revenue if total_revenue else 0,
            "today_profit": sum(r["profit"] for r in today_receipts),
            "month_profit": sum(r["profit"] for r in month_receipts),
        }
        return cache["overview_stats"]

    current_view = {"name": "overview"}
    monthly_expenses_active = {"value": False}
    selected_periods = {"day": None, "month": None, "year": None}

    ctk.CTkLabel(
        sidebar,
        text="التحليلات المتقدمة",
        font=("Tahoma", 22, "bold"),
        text_color="#fff8e8",
        anchor="e",
    ).pack(anchor="e", padx=16, pady=(18, 6))
    ctk.CTkLabel(
        sidebar,
        text="دخل كل عامل والمجموع حسب اليوم والشهر والسنة",
        text_color="#e8dcc0",
        font=("Tahoma", 12),
        anchor="e",
        wraplength=170,
    ).pack(anchor="e", padx=16, pady=(0, 14))

    def set_view(name):
        current_view["name"] = name
        render()

    nav_items = [
        ("نظرة عامة", "overview"),
        ("سجلات عمل العمال", "shifts"),
        ("الأرباح حسب اليوم", "days"),
        ("الأرباح حسب الشهر", "months"),
        ("الأرباح حسب السنة", "years"),
        ("الأرباح حسب العامل", "workers"),
        ("تحليل المنتجات", "products"),
        ("أوقات البيع", "patterns"),
    ]
    for label, name in nav_items:
        ctk.CTkButton(
            sidebar,
            text=label,
            anchor="e",
            height=38,
            fg_color="#3b2e1c",
            hover_color="#b8860b",
            command=lambda n=name: set_view(n),
        ).pack(fill="x", padx=12, pady=4)

    def render_kpis(parent):
        stats = get_overview_stats()
        kpi_row = ctk.CTkFrame(parent, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 6))
        _metric(kpi_row, "إجمالي الإيرادات", _money(stats["total_revenue"]), "#f5c400")
        _metric(kpi_row, "إجمالي الربح", _money(stats["total_profit"]), "#ded38d")
        _metric(kpi_row, "ربح المبيعات", _money(stats["gross_profit"]), "#ded38d")
        _metric(kpi_row, "هامش الربح", _percent(stats["margin"]), "#ffe27a")

        kpi_row_2 = ctk.CTkFrame(parent, fg_color="transparent")
        kpi_row_2.pack(fill="x", pady=(0, 6))
        _metric(kpi_row_2, "ربح اليوم", _money(stats["today_profit"]), "#f5c400")
        _metric(kpi_row_2, "ربح هذا الشهر", _money(stats["month_profit"]), "#ded38d")
        _metric(kpi_row_2, "متوسط الفاتورة", _money(stats["avg_ticket"]), "#fff8e8")

    def render_metric_row(parent, metrics):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 6))
        for title, value, color in metrics:
            _metric(row, title, value, color)

    def period_summary_metrics(data, label):
        latest_key, latest = data[0] if data else ("-", {"revenue": 0, "cost": 0, "profit": 0, "receipts": 0, "qty": 0})
        best_key, best = max(data, key=lambda row: row[1]["profit"]) if data else ("-", {"profit": 0})
        margin = latest["profit"] / latest["revenue"] if latest["revenue"] else 0
        return [
            (f"أحدث {label}", latest_key, "#fff8e8"),
            ("إيراد الفترة", _money(latest["revenue"]), "#f5c400"),
            ("ربح الفترة", _money(latest["profit"]), "#ded38d"),
            ("تكلفة الفترة", _money(latest["cost"]), "#ded38d"),
            ("هامش الفترة", _percent(margin), "#ffe27a"),
            (f"أفضل {label}", f"{best_key} | {_money(best['profit'])}", "#fff8e8"),
        ]

    def totals_from_rows(rows):
        revenue = sum(row.get("revenue", 0) for row in rows)
        cost = sum(row.get("cost", 0) for row in rows)
        profit = sum(row.get("profit", 0) for row in rows)
        receipts_count = sum(row.get("receipts", 0) for row in rows)
        qty = sum(row.get("qty", 0) for row in rows)
        return revenue, cost, profit, receipts_count, qty

    def render_overview():
        ctk.CTkLabel(content, text="نظرة عامة على العمل", font=("Tahoma", 26, "bold"), anchor="e").pack(
            anchor="e", padx=8, pady=(4, 12)
        )
        render_kpis(content)

        products = get_products()
        top_products = sorted(products, key=lambda x: x["profit"], reverse=True)[:8]
        top_section = _section(content, "أكثر المنتجات ربحاً")
        product_widths = [170, 80, 130, 130, 90]
        _row(top_section, ["المنتج", "الكمية", "الإيراد", "الربح", "الهامش"], colors={i: "#e8dcc0" for i in range(5)}, widths=product_widths, height=32)
        for item in top_products:
            item_margin = item["profit"] / item["revenue"] if item["revenue"] else 0
            _row(
                top_section,
                [
                    item["name"],
                    _number(item["qty"]),
                    _money(item["revenue"]),
                    _money(item["profit"]),
                    _percent(item_margin),
                ],
                colors={3: "#f5c400", 4: "#ded38d"},
                widths=product_widths,
            )

        category_totals = defaultdict(lambda: {"revenue": 0, "profit": 0, "qty": 0})
        for item in products:
            cat = category_totals[item["category"]]
            cat["revenue"] += item["revenue"]
            cat["profit"] += item["profit"]
            cat["qty"] += item["qty"]

        cat_section = _section(content, "أداء الفئات")
        category_widths = [170, 80, 130, 130, 90]
        _row(cat_section, ["الفئة", "الكمية", "الإيراد", "الربح", "النسبة"], colors={i: "#e8dcc0" for i in range(5)}, widths=category_widths, height=32)
        for category, data in sorted(category_totals.items(), key=lambda x: x[1]["profit"], reverse=True):
            overview_total_revenue = get_overview_stats()["total_revenue"]
            share = data["revenue"] / overview_total_revenue if overview_total_revenue else 0
            _row(
                cat_section,
                [category, _number(data["qty"]), _money(data["revenue"]), _money(data["profit"]), _percent(share)],
                colors={3: "#f5c400"},
                widths=category_widths,
            )

    def render_shift_table():
        ctk.CTkLabel(content, text="سجلات عمل العمال اليومية", font=("Tahoma", 26, "bold"), anchor="e").pack(
            anchor="e", padx=8, pady=(4, 12)
        )
        shifts = get_shifts()
        shift_revenue, shift_cost, shift_profit, shift_receipts, shift_qty = totals_from_rows(shifts)
        best_shift = max(shifts, key=lambda row: row["profit"]) if shifts else None
        render_metric_row(content, [
            ("عدد سجلات الأيام", _number(len(shifts)), "#fff8e8"),
            ("إجمالي الفواتير", _number(shift_receipts), "#fff8e8"),
            ("الدخل المستلم", _money(shift_revenue), "#f5c400"),
            ("إجمالي الربح", _money(shift_profit), "#ded38d"),
            ("أفضل سجل عامل", f"{best_shift['worker']} | {_money(best_shift['profit'])}" if best_shift else "-", "#ffe27a"),
        ])
        section = _section(content, "كل عامل في كل يوم")
        widths = [170, 100, 120, 80, 125, 125, 115]
        _row(section, ["السجل", "التاريخ", "العامل", "فواتير", "الدخل", "الربح", "ربح/ساعة"], colors={i: "#e8dcc0" for i in range(7)}, widths=widths, height=32)
        for shift in sorted(shifts, key=lambda x: (x["day"], x["profit"]), reverse=True):
            per_hour = shift["profit"] / shift["hours"] if shift["hours"] else 0
            _row(
                section,
                [
                    shift["label"],
                    shift["day"],
                    shift["worker"],
                    _number(shift["receipts"]),
                    _money(shift["revenue"]),
                    _money(shift["profit"]),
                    _money(per_hour),
                ],
                colors={5: "#f5c400", 6: "#ded38d"},
                widths=widths,
            )

    def render_period_table(title, data, worker_data, period_label, period_key):
        ctk.CTkLabel(content, text=title, font=("Tahoma", 26, "bold"), anchor="e").pack(
            anchor="e", padx=8, pady=(4, 12)
        )
        render_metric_row(content, period_summary_metrics(data, period_label))
        keys = [key for key, _item in data]
        selected = selected_periods.get(period_key)
        if selected not in keys:
            selected = keys[0] if keys else None
            selected_periods[period_key] = selected
        if keys:
            controls = ctk.CTkFrame(content, fg_color="transparent")
            controls.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(controls, text=f"اختر {period_label}", font=("Tahoma", 14, "bold")).pack(side="right", padx=8)
            ctk.CTkOptionMenu(
                controls,
                values=keys,
                variable=ctk.StringVar(value=selected),
                command=lambda value: (selected_periods.__setitem__(period_key, value), render()),
                width=180,
            ).pack(side="right", padx=8)
        for key, item in data:
            if key != selected:
                continue
            section = _section(content, f"{period_label}: {key}")
            widths = [140, 80, 80, 125, 125, 125, 90]
            _row(section, ["العامل", "فواتير", "عناصر", "الدخل", "التكلفة", "الربح", "الهامش"], colors={i: "#e8dcc0" for i in range(7)}, widths=widths, height=32)
            item_margin = item["profit"] / item["revenue"] if item["revenue"] else 0
            _row(
                section,
                [
                    "المجموع لكل العمال",
                    _number(item["receipts"]),
                    _number(item["qty"]),
                    _money(item["revenue"]),
                    _money(item["cost"]),
                    _money(item["profit"]),
                    _percent(item_margin),
                ],
                colors={0: "#f5c400", 5: "#f5c400", 6: "#ded38d"},
                widths=widths,
            )
            for worker_name, worker_item in worker_data.get(key, []):
                margin = worker_item["profit"] / worker_item["revenue"] if worker_item["revenue"] else 0
                _row(section, [
                    worker_name,
                    _number(worker_item["receipts"]),
                    _number(worker_item["qty"]),
                    _money(worker_item["revenue"]),
                    _money(worker_item["cost"]),
                    _money(worker_item["profit"]),
                    _percent(margin),
                ], colors={5: "#ded38d"}, widths=widths)

    def render_monthly_profit_table(title, data, worker_data):
        ctk.CTkLabel(content, text=title, font=("Tahoma", 26, "bold"), anchor="e").pack(
            anchor="e", padx=8, pady=(4, 12)
        )
        render_metric_row(content, period_summary_metrics(data, "شهر"))

        show_expenses = monthly_expenses_active["value"]
        controls = ctk.CTkFrame(content, fg_color="transparent")
        controls.pack(fill="x", pady=(0, 8))

        month_keys = [key for key, _item in data]
        selected_month = selected_periods.get("month")
        if selected_month not in month_keys:
            selected_month = month_keys[0] if month_keys else None
            selected_periods["month"] = selected_month
        if month_keys:
            ctk.CTkLabel(controls, text="اختر الشهر", font=("Tahoma", 14, "bold")).pack(side="right", padx=8)
            ctk.CTkOptionMenu(
                controls,
                values=month_keys,
                variable=ctk.StringVar(value=selected_month),
                command=lambda value: (selected_periods.__setitem__("month", value), render()),
                width=170,
            ).pack(side="right", padx=8)

        def toggle_month_expenses():
            monthly_expenses_active["value"] = not monthly_expenses_active["value"]
            render()

        ctk.CTkButton(
            controls,
            text="إخفاء مصروفات هذا الشهر" if show_expenses else "عرض مصروفات هذا الشهر",
            width=190,
            height=36,
            fg_color="#8a5a1f" if show_expenses else "#3b2e1c",
            hover_color="#a66c25",
            command=toggle_month_expenses,
        ).pack(side="right", padx=8)

        expenses_by_month = {}
        if show_expenses:
            for expense in get_expenses():
                month_key = expense["datetime"].strftime("%Y-%m")
                expenses_by_month[month_key] = expenses_by_month.get(month_key, 0) + expense["amount"]

            this_month = date.today().strftime("%Y-%m")
            this_month_profit = next((item["profit"] for key, item in data if key == this_month), 0)
            this_month_expenses = expenses_by_month.get(this_month, 0)
            render_metric_row(
                content,
                [
                    ("مصروفات هذا الشهر", _money(this_month_expenses), "#ffb36b"),
                    ("الربح النهائي لهذا الشهر", _money(this_month_profit - this_month_expenses), "#f5c400"),
                ],
            )

        for key, item in data:
            if key != selected_month:
                continue
            section = _section(content, f"الشهر: {key}")
            if show_expenses:
                widths = [135, 65, 65, 100, 100, 100, 100, 110, 75]
                headers = ["العامل", "فواتير", "عناصر", "الدخل", "التكلفة", "الربح", "المصروفات", "الربح النهائي", "الهامش"]
            else:
                widths = [140, 80, 80, 125, 125, 125, 90]
                headers = ["العامل", "فواتير", "عناصر", "الدخل", "التكلفة", "الربح", "الهامش"]
            _row(section, headers, colors={i: "#e8dcc0" for i in range(len(headers))}, widths=widths, height=32)
            item_margin = item["profit"] / item["revenue"] if item["revenue"] else 0
            if show_expenses:
                expense_amount = expenses_by_month.get(key, 0)
                final_profit = item["profit"] - expense_amount
                values = [
                    "المجموع لكل العمال",
                    _number(item["receipts"]),
                    _number(item["qty"]),
                    _money(item["revenue"]),
                    _money(item["cost"]),
                    _money(item["profit"]),
                    _money(expense_amount),
                    _money(final_profit),
                    _percent(item_margin),
                ]
                colors = {5: "#ded38d", 6: "#ffb36b", 7: "#f5c400", 8: "#ded38d"}
            else:
                values = [
                    "المجموع لكل العمال",
                    _number(item["receipts"]),
                    _number(item["qty"]),
                    _money(item["revenue"]),
                    _money(item["cost"]),
                    _money(item["profit"]),
                    _percent(item_margin),
                ]
                colors = {5: "#f5c400", 6: "#ded38d"}
            colors[0] = "#f5c400"
            _row(section, values, colors=colors, widths=widths)
            for worker_name, worker_item in worker_data.get(key, []):
                margin = worker_item["profit"] / worker_item["revenue"] if worker_item["revenue"] else 0
                if show_expenses:
                    worker_values = [worker_name, _number(worker_item["receipts"]), _number(worker_item["qty"]),
                                     _money(worker_item["revenue"]), _money(worker_item["cost"]),
                                     _money(worker_item["profit"]), "-", "-", _percent(margin)]
                else:
                    worker_values = [worker_name, _number(worker_item["receipts"]), _number(worker_item["qty"]),
                                     _money(worker_item["revenue"]), _money(worker_item["cost"]),
                                     _money(worker_item["profit"]), _percent(margin)]
                _row(section, worker_values, colors={5: "#ded38d"}, widths=widths)

    def render_products():
        ctk.CTkLabel(content, text="تحليل المنتجات", font=("Tahoma", 26, "bold"), anchor="e").pack(
            anchor="e", padx=8, pady=(4, 12)
        )
        products = get_products()
        section = _section(content, "كل المنتجات حسب الربح")
        widths = [160, 120, 75, 120, 120, 120, 80]
        _row(section, ["المنتج", "الفئة", "الكمية", "الإيراد", "التكلفة", "الربح", "الهامش"], colors={i: "#e8dcc0" for i in range(7)}, widths=widths, height=32)
        for item in sorted(products, key=lambda x: x["profit"], reverse=True):
            item_margin = item["profit"] / item["revenue"] if item["revenue"] else 0
            _row(
                section,
                [
                    item["name"],
                    item["category"],
                    _number(item["qty"]),
                    _money(item["revenue"]),
                    _money(item["cost"]),
                    _money(item["profit"]),
                    _percent(item_margin),
                ],
                colors={5: "#f5c400", 6: "#ded38d"},
                widths=widths,
            )

    def render_workers():
        ctk.CTkLabel(content, text="الأرباح حسب العامل", font=("Tahoma", 26, "bold"), anchor="e").pack(
            anchor="e", padx=8, pady=(4, 12)
        )
        workers = get_workers()
        worker_rows = [item for _worker_name, item in workers]
        worker_revenue, worker_cost, worker_profit, worker_receipts, worker_qty = totals_from_rows(worker_rows)
        best_worker = workers[0] if workers else None
        render_metric_row(content, [
            ("عدد العمال", _number(len(workers)), "#fff8e8"),
            ("فواتير العمال", _number(worker_receipts), "#fff8e8"),
            ("إيراد العمال", _money(worker_revenue), "#f5c400"),
            ("ربح العمال", _money(worker_profit), "#ded38d"),
            ("أفضل عامل", f"{best_worker[0]} | {_money(best_worker[1]['profit'])}" if best_worker else "-", "#ffe27a"),
        ])
        section = _section(content, "تقرير العمال")
        widths = [170, 80, 80, 125, 125, 125, 90]
        _row(section, ["العامل", "فواتير", "عناصر", "الإيراد", "التكلفة", "الربح", "الهامش"], colors={i: "#e8dcc0" for i in range(7)}, widths=widths, height=32)
        for worker_name, item in workers:
            item_margin = item["profit"] / item["revenue"] if item["revenue"] else 0
            _row(
                section,
                [
                    worker_name,
                    _number(item["receipts"]),
                    _number(item["qty"]),
                    _money(item["revenue"]),
                    _money(item["cost"]),
                    _money(item["profit"]),
                    _percent(item_margin),
                ],
                colors={5: "#f5c400", 6: "#ded38d"},
                widths=widths,
            )

    def render_patterns():
        ctk.CTkLabel(content, text="أوقات البيع", font=("Tahoma", 26, "bold"), anchor="e").pack(
            anchor="e", padx=8, pady=(4, 12)
        )
        section = _section(content, "الإيراد والربح حسب الساعة")
        hourly = get_hourly()
        max_revenue = max((v["revenue"] for v in hourly.values()), default=1)
        for hour in range(24):
            data = hourly.get(hour, {"revenue": 0, "profit": 0, "receipts": 0})
            row = ctk.CTkFrame(section, fg_color="#2f2517", corner_radius=6)
            row.pack(fill="x", padx=10, pady=4)
            ctk.CTkLabel(row, text=f"{hour:02}:00", width=58, anchor="e").pack(side="right", padx=8)
            bar = ctk.CTkProgressBar(row, width=220)
            bar.pack(side="right", fill="x", expand=True, padx=8)
            bar.set((data["revenue"] or 0) / max_revenue if max_revenue else 0)
            ctk.CTkLabel(
                row,
                text=f"{_number(data['receipts'])} فواتير | الإيراد {_money(data['revenue'])} | الربح {_money(data['profit'])}",
                text_color="#e8dcc0",
                anchor="e",
                justify="right",
            ).pack(side="right", fill="x", expand=True, padx=8)

    def render():
        clear(content)
        view = current_view["name"]
        if view == "overview":
            render_overview()
        elif view == "shifts":
            render_shift_table()
        elif view == "days":
            render_period_table("الدخل حسب اليوم والعامل", get_period("day"), get_period_workers("day"), "اليوم", "day")
        elif view == "months":
            render_monthly_profit_table("الدخل حسب الشهر والعامل", get_period("month"), get_period_workers("month"))
        elif view == "years":
            render_period_table("الدخل حسب السنة والعامل", get_period("year"), get_period_workers("year"), "السنة", "year")
        elif view == "workers":
            render_workers()
        elif view == "products":
            render_products()
        else:
            render_patterns()

    render()
