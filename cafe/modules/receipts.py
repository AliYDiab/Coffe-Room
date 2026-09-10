import customtkinter as ctk
from tkinter import messagebox
from adb import cur, conn
from utils import clear
from datetime import datetime, date
import calendar
import time
from threading import Thread

import state
from state import current_worker, current_session
from firebase_sync import (
    init_firebase,
    send_notification,
    suppress_notifications_since,
    sync_queue_watermark,
)


def load_product_options(search_text="", limit=80):
    search = search_text.strip()
    if search:
        cur.execute(
            """
            SELECT id, name, price, cost
            FROM items
            WHERE name LIKE ?
            ORDER BY name
            LIMIT ?
            """,
            (f"%{search}%", limit),
        )
    else:
        cur.execute(
            """
            SELECT id, name, price, cost
            FROM items
            ORDER BY name
            LIMIT ?
            """,
            (limit,),
        )
    return cur.fetchall()


def show_receipts(main, owner_mode=False):

    clear(main)

    root = ctk.CTkFrame(main)
    root.pack(fill="both", expand=True)

    # =========================
    # LEFT = CALENDAR
    # =========================
    left = ctk.CTkFrame(root, width=420)
    left.pack(side="left", fill="y", padx=10, pady=10)

    # =========================
    # RIGHT = CONTENT
    # =========================
    right = ctk.CTkFrame(root, fg_color="transparent")
    right.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    # =========================
    # LOAD RECEIPTS
    # =========================
    cur.execute("PRAGMA table_info(receipts)")
    receipt_cols = {col[1] for col in cur.fetchall()}

    if "worker_id" in receipt_cols:
        cur.execute("""
        SELECT r.id, r.date, r.total, COALESCE(w.name, '')
        FROM receipts r
        LEFT JOIN workers w ON w.id = r.worker_id
        ORDER BY r.date DESC
        """)
    else:
        cur.execute("""
        SELECT id, date, total, ''
        FROM receipts
        ORDER BY date DESC
        """)

    receipts = cur.fetchall()

    cur.execute("""
    SELECT receipt_id, COUNT(*)
    FROM receipt_items
    GROUP BY receipt_id
    """)
    receipt_item_counts = {rid: count for rid, count in cur.fetchall()}

    # =========================
    # MAP RECEIPTS BY DATE
    # =========================
    receipts_by_day = {}

    for r in receipts:

        rid, time_, total, worker_name = r

        d = datetime.fromisoformat(time_).date()

        if d not in receipts_by_day:
            receipts_by_day[d] = []

        receipts_by_day[d].append(r)

    # =========================
    # STATES
    # =========================
    today = date.today()

    current = {
        "month": today.month,
        "year": today.year
    }

    selected_day = {
        "value": today
    }

    mode = {
        "value": "receipts"
    }

    def refresh_receipt_cache():
        nonlocal receipts_by_day, receipt_item_counts

        if "worker_id" in receipt_cols:
            cur.execute("""
            SELECT r.id, r.date, r.total, COALESCE(w.name, '')
            FROM receipts r
            LEFT JOIN workers w ON w.id = r.worker_id
            ORDER BY r.date DESC
            """)
        else:
            cur.execute("""
            SELECT id, date, total, ''
            FROM receipts
            ORDER BY date DESC
            """)

        fresh_receipts = cur.fetchall()

        cur.execute("""
        SELECT receipt_id, COUNT(*)
        FROM receipt_items
        GROUP BY receipt_id
        """)
        receipt_item_counts = {rid: count for rid, count in cur.fetchall()}

        receipts_by_day = {}
        for r in fresh_receipts:
            rid, time_, total, worker_name = r
            try:
                d = datetime.fromisoformat(time_).date()
            except Exception:
                continue
            receipts_by_day.setdefault(d, []).append(r)

    def notify_worker_receipt_change(action, receipt_id, details=""):
        if owner_mode or state.app_mode != "worker" or not current_worker:
            return

        worker_id = current_worker.get("id")
        worker_name = current_worker.get("name", "Unknown worker")
        session_id = current_session.get("id") if current_session else None
        title = "Receipt changed by worker"
        body = f"{worker_name} {action} receipt #{receipt_id}"
        if details:
            body = f"{body}: {details}"

        def send_worker_notification():
            try:
                from firebase_admin import firestore

                db = init_firebase()
                send_notification(title, body, db=db)
                db.collection("worker_receipt_notifications").add({
                    "receipt_id": receipt_id,
                    "action": action,
                    "details": details,
                    "worker_id": worker_id,
                    "worker_name": worker_name,
                    "session_id": session_id,
                    "created_at": firestore.SERVER_TIMESTAMP,
                })
            except BaseException as exc:
                print(f"[NOTIF ERROR] Worker receipt notification failed: {exc}")

        Thread(target=send_worker_notification, daemon=True).start()

    def restore_receipt_item_stock(receipt_item_id):
        cur.execute("""
            SELECT item_id, name, qty
            FROM receipt_items
            WHERE id=?
        """, (receipt_item_id,))
        row = cur.fetchone()
        if not row:
            return

        item_id, item_name, qty = row
        if qty is None:
            return

        if item_id is not None:
            cur.execute("SELECT stock FROM items WHERE id=?", (item_id,))
            item_row = cur.fetchone()
            if item_row:
                if item_row[0] is None:
                    return
                cur.execute("""
                    UPDATE items
                    SET
                        stock = stock + ?,
                        available = 1
                    WHERE id=?
                """, (qty, item_id))
                return

        if item_name:
            cur.execute("""
                SELECT id
                FROM items
                WHERE name=? AND stock IS NOT NULL
                ORDER BY id
                LIMIT 1
            """, (item_name,))
            match = cur.fetchone()
            if match:
                cur.execute("""
                    UPDATE items
                    SET
                        stock = stock + ?,
                        available = 1
                    WHERE id=?
                """, (qty, match[0]))

    def restore_receipt_stock(receipt_id):
        cur.execute("""
            SELECT id
            FROM receipt_items
            WHERE receipt_id=?
        """, (receipt_id,))
        for (receipt_item_id,) in cur.fetchall():
            restore_receipt_item_stock(receipt_item_id)

    def show_item_receipts(item_name, item_id=None):
        win = ctk.CTkToplevel(main)
        win.geometry("760x620")
        win.title(f"Receipts for {item_name}")
        win.transient(main)
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))

        frame = ctk.CTkScrollableFrame(win)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            frame,
            text=f"الفواتير التي تحتوي: {item_name}",
            font=("Tahoma", 24, "bold"),
            anchor="e",
        ).pack(anchor="e", pady=(8, 12))

        if item_id is not None:
            item_filter_sql = "WHERE (ri.item_id = ? OR ri.name = ?)"
            item_filter_params = (item_id, item_name)
        else:
            item_filter_sql = "WHERE ri.name = ?"
            item_filter_params = (item_name,)

        cur.execute(
            f"""
            SELECT
                r.id,
                r.date,
                r.total,
                SUM(ri.qty) AS item_qty,
                SUM(ri.qty * ri.price) AS item_revenue,
                SUM(ri.qty * COALESCE(ri.cost, 0)) AS item_cost
            FROM receipt_items ri
            JOIN receipts r ON r.id = ri.receipt_id
            {item_filter_sql}
            GROUP BY r.id, r.date, r.total
            ORDER BY r.date DESC
            """,
            item_filter_params,
        )
        rows = cur.fetchall()

        if not rows:
            ctk.CTkLabel(
                frame,
                text="لا توجد فواتير لهذا العنصر",
                text_color="gray",
                font=("Tahoma", 16),
            ).pack(pady=35)
            return

        total_qty = sum(row[3] or 0 for row in rows)
        total_revenue = sum(row[4] or 0 for row in rows)
        total_profit = sum((row[4] or 0) - (row[5] or 0) for row in rows)
        today_value = date.today()
        day_count = 0
        month_count = 0
        year_count = 0
        for row in rows:
            try:
                receipt_day = datetime.fromisoformat(row[1]).date()
            except Exception:
                continue
            if receipt_day == today_value:
                day_count += 1
            if receipt_day.year == today_value.year and receipt_day.month == today_value.month:
                month_count += 1
            if receipt_day.year == today_value.year:
                year_count += 1

        summary = ctk.CTkFrame(frame, fg_color="#5a4316", corner_radius=12)
        summary.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            summary,
            text=f"عدد الفواتير: {len(rows)} | الكمية: {total_qty:g} | الإيراد: {total_revenue:.2f} SYP | الربح: {total_profit:.2f} SYP",
            font=("Tahoma", 15, "bold"),
            anchor="e",
        ).pack(anchor="e", padx=12, pady=12)

        count_summary = ctk.CTkFrame(frame, fg_color="#241c11", corner_radius=12)
        count_summary.pack(fill="x", pady=(0, 12))
        for label, value in (
            ("اليوم", day_count),
            ("هذا الشهر", month_count),
            ("هذه السنة", year_count),
        ):
            box = ctk.CTkFrame(count_summary, fg_color="#2f2517", corner_radius=10)
            box.pack(side="right", fill="x", expand=True, padx=6, pady=8)
            ctk.CTkLabel(
                box,
                text=label,
                text_color="#e8dcc0",
                font=("Tahoma", 13)
            ).pack(pady=(8, 0))
            ctk.CTkLabel(
                box,
                text=f"{value} فواتير",
                text_color="#f5c400",
                font=("Tahoma", 18, "bold")
            ).pack(pady=(2, 8))

        def open_receipt_from_list(receipt_id):
            show_receipt_details(receipt_id)

        for receipt_id, receipt_date, receipt_total, item_qty, item_revenue, item_cost in rows:
            try:
                dt = datetime.fromisoformat(receipt_date)
                display_date = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                display_date = receipt_date or ""

            item_profit = (item_revenue or 0) - (item_cost or 0)
            card = ctk.CTkFrame(frame, fg_color="#2f2517", corner_radius=12)
            card.pack(fill="x", pady=6)
            card.bind("<Button-1>", lambda _e, rid=receipt_id: open_receipt_from_list(rid))

            title = ctk.CTkLabel(
                card,
                text=f"فاتورة #{receipt_id} - {display_date}",
                font=("Tahoma", 17, "bold"),
                anchor="e",
            )
            title.pack(anchor="e", padx=14, pady=(10, 3))
            title.bind("<Button-1>", lambda _e, rid=receipt_id: open_receipt_from_list(rid))

            ctk.CTkLabel(
                card,
                text=f"كمية العنصر: {item_qty:g} | إيراد العنصر: {item_revenue or 0:.2f} SYP | ربح العنصر: {item_profit:.2f} SYP | إجمالي الفاتورة: {receipt_total or 0:.2f} SYP",
                text_color="#ded38d",
                anchor="e",
            ).pack(anchor="e", padx=14, pady=(0, 10))

    # =========================
    # ITEM QR / BARCODE SCANNER
    # =========================
    scan_buffer = {"chars": "", "timer": None, "started": None, "last": None}
    SCAN_TIMEOUT_MS = 80
    MIN_SCAN_LENGTH = 4
    MAX_SCAN_DURATION_MS = 1200
    MAX_KEY_GAP_MS = 120
    TEXT_WIDGET_CLASSES = {"Entry", "Text", "TEntry", "Spinbox"}

    def focused_text_input():
        try:
            focused = root.winfo_toplevel().focus_get()
            return focused is not None and focused.winfo_class() in TEXT_WIDGET_CLASSES
        except Exception:
            return False

    def resolve_scanned_item(code):
        scanned_code = code.strip()
        if scanned_code.upper().startswith("ITEM_ID:"):
            item_id_text = scanned_code.split(":", 1)[1].strip()
            if item_id_text.isdigit():
                cur.execute("SELECT id, name FROM items WHERE id=?", (int(item_id_text),))
                return cur.fetchone()

        cur.execute("SELECT id, name FROM items WHERE barcode_value=?", (scanned_code,))
        item = cur.fetchone()
        if item:
            return item

        if scanned_code.isdigit():
            cur.execute("SELECT id, name FROM items WHERE id=?", (int(scanned_code),))
            return cur.fetchone()

        return None

    def flush_scan():
        if scan_buffer["timer"] is not None:
            try:
                root.after_cancel(scan_buffer["timer"])
            except Exception:
                pass
        code = scan_buffer["chars"].strip()
        started = scan_buffer["started"]
        last = scan_buffer["last"]
        scan_buffer["chars"] = ""
        scan_buffer["timer"] = None
        scan_buffer["started"] = None
        scan_buffer["last"] = None
        if not code:
            return
        duration_ms = ((last or time.monotonic()) - (started or time.monotonic())) * 1000
        if len(code) < MIN_SCAN_LENGTH or duration_ms > MAX_SCAN_DURATION_MS:
            return

        item = resolve_scanned_item(code)
        if not item:
            print("Receipt item scan not found:", code)
            try:
                import winsound
                winsound.Beep(400, 120)
            except Exception:
                pass
            return

        item_id, item_name = item
        show_item_receipts(item_name, item_id)
        try:
            import winsound
            winsound.Beep(1200, 80)
        except Exception:
            pass

    def on_scan_key(event):
        if not root.winfo_exists() or focused_text_input():
            return
        if not event.char or not event.char.isprintable():
            return

        now = time.monotonic()
        if (
            scan_buffer["last"] is not None
            and (now - scan_buffer["last"]) * 1000 > MAX_KEY_GAP_MS
        ):
            scan_buffer["chars"] = ""
            scan_buffer["started"] = None

        if not scan_buffer["chars"]:
            scan_buffer["started"] = now

        scan_buffer["chars"] += event.char
        scan_buffer["last"] = now
        if scan_buffer["timer"] is not None:
            root.after_cancel(scan_buffer["timer"])
        scan_buffer["timer"] = root.after(SCAN_TIMEOUT_MS, flush_scan)

    def finish_scan_on_enter(event=None):
        if not root.winfo_exists() or focused_text_input():
            return
        if scan_buffer["chars"].strip():
            flush_scan()
            return "break"

    try:
        tk_root = root.winfo_toplevel()
        tk_root.bind("<Key>", on_scan_key)
        tk_root.bind("<Return>", finish_scan_on_enter)
        tk_root.bind("<KP_Enter>", finish_scan_on_enter)
    except Exception:
        print("Warning: Could not bind keyboard events for receipt item scanning")

        # =========================
    # RECEIPT DETAILS
    # =========================
    def show_receipt_details(rid):

        detail = ctk.CTkToplevel(main)
        detail.geometry("700x600")
        detail.title(f"فاتورة #{rid}")
        detail.transient(main)
        detail.lift()
        detail.focus_force()
        detail.attributes("-topmost", True)
        detail.after(200, lambda: detail.attributes("-topmost", False))
        
        frame = ctk.CTkScrollableFrame(detail)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        cur.execute("""
        SELECT date,total
        FROM receipts
        WHERE id=?
        """, (rid,))

        receipt = cur.fetchone()

        if not receipt:
            return

        def refresh_details():
            detail.destroy()
            show_receipt_details(rid)

        def recalculate_receipt_total():
            cur.execute(
                "SELECT COALESCE(SUM(qty * price), 0) FROM receipt_items WHERE receipt_id=?",
                (rid,)
            )
            new_total = cur.fetchone()[0] or 0
            cur.execute("UPDATE receipts SET total=? WHERE id=?", (new_total, rid))
            conn.commit()
            return new_total

        def delete_receipt():
            if not messagebox.askyesno("Confirm", f"Delete receipt #{rid}?", parent=detail):
                return
            notify_worker_receipt_change("deleted", rid)
            restore_receipt_stock(rid)
            cur.execute("DELETE FROM receipt_items WHERE receipt_id=?", (rid,))
            try:
                cur.execute("DELETE FROM debts WHERE receipt_id=?", (rid,))
            except Exception:
                pass
            cur.execute("DELETE FROM receipts WHERE id=?", (rid,))
            conn.commit()
            detail.destroy()
            show_receipts(main, owner_mode)

        def edit_receipt_item(receipt_item_id, current_qty, current_price):
            win = ctk.CTkToplevel(detail)
            win.title("Edit receipt item")
            win.geometry("320x240")
            win.transient(detail)
            win.grab_set()
            qty_entry = ctk.CTkEntry(win, placeholder_text="Quantity")
            qty_entry.insert(0, str(current_qty))
            qty_entry.pack(fill="x", padx=20, pady=(25, 10))
            price_entry = ctk.CTkEntry(win, placeholder_text="Price")
            price_entry.insert(0, str(current_price))
            price_entry.pack(fill="x", padx=20, pady=10)

            def save_item():
                try:
                    qty = float(qty_entry.get())
                    price = float(price_entry.get())
                    if qty <= 0 or price < 0:
                        raise ValueError
                except Exception:
                    messagebox.showwarning("Warning", "Enter valid quantity and price.", parent=win)
                    return
                cur.execute(
                    "UPDATE receipt_items SET qty=?, price=? WHERE id=?",
                    (qty, price, receipt_item_id)
                )
                recalculate_receipt_total()
                conn.commit()
                notify_worker_receipt_change(
                    "edited item in",
                    rid,
                    f"item row #{receipt_item_id}, qty {current_qty:g}->{qty:g}, price {current_price:g}->{price:g}"
                )
                win.destroy()
                refresh_details()

            ctk.CTkButton(win, text="Save", fg_color="#f5c400", command=save_item).pack(fill="x", padx=20, pady=10)
            text_color="#15100a",
            ctk.CTkButton(win, text="Cancel", fg_color="#b23b2e", command=win.destroy).pack(fill="x", padx=20)

        def remove_receipt_item(receipt_item_id):
            if not messagebox.askyesno("Confirm", "Remove this item from the receipt?", parent=detail):
                return
            restore_receipt_item_stock(receipt_item_id)
            cur.execute("DELETE FROM receipt_items WHERE id=?", (receipt_item_id,))
            recalculate_receipt_total()
            conn.commit()
            notify_worker_receipt_change("removed item from", rid, f"item row #{receipt_item_id}")
            refresh_details()

        def add_receipt_item():
            win = ctk.CTkToplevel(detail)
            win.title("Add receipt item")
            win.geometry("380x300")
            win.transient(detail)
            win.grab_set()
            products = load_product_options()
            if not products:
                ctk.CTkLabel(win, text="No items found").pack(pady=30)
                return
            product_labels = [f"{name} - {price:.0f}" for _, name, price, _ in products]
            product_by_label = {label: product for label, product in zip(product_labels, products)}
            product_var = ctk.StringVar(value=product_labels[0])
            search_var = ctk.StringVar()
            search_entry = ctk.CTkEntry(win, textvariable=search_var, placeholder_text="Search item")
            search_entry.pack(fill="x", padx=20, pady=(20, 8))
            product_menu = ctk.CTkOptionMenu(win, variable=product_var, values=product_labels)
            product_menu.pack(fill="x", padx=20, pady=(0, 10))
            qty_entry = ctk.CTkEntry(win, placeholder_text="Quantity")
            qty_entry.insert(0, "1")
            qty_entry.pack(fill="x", padx=20, pady=10)

            search_timer = {"id": None}

            def update_products(*args):
                nonlocal product_by_label
                if search_timer["id"] is not None:
                    win.after_cancel(search_timer["id"])

                def refresh_options():
                    nonlocal product_by_label
                    products_now = load_product_options(search_var.get())
                    labels_now = [f"{name} - {price:.0f}" for _, name, price, _ in products_now]
                    product_by_label = {label: product for label, product in zip(labels_now, products_now)}
                    if labels_now:
                        product_var.set(labels_now[0])
                        product_menu.configure(values=labels_now)
                    else:
                        product_var.set("")
                        product_menu.configure(values=[""])

                search_timer["id"] = win.after(180, refresh_options)

            search_var.trace_add("write", update_products)

            def save_new_item():
                try:
                    qty = float(qty_entry.get())
                    if qty <= 0:
                        raise ValueError
                except Exception:
                    messagebox.showwarning("Warning", "Enter a valid quantity.", parent=win)
                    return
                if product_var.get() not in product_by_label:
                    messagebox.showwarning("Warning", "Select an item.", parent=win)
                    return
                item_id, name, price, cost = product_by_label[product_var.get()]
                cur.execute(
                    "INSERT INTO receipt_items (receipt_id, item_id, name, qty, price, cost) VALUES (?, ?, ?, ?, ?, ?)",
                    (rid, item_id, name, qty, price, cost or 0)
                )
                recalculate_receipt_total()
                conn.commit()
                notify_worker_receipt_change("added item to", rid, f"{name} x{qty:g}")
                win.destroy()
                refresh_details()

            ctk.CTkButton(win, text="Add", fg_color="#f5c400", command=save_new_item).pack(fill="x", padx=20, pady=10)
            text_color="#15100a",
            ctk.CTkButton(win, text="Cancel", fg_color="#b23b2e", command=win.destroy).pack(fill="x", padx=20)

        time_, total = receipt
        dt = datetime.fromisoformat(time_)

        ctk.CTkLabel(
            frame,
            text=f"🧾 فاتورة #{rid}",
            font=("Tahoma", 28, "bold")
        ).pack(pady=(10,5))

        ctk.CTkLabel(
            frame,
            text=dt.strftime("%Y-%m-%d  %H:%M"),
            text_color="#e8dcc0",
            font=("Tahoma", 16)
        ).pack(pady=(0,15))

        owner_actions = ctk.CTkFrame(frame, fg_color="transparent")
        owner_actions.pack(fill="x", pady=(0, 15))
        ctk.CTkButton(
            owner_actions,
            text="+ Add Item",
            fg_color="#f5c400",
            text_color="#15100a",
            command=add_receipt_item
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            owner_actions,
            text="Delete Receipt",
            fg_color="#b23b2e",
            command=delete_receipt
        ).pack(side="left", padx=5)

        cur.execute("""
        SELECT id, name, qty, price
        FROM receipt_items
        WHERE receipt_id=?
        """, (rid,))

        items = cur.fetchall()

        for receipt_item_id, name, qty, price in items:

            subtotal = qty * price

            card = ctk.CTkFrame(
                frame,
                fg_color="#2f2517",
                corner_radius=15
            )
            card.pack(fill="x", pady=6)
            card.bind("<Button-1>", lambda e, n=name: show_item_receipts(n))

            name_label = ctk.CTkLabel(
                card,
                text=name,
                font=("Tahoma", 18, "bold")
            )
            name_label.pack(anchor="w", padx=15, pady=(10,0))
            name_label.bind("<Button-1>", lambda e, n=name: show_item_receipts(n))

            ctk.CTkLabel(
                card,
                text=f"الكمية: {qty}",
                font=("Tahoma", 15)
            ).pack(anchor="w", padx=15)

            ctk.CTkLabel(
                card,
                text=f"السعر: {price:.2f} SYP",
                text_color="#f5c400"
            ).pack(anchor="w", padx=15)

            ctk.CTkLabel(
                card,
                text=f"الإجمالي: {subtotal:.2f} SYP",
                text_color="#ded38d"
            ).pack(anchor="w", padx=15, pady=(0,10))

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", padx=15, pady=(0, 10))
            ctk.CTkButton(
                actions,
                text="Edit",
                width=90,
                command=lambda ri=receipt_item_id, q=qty, p=price: edit_receipt_item(ri, q, p)
            ).pack(side="left", padx=(0, 5))
            ctk.CTkButton(
                actions,
                text="Remove",
                width=90,
                fg_color="#b23b2e",
                command=lambda ri=receipt_item_id: remove_receipt_item(ri)
            ).pack(side="left", padx=5)

        total_card = ctk.CTkFrame(
            frame,
            fg_color="#5a4316",
            corner_radius=15
        )
        total_card.pack(fill="x", pady=15)

        ctk.CTkLabel(
            total_card,
            text=f"💰 المجموع النهائي: {total:.2f} SYP",
            font=("Tahoma", 24, "bold")
        ).pack(pady=20)

    def render_receipt_detail_panel(parent, rid, after_change):
        clear(parent)

        if not rid:
            ctk.CTkLabel(
                parent,
                text="اختر فاتورة لعرض التفاصيل",
                text_color="gray",
                font=("Tahoma", 18)
            ).pack(pady=50)
            return

        cur.execute("PRAGMA table_info(receipts)")
        receipt_cols = {col[1] for col in cur.fetchall()}
        if "worker_id" in receipt_cols:
            cur.execute("""
            SELECT r.date, r.total, COALESCE(w.name, '')
            FROM receipts r
            LEFT JOIN workers w ON w.id = r.worker_id
            WHERE r.id=?
            """, (rid,))
        else:
            cur.execute("SELECT date, total, '' FROM receipts WHERE id=?", (rid,))

        receipt = cur.fetchone()
        if not receipt:
            ctk.CTkLabel(parent, text="لم يتم العثور على الفاتورة", text_color="gray").pack(pady=40)
            return

        time_, total, worker_name = receipt

        def recalculate_receipt_total():
            cur.execute(
                "SELECT COALESCE(SUM(qty * price), 0) FROM receipt_items WHERE receipt_id=?",
                (rid,)
            )
            new_total = cur.fetchone()[0] or 0
            cur.execute("UPDATE receipts SET total=? WHERE id=?", (new_total, rid))
            conn.commit()
            return new_total

        def refresh_current():
            render_receipt_detail_panel(parent, rid, after_change)

        def delete_receipt():
            if not messagebox.askyesno("Confirm", f"Delete receipt #{rid}?", parent=parent):
                return
            notify_worker_receipt_change("deleted", rid)
            restore_receipt_stock(rid)
            cur.execute("DELETE FROM receipt_items WHERE receipt_id=?", (rid,))
            try:
                cur.execute("DELETE FROM debts WHERE receipt_id=?", (rid,))
            except Exception:
                pass
            cur.execute("DELETE FROM receipts WHERE id=?", (rid,))
            conn.commit()
            after_change(None)

        def edit_receipt_item(receipt_item_id, current_qty, current_price):
            win = ctk.CTkToplevel(parent)
            win.title("Edit receipt item")
            win.geometry("320x240")
            win.transient(parent.winfo_toplevel())
            win.grab_set()
            qty_entry = ctk.CTkEntry(win, placeholder_text="Quantity")
            qty_entry.insert(0, str(current_qty))
            qty_entry.pack(fill="x", padx=20, pady=(25, 10))
            price_entry = ctk.CTkEntry(win, placeholder_text="Price")
            price_entry.insert(0, str(current_price))
            price_entry.pack(fill="x", padx=20, pady=10)

            def save_item():
                try:
                    qty = float(qty_entry.get())
                    price = float(price_entry.get())
                    if qty <= 0 or price < 0:
                        raise ValueError
                except Exception:
                    messagebox.showwarning("Warning", "Enter valid quantity and price.", parent=win)
                    return
                cur.execute(
                    "UPDATE receipt_items SET qty=?, price=? WHERE id=?",
                    (qty, price, receipt_item_id)
                )
                recalculate_receipt_total()
                conn.commit()
                notify_worker_receipt_change(
                    "edited item in",
                    rid,
                    f"item row #{receipt_item_id}, qty {current_qty:g}->{qty:g}, price {current_price:g}->{price:g}"
                )
                win.destroy()
                after_change(rid)

            ctk.CTkButton(win, text="Save", fg_color="#f5c400", command=save_item).pack(fill="x", padx=20, pady=10)
            text_color="#15100a",
            ctk.CTkButton(win, text="Cancel", fg_color="#b23b2e", command=win.destroy).pack(fill="x", padx=20)

        def remove_receipt_item(receipt_item_id):
            if not messagebox.askyesno("Confirm", "Remove this item from the receipt?", parent=parent):
                return
            restore_receipt_item_stock(receipt_item_id)
            cur.execute("DELETE FROM receipt_items WHERE id=?", (receipt_item_id,))
            recalculate_receipt_total()
            conn.commit()
            notify_worker_receipt_change("removed item from", rid, f"item row #{receipt_item_id}")
            after_change(rid)

        def add_receipt_item():
            win = ctk.CTkToplevel(parent)
            win.title("Add receipt item")
            win.geometry("380x300")
            win.transient(parent.winfo_toplevel())
            win.grab_set()
            products = load_product_options()
            if not products:
                ctk.CTkLabel(win, text="No items found").pack(pady=30)
                return
            product_labels = [f"{name} - {price:.0f}" for _, name, price, _ in products]
            product_by_label = {label: product for label, product in zip(product_labels, products)}
            product_var = ctk.StringVar(value=product_labels[0])
            search_var = ctk.StringVar()
            search_entry = ctk.CTkEntry(win, textvariable=search_var, placeholder_text="Search item")
            search_entry.pack(fill="x", padx=20, pady=(20, 8))
            product_menu = ctk.CTkOptionMenu(win, variable=product_var, values=product_labels)
            product_menu.pack(fill="x", padx=20, pady=(0, 10))
            qty_entry = ctk.CTkEntry(win, placeholder_text="Quantity")
            qty_entry.insert(0, "1")
            qty_entry.pack(fill="x", padx=20, pady=10)

            search_timer = {"id": None}

            def update_products(*args):
                nonlocal product_by_label
                if search_timer["id"] is not None:
                    win.after_cancel(search_timer["id"])

                def refresh_options():
                    nonlocal product_by_label
                    products_now = load_product_options(search_var.get())
                    labels_now = [f"{name} - {price:.0f}" for _, name, price, _ in products_now]
                    product_by_label = {label: product for label, product in zip(labels_now, products_now)}
                    if labels_now:
                        product_var.set(labels_now[0])
                        product_menu.configure(values=labels_now)
                    else:
                        product_var.set("")
                        product_menu.configure(values=[""])

                search_timer["id"] = win.after(180, refresh_options)

            search_var.trace_add("write", update_products)

            def save_new_item():
                try:
                    qty = float(qty_entry.get())
                    if qty <= 0:
                        raise ValueError
                except Exception:
                    messagebox.showwarning("Warning", "Enter a valid quantity.", parent=win)
                    return
                if product_var.get() not in product_by_label:
                    messagebox.showwarning("Warning", "Select an item.", parent=win)
                    return
                item_id, name, price, cost = product_by_label[product_var.get()]
                cur.execute(
                    "INSERT INTO receipt_items (receipt_id, item_id, name, qty, price, cost) VALUES (?, ?, ?, ?, ?, ?)",
                    (rid, item_id, name, qty, price, cost or 0)
                )
                recalculate_receipt_total()
                conn.commit()
                notify_worker_receipt_change("added item to", rid, f"{name} x{qty:g}")
                win.destroy()
                after_change(rid)

            ctk.CTkButton(win, text="Add", fg_color="#f5c400", command=save_new_item).pack(fill="x", padx=20, pady=10)
            text_color="#15100a",
            ctk.CTkButton(win, text="Cancel", fg_color="#b23b2e", command=win.destroy).pack(fill="x", padx=20)

        try:
            dt = datetime.fromisoformat(time_)
            display_time = dt.strftime("%Y-%m-%d  %H:%M")
        except Exception:
            display_time = time_ or ""

        header = ctk.CTkFrame(parent, fg_color="#241c11", corner_radius=12)
        header.pack(fill="x", padx=8, pady=(8, 10))
        ctk.CTkLabel(
            header,
            text=f"🧾 فاتورة #{rid}",
            font=("Tahoma", 24, "bold")
        ).pack(anchor="w", padx=14, pady=(12, 2))
        meta_text = display_time
        if worker_name:
            meta_text += f"   |   العامل: {worker_name}"
        ctk.CTkLabel(
            header,
            text=meta_text,
            text_color="#e8dcc0",
            font=("Tahoma", 14)
        ).pack(anchor="w", padx=14, pady=(0, 12))

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.pack(fill="x", padx=8, pady=(0, 10))
        ctk.CTkButton(
            actions,
            text="+ Add Item",
            fg_color="#f5c400",
            text_color="#15100a",
            command=add_receipt_item
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            actions,
            text="Open Popup",
            fg_color="#3b2e1c",
            hover_color="#b8860b",
            command=lambda: show_receipt_details(rid)
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            actions,
            text="Delete Receipt",
            fg_color="#b23b2e",
            command=delete_receipt
        ).pack(side="right", padx=(6, 0))

        cur.execute("""
        SELECT id, name, qty, price
        FROM receipt_items
        WHERE receipt_id=?
        """, (rid,))
        items = cur.fetchall()

        if not items:
            ctk.CTkLabel(parent, text="لا توجد عناصر في هذه الفاتورة", text_color="gray").pack(pady=30)
        for receipt_item_id, name, qty, price in items:
            subtotal = qty * price
            card = ctk.CTkFrame(parent, fg_color="#2f2517", corner_radius=10)
            card.pack(fill="x", padx=8, pady=5)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=12, pady=(10, 4))
            item_label = ctk.CTkLabel(top_row, text=name, font=("Tahoma", 16, "bold"))
            item_label.pack(side="left")
            item_label.bind("<Button-1>", lambda e, n=name: show_item_receipts(n))
            ctk.CTkLabel(
                top_row,
                text=f"{subtotal:.2f} SYP",
                text_color="#ded38d",
                font=("Tahoma", 15, "bold")
            ).pack(side="right")

            ctk.CTkLabel(
                card,
                text=f"الكمية: {qty:g}   |   السعر: {price:.2f} SYP",
                text_color="#e8dcc0",
                font=("Tahoma", 13)
            ).pack(anchor="w", padx=12, pady=(0, 8))

            row_actions = ctk.CTkFrame(card, fg_color="transparent")
            row_actions.pack(fill="x", padx=12, pady=(0, 10))
            ctk.CTkButton(
                row_actions,
                text="Edit",
                width=85,
                command=lambda ri=receipt_item_id, q=qty, p=price: edit_receipt_item(ri, q, p)
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                row_actions,
                text="Remove",
                width=85,
                fg_color="#b23b2e",
                command=lambda ri=receipt_item_id: remove_receipt_item(ri)
            ).pack(side="left")

        total_card = ctk.CTkFrame(parent, fg_color="#5a4316", corner_radius=12)
        total_card.pack(fill="x", padx=8, pady=12)
        ctk.CTkLabel(
            total_card,
            text=f"💰 المجموع النهائي: {total:.2f} SYP",
            font=("Tahoma", 22, "bold")
        ).pack(pady=16)

    def create_receipt(day, after_created=None):
        win = ctk.CTkToplevel(main)
        win.title("New receipt")
        win.geometry("380x300")
        win.transient(main)
        win.grab_set()

        products = load_product_options()
        if not products:
            ctk.CTkLabel(win, text="No items found").pack(pady=30)
            return

        product_labels = [f"{name} - {price:.0f}" for _, name, price, _ in products]
        product_by_label = {label: product for label, product in zip(product_labels, products)}
        product_var = ctk.StringVar(value=product_labels[0])
        search_var = ctk.StringVar()
        ctk.CTkEntry(win, textvariable=search_var, placeholder_text="Search item").pack(fill="x", padx=20, pady=(20, 8))
        product_menu = ctk.CTkOptionMenu(win, variable=product_var, values=product_labels)
        product_menu.pack(fill="x", padx=20, pady=(0, 10))

        qty_entry = ctk.CTkEntry(win, placeholder_text="Quantity")
        qty_entry.insert(0, "1")
        qty_entry.pack(fill="x", padx=20, pady=10)

        search_timer = {"id": None}

        def update_products(*args):
            nonlocal product_by_label
            if search_timer["id"] is not None:
                win.after_cancel(search_timer["id"])

            def refresh_options():
                nonlocal product_by_label
                products_now = load_product_options(search_var.get())
                labels_now = [f"{name} - {price:.0f}" for _, name, price, _ in products_now]
                product_by_label = {label: product for label, product in zip(labels_now, products_now)}
                if labels_now:
                    product_var.set(labels_now[0])
                    product_menu.configure(values=labels_now)
                else:
                    product_var.set("")
                    product_menu.configure(values=[""])

            search_timer["id"] = win.after(180, refresh_options)

        search_var.trace_add("write", update_products)

        def save_receipt():
            try:
                qty = float(qty_entry.get())
                if qty <= 0:
                    raise ValueError
            except Exception:
                messagebox.showwarning("Warning", "Enter a valid quantity.", parent=win)
                return

            if product_var.get() not in product_by_label:
                messagebox.showwarning("Warning", "Select an item.", parent=win)
                return
            item_id, name, price, cost = product_by_label[product_var.get()]
            total = qty * price
            receipt_time = datetime.combine(day, datetime.now().time()).isoformat()
            cur.execute("PRAGMA table_info(receipts)")
            receipt_cols = {col[1] for col in cur.fetchall()}
            worker_id = current_worker.get("id") if current_worker else None
            worker_session_id = current_session.get("id") if current_session else None
            notification_watermark = sync_queue_watermark(conn)

            if {"worker_id", "worker_session_id", "income_date", "status"}.issubset(receipt_cols):
                cur.execute(
                    "INSERT INTO receipts (date, total, status, worker_id, worker_session_id, income_date) VALUES (?, ?, 'paid', ?, ?, ?)",
                    (receipt_time, total, worker_id, worker_session_id, receipt_time)
                )
            else:
                cur.execute(
                    "INSERT INTO receipts (date, total) VALUES (?, ?)",
                    (receipt_time, total)
                )
            receipt_id = cur.lastrowid
            cur.execute(
                "INSERT INTO receipt_items (receipt_id, item_id, name, qty, price, cost) VALUES (?, ?, ?, ?, ?, ?)",
                (receipt_id, item_id, name, qty, price, cost or 0)
            )
            suppress_notifications_since(conn, notification_watermark)
            conn.commit()
            win.destroy()
            if after_created:
                after_created(receipt_id)
            else:
                show_receipts(main, owner_mode)

        ctk.CTkButton(win, text="Create", fg_color="#f5c400", command=save_receipt).pack(fill="x", padx=20, pady=10)
        text_color="#15100a",
        ctk.CTkButton(win, text="Cancel", fg_color="#b23b2e", command=win.destroy).pack(fill="x", padx=20)

    # =========================
    # LOAD DAY CONTENT
    # =========================
    def load_day(day, selected_receipt_id=None):

        selected_day["value"] = day

        clear(right)

        # =========================
        # TOP BAR
        # =========================
        top = ctk.CTkFrame(right)
        top.pack(fill="x", pady=10)

        ctk.CTkLabel(
            top,
            text=f"🧾 {day}",
            font=("Tahoma", 24, "bold")
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            top,
            text="+ New Receipt",
            command=lambda d=day: create_receipt(
                d,
                lambda rid, selected_day=d: (
                    refresh_receipt_cache(),
                    load_day(selected_day, rid)
                )
            ),
            width=130,
            fg_color="#f5c400",
            text_color="#15100a",
        ).pack(side="right", padx=5)

        def set_receipts():
            mode["value"] = "receipts"
            load_day(selected_day["value"])

        def set_items():
            mode["value"] = "items"
            load_day(selected_day["value"])

        ctk.CTkButton(
            top,
            text="🧾 الفواتير",
            command=set_receipts,
            width=120
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            top,
            text="📦 العناصر",
            command=set_items,
            width=120
        ).pack(side="right", padx=5)

        ctk.CTkLabel(
            top,
            text="امسح QR/باركود عنصر لعرض فواتيره",
            text_color="#ded38d",
            font=("Tahoma", 13)
        ).pack(side="right", padx=10)

        receipts_for_day = receipts_by_day.get(day, [])

        # =========================
        # NO RECEIPTS
        # =========================
        if not receipts_for_day:

            ctk.CTkLabel(
                right,
                text="لا توجد فواتير لهذا اليوم",
                text_color="gray",
                font=("Tahoma", 18)
            ).pack(pady=50)

            return

        # =====================================================
        # MODE 1 = RECEIPTS MASTER-DETAIL
        # =====================================================
        if mode["value"] == "receipts":

            selected_receipt = {
                "id": selected_receipt_id or receipts_for_day[0][0]
            }

            split = ctk.CTkFrame(right, fg_color="transparent")
            split.pack(fill="both", expand=True, pady=(4, 0))

            receipt_list = ctk.CTkScrollableFrame(split, width=330, fg_color="#1c160e")
            receipt_list.pack(side="left", fill="y", padx=(0, 10), pady=5)

            detail_panel = ctk.CTkScrollableFrame(split, fg_color="#1c160e")
            detail_panel.pack(side="left", fill="both", expand=True, pady=5)

            day_total = sum((r[2] or 0) for r in receipts_for_day)
            ctk.CTkLabel(
                receipt_list,
                text=f"{len(receipts_for_day)} فواتير | {day_total:.2f} SYP",
                text_color="#ded38d",
                font=("Tahoma", 15, "bold")
            ).pack(fill="x", padx=8, pady=(8, 10))

            def after_detail_change(next_selected_id):
                refresh_receipt_cache()
                load_day(day, next_selected_id)

            def select_receipt(rid):
                selected_receipt["id"] = rid
                rebuild_receipt_list()
                render_receipt_detail_panel(detail_panel, rid, after_detail_change)

            def rebuild_receipt_list():
                for widget in receipt_list.winfo_children()[1:]:
                    widget.destroy()

                for receipt in receipts_for_day:
                    rid, time_, total, worker_name = receipt
                    try:
                        receipt_time = datetime.fromisoformat(time_).strftime("%H:%M")
                    except Exception:
                        receipt_time = ""

                    selected = rid == selected_receipt["id"]
                    card = ctk.CTkFrame(
                        receipt_list,
                        fg_color="#5a4316" if selected else "#2f2517",
                        corner_radius=10
                    )
                    card.pack(fill="x", padx=8, pady=5)
                    card.bind("<Button-1>", lambda _e, r=rid: select_receipt(r))
                    card.bind("<Double-Button-1>", lambda _e, r=rid: show_receipt_details(r))

                    header_row = ctk.CTkFrame(card, fg_color="transparent")
                    header_row.pack(fill="x", padx=10, pady=(10, 2))
                    receipt_label = ctk.CTkLabel(
                        header_row,
                        text=f"فاتورة #{rid}",
                        font=("Tahoma", 16, "bold")
                    )
                    receipt_label.pack(side="left")
                    receipt_label.bind("<Button-1>", lambda _e, r=rid: select_receipt(r))
                    receipt_label.bind("<Double-Button-1>", lambda _e, r=rid: show_receipt_details(r))
                    ctk.CTkLabel(
                        header_row,
                        text=receipt_time,
                        text_color="#e8dcc0",
                        font=("Tahoma", 13)
                    ).pack(side="right")

                    ctk.CTkLabel(
                        card,
                        text=f"{total or 0:.2f} SYP",
                        text_color="#f5c400",
                        font=("Tahoma", 17, "bold")
                    ).pack(anchor="w", padx=10)

                    meta = f"{receipt_item_counts.get(rid, 0)} items"
                    if worker_name:
                        meta += f" | {worker_name}"
                    ctk.CTkLabel(
                        card,
                        text=meta,
                        text_color="#ded38d",
                        font=("Tahoma", 12)
                    ).pack(anchor="w", padx=10, pady=(0, 10))

            rebuild_receipt_list()
            render_receipt_detail_panel(detail_panel, selected_receipt["id"], after_detail_change)

        # =====================================================
        # MODE 2 = ITEM ANALYTICS
        # =====================================================
        else:
            analytics_panel = ctk.CTkScrollableFrame(right, fg_color="transparent")
            analytics_panel.pack(fill="both", expand=True, pady=(4, 0))

            receipt_ids = [r[0] for r in receipts_for_day]
            placeholders = ",".join("?" for _ in receipt_ids)
            cur.execute(f"""
                SELECT
                    ri.name,
                    SUM(ri.qty) AS qty,
                    SUM(ri.qty * ri.price) AS revenue,
                    SUM(ri.qty * COALESCE(ri.cost, i.cost, 0)) AS cost
                FROM receipt_items ri
                JOIN receipts r ON r.id = ri.receipt_id
                LEFT JOIN items i ON ri.item_id = i.id
                WHERE ri.receipt_id IN ({placeholders})
                  AND (r.status IS NULL OR r.status = 'paid')
                GROUP BY ri.name
                ORDER BY qty DESC
            """, receipt_ids)

            item_map = {
                name: {
                    "qty": qty or 0,
                    "revenue": revenue or 0,
                    "profit": (revenue or 0) - (cost or 0)
                }
                for name, qty, revenue, cost in cur.fetchall()
            }

            total_profit = 0

            sorted_items = sorted(
                item_map.items(),
                key=lambda x: x[1]["qty"],
                reverse=True
            )

            for name, data in sorted_items:

                total_profit += data["profit"]

                card = ctk.CTkFrame(
                    analytics_panel,
                    fg_color="#2f2517",
                    corner_radius=15
                )

                card.pack(fill="x", pady=8)
                card.bind("<Button-1>", lambda e, n=name: show_item_receipts(n))

                item_label = ctk.CTkLabel(
                    card,
                    text=name,
                    font=("Tahoma", 20, "bold")
                )
                item_label.pack(anchor="w", padx=15, pady=(10, 0))
                item_label.bind("<Button-1>", lambda e, n=name: show_item_receipts(n))

                ctk.CTkLabel(
                    card,
                    text=f"الكمية: {data['qty']}",
                    font=("Tahoma", 16)
                ).pack(anchor="w", padx=15)

                ctk.CTkLabel(
                    card,
                    text=f"الإيراد: {data['revenue']:.2f} SYP",
                    text_color="#f5c400",
                    font=("Tahoma", 16)
                ).pack(anchor="w", padx=15)

                ctk.CTkLabel(
                    card,
                    text=f"الربح: {data['profit']:.2f} SYP",
                    text_color="#ded38d",
                    font=("Tahoma", 16)
                ).pack(anchor="w", padx=15, pady=(0, 10))

            total_card = ctk.CTkFrame(
                analytics_panel,
                fg_color="#5a4316",
                corner_radius=15
            )

            total_card.pack(fill="x", pady=15)

            ctk.CTkLabel(
                total_card,
                text=f"💰 إجمالي الربح لليوم: {total_profit:.2f} SYP",
                font=("Tahoma", 22, "bold")
            ).pack(pady=20)

    # =========================
    # CALENDAR RENDER
    # =========================
    def show_calendar():

        clear(left)

        header = ctk.CTkFrame(left)
        header.pack(fill="x", pady=10)

        def prev_month():

            current["month"] -= 1

            if current["month"] < 1:
                current["month"] = 12
                current["year"] -= 1

            show_calendar()

        def next_month():

            current["month"] += 1

            if current["month"] > 12:
                current["month"] = 1
                current["year"] += 1

            show_calendar()

        ctk.CTkButton(
            header,
            text="⬅",
            width=40,
            command=prev_month
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            header,
            text=f"{calendar.month_name[current['month']]} {current['year']}",
            font=("Tahoma", 24, "bold")
        ).pack(side="left", padx=20)

        ctk.CTkButton(
            header,
            text="➡",
            width=40,
            command=next_month
        ).pack(side="left", padx=5)

        week_frame = ctk.CTkFrame(left, fg_color="transparent")
        week_frame.pack(pady=5)

        for w in ["الإث", "الث", "الأر", "الخ", "الج", "الس", "الأح"]:
            ctk.CTkLabel(
                week_frame,
                text=w,
                width=50,
                font=("Tahoma", 14, "bold")
            ).pack(side="left", padx=2)

        cal_frame = ctk.CTkFrame(left, fg_color="transparent")
        cal_frame.pack()

        cal = calendar.Calendar()

        for week in cal.monthdayscalendar(
            current["year"],
            current["month"]
        ):

            row = ctk.CTkFrame(cal_frame, fg_color="transparent")
            row.pack()

            for day_num in week:

                if day_num == 0:

                    ctk.CTkLabel(
                        row,
                        text="",
                        width=50,
                        height=50
                    ).pack(side="left", padx=2, pady=2)

                    continue

                day_date = date(
                    current["year"],
                    current["month"],
                    day_num
                )

                has_receipts = day_date in receipts_by_day

                color = "#3b2e1c"

                if day_date == today:
                    color = "#f5c400"

                elif has_receipts:
                    color = "#b8860b"

                btn = ctk.CTkButton(
                    row,
                    text=str(day_num),
                    width=50,
                    height=50,
                    corner_radius=10,
                    fg_color=color,
                    command=lambda d=day_date: load_day(d)
                )

                btn.pack(side="left", padx=2, pady=2)

    show_calendar()
    load_day(today)
