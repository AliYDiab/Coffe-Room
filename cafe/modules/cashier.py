import customtkinter as ctk
from tkinter import messagebox
import sqlite3
import time
from datetime import datetime

from adb import cur, conn, get_worker_session_totals
from firebase_sync import suppress_notifications_since, sync_queue_watermark
import state
from state import cart, current_worker, current_session
from utils import clear, get_item_stock


# =========================================================
# MAIN CASHIER
# =========================================================
def show_cashier(main, refresh_callback):

    clear(main)

    root = ctk.CTkFrame(main)
    root.pack(fill="both", expand=True)

    # =====================================================
    # TOP BAR
    # =====================================================
    top = ctk.CTkFrame(root, height=80, fg_color="#2f2517")
    top.pack(fill="x", padx=10, pady=10)
    top.pack_propagate(False)

    left_info = ctk.CTkFrame(top, fg_color="transparent")
    left_info.pack(side="left", padx=20)

    ctk.CTkLabel(
        left_info,
        text="☕ Coffe Room",
        font=("Tahoma", 28, "bold")
    ).pack(anchor="w")

    ctk.CTkLabel(
        left_info,
        text=datetime.now().strftime("%A %d %B %Y"),
        text_color="#e8dcc0"
    ).pack(anchor="w")

    right_info = ctk.CTkFrame(top, fg_color="transparent")
    right_info.pack(side="right", padx=20)

    cur.execute("SELECT COUNT(*) FROM receipts")
    total_orders = cur.fetchone()[0] or 0

    cur.execute("SELECT SUM(total) FROM receipts WHERE status IS NULL OR status = 'paid'")
    total_revenue = cur.fetchone()[0] or 0

    ctk.CTkLabel(
        right_info,
        text=f"🧾 الطلبات: {total_orders}",
        font=("Tahoma", 15)
    ).pack(anchor="e")

    ctk.CTkLabel(
        right_info,
        text=f"💰 الإيرادات: {total_revenue:.2f} SYP",
        text_color="#f5c400",
        font=("Tahoma", 15, "bold")
    ).pack(anchor="e")

    # عرض معلومات العامل وسجل اليوم (فقط في وضع العامل)
    work_info = ctk.CTkFrame(right_info, fg_color="transparent")
    work_info.pack(anchor="e", pady=(10, 0))

    def update_work_display():
        for widget in work_info.winfo_children():
            widget.destroy()

        # عرض معلومات العامل فقط في وضع العامل
        if state.app_mode == "worker" and current_worker and current_session:
            worker_name = current_worker.get("name", "غير معروف")
            session_id = current_session.get("id", "غير معروف")
            session_date = current_session.get("work_date", "غير معروف")
            worker_totals = get_worker_session_totals(session_id)

            ctk.CTkLabel(
                work_info,
                text=f"👷 {worker_name}",
                font=("Tahoma", 12),
                text_color="#ded38d"
            ).pack(anchor="e")

            ctk.CTkLabel(
                work_info,
                text=f"📅 {session_date}",
                font=("Tahoma", 12),
                text_color="#ded38d"
            ).pack(anchor="e")

            ctk.CTkLabel(
                work_info,
                text=(
                    f"عناصر اليوم: {worker_totals['items']:g} | "
                    f"الدخل: {worker_totals['revenue']:,.0f} SYP"
                ),
                font=("Tahoma", 12, "bold"),
                text_color="#f5c400"
            ).pack(anchor="e")
        else:
            # في وضع المالك أو بدون جلسة، لا تعرض شيء
            pass

    update_work_display()

    # =====================================================
    # BODY
    # =====================================================
    body = ctk.CTkFrame(root, fg_color="transparent")
    body.pack(fill="both", expand=True)

    sidebar = ctk.CTkScrollableFrame(body, width=220, fg_color="#2f2517")
    sidebar.pack(side="left", fill="y", padx=10, pady=10)

    ctk.CTkLabel(
        sidebar,
        text="📂 الفئات",
        font=("Tahoma", 24, "bold")
    ).pack(pady=20)

    center = ctk.CTkScrollableFrame(body, fg_color="#241c11")
    center.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    cart_panel = ctk.CTkFrame(body, width=400, fg_color="#2f2517")
    cart_panel.pack(side="right", fill="y", padx=10, pady=10)
    cart_panel.pack_propagate(False)

    search_var = ctk.StringVar()
    search_entry = ctk.CTkEntry(
        center,
        placeholder_text="🔍 بحث عن المنتجات...",
        height=45,
        textvariable=search_var,
        font=("Tahoma", 16)
    )
    search_entry.pack(fill="x", padx=15, pady=15)

    content_frame = ctk.CTkFrame(center, fg_color="transparent")
    content_frame.pack(fill="both", expand=True)

    selected_category = {"value": None}
    product_page = {"limit": 36}
    PRODUCT_BATCH_SIZE = 36

    # =====================================================
    # BARCODE SCANNER
    # =====================================================
    scan_buffer = {"chars": "", "timer": None, "started": None, "last": None}
    SCAN_TIMEOUT_MS = 80
    MIN_SCAN_LENGTH = 4
    MAX_SCAN_DURATION_MS = 1200
    MAX_KEY_GAP_MS = 120
    TEXT_WIDGET_CLASSES = {"Entry", "Text", "TEntry", "Spinbox"}

    def remove_scanned_text_from_focused_input(code):
        try:
            focused = root.winfo_toplevel().focus_get()
            if focused is None or focused.winfo_class() not in TEXT_WIDGET_CLASSES:
                return
            value = focused.get()
            if value.endswith(code):
                focused.delete(len(value) - len(code), "end")
        except Exception:
            pass

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
        cur.execute("""
            SELECT id, name, price, stock, 0, type, cost
            FROM items WHERE barcode_value = ?
        """, (code,))
        item = cur.fetchone()
        if item:
            remove_scanned_text_from_focused_input(code)
            add_to_cart(item)
            try:
                import winsound
                winsound.Beep(1200, 80)
            except Exception:
                pass
        else:
            print("Barcode not found:", code)

    def on_scan_key(event):
        if not root.winfo_exists():
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

    try:
        tk_root = root.winfo_toplevel()
        tk_root.bind("<Key>", on_scan_key)
    except Exception:
        # إذا فشل ربط الحدث، تجاهله (المسح الضوئي قد لا يعمل في هذا الوضع)
        print("Warning: Could not bind keyboard events for barcode scanning")

    def on_search_focus_in(event):
        if scan_buffer["timer"] is not None:
            root.after_cancel(scan_buffer["timer"])
            scan_buffer["timer"] = None
        scan_buffer["chars"] = ""

    def on_search_focus_out(event):
        scan_buffer["chars"] = ""

    search_entry._entry.bind("<FocusIn>",  on_search_focus_in)
    search_entry._entry.bind("<FocusOut>", on_search_focus_out)
    search_entry._entry.bind("<Escape>", lambda e: root.winfo_toplevel().focus_set())

    # =====================================================
    # AVAILABILITY HELPERS
    # =====================================================
    def is_item_available(item_id):
        cur.execute("SELECT type, stock FROM items WHERE id=?", (item_id,))
        row = cur.fetchone()
        if not row:
            return False
        item_type, stock = row
        item_type = item_type or "fixed"
        if item_type == "fixed":
            return stock is None or stock > 0
        cur.execute("SELECT ingredient_id, qty FROM item_ingredients WHERE item_id=?", (item_id,))
        recipe = cur.fetchall()
        if not recipe:
            return False
        for ing_id, needed_qty in recipe:
            cur.execute("SELECT quantity FROM ingredients WHERE id=?", (ing_id,))
            r = cur.fetchone()
            if (r[0] if r else 0) < needed_qty:
                return False
        return True

    def current_available_qty(item_id):
        cur.execute("SELECT type, stock FROM items WHERE id=?", (item_id,))
        row = cur.fetchone()
        if not row:
            return 0
        item_type, stock = row
        item_type = item_type or "fixed"
        if item_type == "fixed":
            return None if stock is None else stock
        cur.execute("SELECT ingredient_id, qty FROM item_ingredients WHERE item_id=?", (item_id,))
        recipe = cur.fetchall()
        if not recipe:
            return 0
        min_available = float("inf")
        for ing_id, needed_qty in recipe:
            cur.execute("SELECT quantity FROM ingredients WHERE id=?", (ing_id,))
            r = cur.fetchone()
            min_available = min(min_available, (r[0] if r else 0) // needed_qty)
        return min_available if min_available != float("inf") else 0

    def load_recipe_stock_map(item_ids):
        if not item_ids:
            return {}
        placeholders = ",".join("?" for _ in item_ids)
        cur.execute(f"""
            SELECT ii.item_id, ii.qty, ing.quantity
            FROM item_ingredients ii
            JOIN ingredients ing ON ii.ingredient_id = ing.id
            WHERE ii.item_id IN ({placeholders})
        """, item_ids)
        possible = {}
        for item_id, needed_qty, available_qty in cur.fetchall():
            if not needed_qty:
                continue
            possible.setdefault(item_id, []).append((available_qty or 0) // needed_qty)
        return {
            item_id: int(min(values)) if values else 0
            for item_id, values in possible.items()
        }

    # =====================================================
    # LOAD PRODUCTS
    # =====================================================
    def load_items(category=None, reset_limit=False):
        selected_category["value"] = category
        if reset_limit:
            product_page["limit"] = PRODUCT_BATCH_SIZE
        for widget in content_frame.winfo_children():
            widget.destroy()

        search = search_var.get().strip()
        where = []
        params = []
        if category:
            where.append("i.category = ?")
            params.append(category)
        if search:
            where.append("i.name LIKE ?")
            params.append(f"%{search}%")

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        cur.execute(f"SELECT COUNT(*) FROM items i {where_sql}", params)
        total_items = cur.fetchone()[0] or 0

        cur.execute(f"""
            SELECT i.id, i.name, i.price, i.stock,
                   COALESCE(s.sold, 0) AS sold, i.type, i.cost
            FROM items i
            LEFT JOIN (
                SELECT item_id, SUM(qty) AS sold
                FROM receipt_items
                WHERE item_id IS NOT NULL
                GROUP BY item_id
            ) s ON s.item_id = i.id
            {where_sql}
            ORDER BY sold DESC, i.name
            LIMIT ?
        """, params + [product_page["limit"]])

        visible_items = cur.fetchall()
        recipe_stock = load_recipe_stock_map([
            item_id for item_id, _, _, _, _, item_type, _ in visible_items
            if (item_type or "fixed") != "fixed"
        ])

        grid_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True)
        columns = 6
        for i in range(columns):
            grid_frame.grid_columnconfigure(i, weight=1, minsize=120)

        row = col = 0
        for item in visible_items:
            item_id, name, price, stock, sold, item_type, item_cost = item
            item_type = item_type or "fixed"
            item_cost = item_cost or 0
            stock_text = None if item_type == "fixed" and stock is None else (
                stock if item_type == "fixed" else recipe_stock.get(item_id, 0)
            )
            available = stock_text is None or stock_text > 0

            if available:
                add_text, b_state, b_color, bh_color = "+ إضافة", "normal", "#b8860b", "#d8c81d"
            else:
                add_text, b_state, b_color, bh_color = "غير متوفر", "disabled", "#b23b2e", "#7a261f"

            card = ctk.CTkFrame(grid_frame, width=120, height=145, corner_radius=12, fg_color="#2f2517")
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            card.grid_propagate(False)

            ctk.CTkLabel(card, text=name, font=("Tahoma", 13, "bold"), wraplength=105).pack(pady=(10, 4))
            ctk.CTkLabel(card, text=f"{price:.0f} SYP", text_color="#f5c400", font=("Tahoma", 15, "bold")).pack()

            if stock_text is None:
                disp_stock, s_color = "∞", "#e8dcc0"
            else:
                disp_stock = str(stock_text)
                s_color = "#b23b2e" if stock_text < 10 else "#e8dcc0"

            ctk.CTkLabel(card, text=f"المخزون: {disp_stock}", text_color=s_color).pack()
            ctk.CTkLabel(card, text=f"🔥 المبيعات: {sold}", text_color="#ded38d").pack(pady=(0, 10))
            ctk.CTkButton(
                card, state=b_state, text=add_text, height=30, corner_radius=8,
                fg_color=b_color, hover_color=bh_color,
                font=("Tahoma", 11, "bold"),
                command=lambda x=item: add_to_cart(x)
            ).pack(fill="x", padx=8, pady=(3, 8))

            col += 1
            if col >= columns:
                col = 0
                row += 1

        if total_items > product_page["limit"]:
            ctk.CTkButton(
                content_frame,
                text=f"Load more ({total_items - product_page['limit']})",
                height=40,
                fg_color="#3b2e1c",
                hover_color="#b8860b",
                command=lambda: (
                    product_page.update({"limit": product_page["limit"] + PRODUCT_BATCH_SIZE}),
                    load_items(selected_category["value"])
                )
            ).pack(fill="x", padx=15, pady=12)

    # =====================================================
    # CART
    # =====================================================
    def load_cart():
        for w in cart_panel.winfo_children():
            w.destroy()

        cart_items_frame = ctk.CTkScrollableFrame(cart_panel, fg_color="transparent")
        cart_items_frame.pack(fill="both", expand=True, padx=5, pady=(5, 0))

        ctk.CTkLabel(
            cart_items_frame, text="🛒 الطلب الحالي",
            font=("Tahoma", 26, "bold")
        ).pack(pady=20)

        total = 0
        for name, item in cart.items():
            subtotal = item["price"] * item["qty"]
            total += subtotal

            card = ctk.CTkFrame(cart_items_frame, fg_color="#3b2e1c", corner_radius=15)
            card.pack(fill="x", padx=10, pady=8)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(10, 5))
            ctk.CTkLabel(
                top_row,
                text=name,
                font=("Tahoma", 17, "bold"),
                anchor="w",
                justify="left",
                wraplength=230
            ).pack(fill="x", anchor="w")
            ctk.CTkLabel(
                top_row,
                text=f"{subtotal:.2f} SYP",
                text_color="#f5c400",
                font=("Tahoma", 16, "bold")
            ).pack(anchor="e", pady=(4, 0))

            controls = ctk.CTkFrame(card, fg_color="transparent")
            controls.pack(fill="x", padx=10, pady=(0, 10))

            def increase(n=name):
                avail = current_available_qty(cart[n]["id"])
                if avail is not None and cart[n]["qty"] + 1 > avail:
                    messagebox.showwarning("تنبيه", "الكمية المتوفرة غير كافية")
                    return
                cart[n]["qty"] += 1
                root.after(10, load_cart)

            def decrease(n=name):
                cart[n]["qty"] -= 1
                if cart[n]["qty"] <= 0:
                    del cart[n]
                root.after(10, load_cart)

            ctk.CTkButton(controls, text="-", width=40, command=decrease).pack(side="left")
            ctk.CTkLabel(controls, text=str(item["qty"]), width=50,
                         font=("Tahoma", 16, "bold")).pack(side="left")
            ctk.CTkButton(controls, text="+", width=40, command=increase).pack(side="left")

        footer = ctk.CTkFrame(cart_panel, fg_color="transparent")
        footer.pack(fill="x", padx=5, pady=(5, 10))

        total_box = ctk.CTkFrame(footer, fg_color="#5a4316", corner_radius=20)
        total_box.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(total_box, text="الإجمالي", font=("Tahoma", 18)).pack(pady=(15, 5))
        ctk.CTkLabel(total_box, text=f"{total:.2f} SYP",
                     font=("Tahoma", 34, "bold")).pack(pady=(0, 15))

        # ── two checkout buttons ──
        btn_row = ctk.CTkFrame(footer, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=0)

        ctk.CTkButton(
            btn_row, text="💳 دفع",
            height=55, corner_radius=18,
            fg_color="#f5c400", hover_color="#d9a900",
            text_color="#15100a",
            font=("Tahoma", 18, "bold"),
            command=lambda: checkout(is_debt=False)
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(
            btn_row, text="📋 دين",
            height=55, corner_radius=18,
            fg_color="#ded38d", hover_color="#a77910",
            text_color="#15100a",
            font=("Tahoma", 18, "bold"),
            command=lambda: open_debt_checkout(total)
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

    # =====================================================
    # DEBT CHECKOUT POPUP
    # =====================================================
    def open_debt_checkout(total):
        if not cart:
            return

        win = ctk.CTkToplevel()
        win.title("📋 تسجيل كدين")
        win.geometry("380x460")
        win.attributes("-topmost", True)
        win.focus_force()
        win.grab_set()

        ctk.CTkLabel(
            win, text="📋 تسجيل الطلب كدين",
            font=("Tahoma", 18, "bold")
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            win, text=f"المبلغ الإجمالي: {total:,.0f} SYP",
            text_color="#ded38d", font=("Tahoma", 15, "bold")
        ).pack(pady=(0, 15))

        ctk.CTkLabel(
            win, text="اختر زبون موجود أو اكتب اسم جديد",
            text_color="#e8dcc0", font=("Tahoma", 13)
        ).pack()

        cur.execute("SELECT DISTINCT customer FROM debts ORDER BY customer")
        existing = [r[0] for r in cur.fetchall()]

        customer_var = ctk.StringVar()
        customer_entry = ctk.CTkEntry(
            win, textvariable=customer_var,
            placeholder_text="اسم الزبون...",
            font=("Tahoma", 14), height=42
        )
        customer_entry.pack(fill="x", padx=20, pady=(10, 4))

        suggest_frame = ctk.CTkFrame(win, fg_color="#3b2e1c", corner_radius=8)

        def update_suggestions(*args):
            for w in suggest_frame.winfo_children():
                w.destroy()
            text = customer_var.get().strip()
            if not text:
                suggest_frame.pack_forget()
                return
            matches = [c for c in existing if text.lower() in c.lower()]
            if not matches:
                suggest_frame.pack_forget()
                return
            suggest_frame.pack(fill="x", padx=20, pady=(0, 6))
            for name in matches[:5]:
                ctk.CTkButton(
                    suggest_frame, text=name, height=32,
                    fg_color="transparent", hover_color="#b8860b",
                    anchor="w", font=("Tahoma", 13),
                    command=lambda n=name: [
                        customer_var.set(n),
                        suggest_frame.pack_forget()
                    ]
                ).pack(fill="x", padx=4, pady=1)

        customer_var.trace_add("write", update_suggestions)

        if existing:
            ctk.CTkLabel(
                win, text="زبائن موجودون:",
                text_color="#e8dcc0", font=("Tahoma", 12)
            ).pack(anchor="w", padx=20, pady=(8, 4))

            quick_frame = ctk.CTkScrollableFrame(
                win, height=100, fg_color="#2f2517", corner_radius=8
            )
            quick_frame.pack(fill="x", padx=20, pady=(0, 10))

            for cname in existing:
                ctk.CTkButton(
                    quick_frame, text=cname, height=32,
                    fg_color="#3b2e1c", hover_color="#b8860b",
                    font=("Tahoma", 13), anchor="w",
                    command=lambda n=cname: customer_var.set(n)
                ).pack(fill="x", pady=2)

        note_entry = ctk.CTkEntry(
            win, placeholder_text="ملاحظة (اختياري)",
            font=("Tahoma", 13)
        )
        note_entry.pack(fill="x", padx=20, pady=(0, 20))

        def confirm_debt():
            customer = customer_var.get().strip()
            if not customer:
                messagebox.showwarning("تنبيه", "أدخل اسم الزبون", parent=win)
                return
            note = note_entry.get().strip() or None
            win.destroy()
            checkout(is_debt=True, customer=customer, debt_note=note)

        ctk.CTkButton(
            win, text="✅ تأكيد الدين",
            height=50, corner_radius=14,
            fg_color="#ded38d", hover_color="#a77910",
            text_color="#15100a",
            font=("Tahoma", 16, "bold"),
            command=confirm_debt
        ).pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkButton(
            win, text="إلغاء", height=36,
            fg_color="#5a4528", hover_color="#725a34",
            command=win.destroy
        ).pack(fill="x", padx=20)

    # =====================================================
    # ADD TO CART
    # =====================================================
    def add_to_cart(item):
        item_id, name, price, stock, sold, item_type, item_cost = item
        item_type = item_type or "fixed"

        avail       = current_available_qty(item_id)
        current_qty = cart.get(name, {}).get("qty", 0)

        if avail is not None and current_qty + 1 > avail:
            messagebox.showwarning("تنبيه", "الكمية المتوفرة غير كافية")
            return

        if name not in cart:
            cart[name] = {
                "id":    item_id,
                "price": price,
                "qty":   0,
                "type":  item_type,
                "stock": stock,
                "cost":  item_cost or 0
            }

        cart[name]["qty"] += 1
        root.after(10, load_cart)

    # =====================================================
    # CHECKOUT
    # =====================================================
    def checkout(is_debt=False, customer=None, debt_note=None):
        if not cart:
            return

        # STEP 1: validation
        for name, item in cart.items():
            qty_sold  = item["qty"]
            item_id   = item.get("id")
            item_type = item.get("type") or "fixed"
            stock     = item.get("stock")

            if not item_id:
                cur.execute("SELECT id, stock, type FROM items WHERE name=?", (name,))
                result = cur.fetchone()
                if not result:
                    messagebox.showerror("خطأ", f"العنصر {name} غير موجود")
                    return
                item_id, stock, item_type = result
                item_type = item_type or "fixed"

            available_qty = get_item_stock(cur, item_id, item_type, stock)
            if available_qty is not None:
                if available_qty <= 0:
                    messagebox.showerror("خطأ", f"{name} غير متوفر")
                    return
                if qty_sold > available_qty:
                    messagebox.showerror("خطأ", f"الكمية غير كافية لـ {name}")
                    return

        # STEP 2: ensure columns exist
        _ensure_receipt_debt_columns()
        _ensure_worker_columns()

        paid_status = "debt" if is_debt else "paid"

        # معلومات العامل وسجل يومه الحالي
        worker_id = current_worker.get("id") if current_worker else None
        worker_session_id = current_session.get("id") if current_session else None
        receipt_time = datetime.now().isoformat()
        income_date = None if is_debt else receipt_time
        notification_watermark = sync_queue_watermark(conn)

        try:
            cur.execute("""
                INSERT INTO receipts (date, total, status, customer, worker_id, worker_session_id, income_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (receipt_time, 0, paid_status, customer, worker_id, worker_session_id, income_date))
        except sqlite3.OperationalError:
            cur.execute("""
                INSERT INTO receipts (time, total, status, customer, worker_id, worker_session_id, income_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (receipt_time, 0, paid_status, customer, worker_id, worker_session_id, income_date))

        receipt_id = cur.lastrowid
        total = 0

        # STEP 3: process items
        for name, item in cart.items():
            qty_sold  = item["qty"]
            price     = item["price"]
            item_cost = item.get("cost") or 0
            item_id   = item.get("id")
            item_type = item.get("type") or "fixed"
            stock     = item.get("stock")

            if not item_id:
                cur.execute("SELECT id, stock, type, cost FROM items WHERE name=?", (name,))
                result = cur.fetchone()
                if not result:
                    continue
                item_id, stock, item_type, item_cost = result
                item_type = item_type or "fixed"

            if item_type == "recipe":
                cur.execute("SELECT ingredient_id, qty FROM item_ingredients WHERE item_id=?", (item_id,))
                for ing_id, qty_needed in cur.fetchall():
                    total_deduct = qty_needed * qty_sold
                    cur.execute("""
                        UPDATE ingredients
                        SET quantity = CASE WHEN quantity - ? < 0 THEN 0 ELSE quantity - ? END
                        WHERE id = ?
                    """, (total_deduct, total_deduct, ing_id))
            else:
                cur.execute("""
                    UPDATE items
                    SET stock = CASE WHEN stock IS NULL THEN NULL
                                     WHEN stock - ? < 0 THEN 0
                                     ELSE stock - ? END
                    WHERE id = ?
                """, (qty_sold, qty_sold, item_id))

            cur.execute("SELECT stock, type FROM items WHERE id=?", (item_id,))
            row = cur.fetchone()
            if row:
                stock_after, type_after = row
                type_after = type_after or item_type
                try:
                    real_after = get_item_stock(cur, item_id, type_after, stock_after)
                except TypeError:
                    real_after = get_item_stock(item_id, type_after, stock_after)

                new_available = 1 if (
                    type_after == "fixed" and (stock_after is None or stock_after > 0)
                ) or (
                    type_after != "fixed" and real_after is not None and real_after > 0
                ) else 0
                cur.execute("UPDATE items SET available=? WHERE id=?", (new_available, item_id))

            subtotal = price * qty_sold
            total   += subtotal

            try:
                cur.execute("""
                    INSERT INTO receipt_items (receipt_id, item_id, name, qty, price, cost)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (receipt_id, item_id, name, qty_sold, price, item_cost))
            except sqlite3.OperationalError:
                cur.execute("""
                    INSERT INTO receipt_items (receipt_id, name, qty, price)
                    VALUES (?, ?, ?, ?)
                """, (receipt_id, name, qty_sold, price))

        cur.execute("UPDATE receipts SET total=? WHERE id=?", (total, receipt_id))

        # STEP 4: if debt → link to debts table
        if is_debt:
            _ensure_debt_tables()
            cur.execute("""
                INSERT INTO debts (customer, amount, paid, note, created_at, receipt_id)
                VALUES (?, ?, 0, ?, ?, ?)
            """, (customer, total, debt_note, datetime.now().isoformat(), receipt_id))

        # A checkout is one new-receipt action. Keep its data sync, but do not
        # turn the receipt or its stock deductions into a generic push. A debt
        # created by the same checkout remains a separately notifiable event.
        suppress_notifications_since(
            conn,
            notification_watermark,
            keep_tables={"debts"} if is_debt else (),
        )
        conn.commit()
        cart.clear()

        product_page["limit"] = PRODUCT_BATCH_SIZE
        load_items(selected_category["value"])
        load_cart()

    def checkout_on_enter(event=None):
        try:
            if not root.winfo_exists():
                return
            if scan_buffer["chars"].strip():
                flush_scan()
                return "break"
            if not cart:
                return
        except Exception:
            return

        checkout(is_debt=False)
        return "break"

    try:
        root.winfo_toplevel().bind("<Return>", checkout_on_enter)
        root.winfo_toplevel().bind("<KP_Enter>", checkout_on_enter)
    except Exception:
        print("Warning: Could not bind Enter key for checkout")

    # =====================================================
    # CATEGORY BUTTONS
    # =====================================================
    ctk.CTkButton(
        sidebar, text="🌍 الكل", height=50, corner_radius=15,
        font=("Tahoma", 16, "bold"), command=lambda: load_items(reset_limit=True)
    ).pack(fill="x", padx=10, pady=5)

    cur.execute("SELECT name FROM categories")
    for cat in [c[0] for c in cur.fetchall()]:
        ctk.CTkButton(
            sidebar, text=cat, height=50, corner_radius=15,
            font=("Tahoma", 16), command=lambda c=cat: load_items(c, reset_limit=True)
        ).pack(fill="x", padx=10, pady=5)

    search_timer = {"id": None}

    def schedule_search(*args):
        if search_timer["id"] is not None:
            root.after_cancel(search_timer["id"])
        search_timer["id"] = root.after(
            150,
            lambda: load_items(selected_category["value"], reset_limit=True)
        )

    search_var.trace_add("write", schedule_search)

    load_items(reset_limit=True)
    root.after(10, load_cart)


# =====================================================
# DB MIGRATION HELPERS
# =====================================================
def _ensure_receipt_debt_columns():
    cur.execute("PRAGMA table_info(receipts)")
    cols = [c[1] for c in cur.fetchall()]
    if "status" not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN status TEXT DEFAULT 'paid'")
    if "customer" not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN customer TEXT")
    conn.commit()


def _ensure_debt_tables():
    cur.execute("PRAGMA table_info(debts)")
    cols = [c[1] for c in cur.fetchall()]
    if "receipt_id" not in cols:
        cur.execute("ALTER TABLE debts ADD COLUMN receipt_id INTEGER")
    conn.commit()


def _ensure_worker_columns():
    """Ensure worker-day and income-recognition fields exist on receipts."""
    cur.execute("PRAGMA table_info(receipts)")
    cols = [c[1] for c in cur.fetchall()]
    if "worker_id" not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN worker_id INTEGER")
    if "worker_session_id" not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN worker_session_id INTEGER")
    if "income_date" not in cols:
        cur.execute("ALTER TABLE receipts ADD COLUMN income_date TEXT")
    conn.commit()
