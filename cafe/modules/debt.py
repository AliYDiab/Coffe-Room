import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from adb import cur, conn, create_sync_triggers, record_debt_payment
from firebase_sync import suppress_notifications_since, sync_queue_watermark
from state import current_session, current_worker
from utils import clear


# =====================================================
# INIT TABLES
# =====================================================
def init_debt_tables():
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS debts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            customer    TEXT    NOT NULL,
            amount      REAL    NOT NULL DEFAULT 0,
            paid        REAL    NOT NULL DEFAULT 0,
            note        TEXT,
            created_at  TEXT    NOT NULL,
            receipt_id  INTEGER
        );

        CREATE TABLE IF NOT EXISTS debt_payments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            debt_id    INTEGER NOT NULL REFERENCES debts(id),
            amount     REAL    NOT NULL,
            paid_at    TEXT    NOT NULL,
            note       TEXT
        );
    """)
    # safe migration: add receipt_id if missing
    cur.execute("PRAGMA table_info(debts)")
    cols = [c[1] for c in cur.fetchall()]
    if "receipt_id" not in cols:
        cur.execute("ALTER TABLE debts ADD COLUMN receipt_id INTEGER")

    # safe migration: add status + customer to receipts if missing
    cur.execute("PRAGMA table_info(receipts)")
    rcols = [c[1] for c in cur.fetchall()]
    if "status" not in rcols:
        cur.execute("ALTER TABLE receipts ADD COLUMN status TEXT DEFAULT 'paid'")
    if "customer" not in rcols:
        cur.execute("ALTER TABLE receipts ADD COLUMN customer TEXT")
    if "worker_id" not in rcols:
        cur.execute("ALTER TABLE receipts ADD COLUMN worker_id INTEGER")
    if "worker_session_id" not in rcols:
        cur.execute("ALTER TABLE receipts ADD COLUMN worker_session_id INTEGER")
    if "income_date" not in rcols:
        cur.execute("ALTER TABLE receipts ADD COLUMN income_date TEXT")

    conn.commit()
    create_sync_triggers()


# =====================================================
# MAIN DEBTS SCREEN
# =====================================================
def show_debts(main):

    init_debt_tables()
    clear(main)

    root = ctk.CTkFrame(main)
    root.pack(fill="both", expand=True)

    # ── TOP BAR ──
    top = ctk.CTkFrame(root, height=70, fg_color="#241c11")
    top.pack(fill="x", padx=10, pady=10)
    top.pack_propagate(False)

    ctk.CTkLabel(
        top, text="💳 الديون",
        font=("Tahoma", 24, "bold")
    ).pack(side="left", padx=20)

    btns = ctk.CTkFrame(top, fg_color="transparent")
    btns.pack(side="right", padx=10)

    ctk.CTkButton(
        btns, text="+ دين جديد",
        fg_color="#f5c400", hover_color="#d9a900",
        text_color="#15100a",
        font=("Tahoma", 14, "bold"),
        command=lambda: open_add_debt_panel(root, refresh)
    ).pack(side="left", padx=5)

    # ── SUMMARY STRIP ──
    summary = ctk.CTkFrame(root, fg_color="#2f2517", corner_radius=12)
    summary.pack(fill="x", padx=15, pady=(0, 8))

    total_lbl  = ctk.CTkLabel(summary, text="", font=("Tahoma", 14))
    paid_lbl   = ctk.CTkLabel(summary, text="", font=("Tahoma", 14))
    remain_lbl = ctk.CTkLabel(summary, text="", font=("Tahoma", 14, "bold"))

    total_lbl.pack(side="left",  padx=20, pady=10)
    paid_lbl.pack(side="left",   padx=20, pady=10)
    remain_lbl.pack(side="left", padx=20, pady=10)

    # ── BODY ──
    body = ctk.CTkFrame(root, fg_color="transparent")
    body.pack(fill="both", expand=True)

    left = ctk.CTkScrollableFrame(body, width=260, fg_color="#2f2517")
    left.pack(side="left", fill="y", padx=10, pady=10)

    ctk.CTkLabel(
        left, text="👤 الزبائن",
        font=("Tahoma", 18, "bold")
    ).pack(pady=12)

    right = ctk.CTkScrollableFrame(body, fg_color="#1c160e")
    right.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    selected_customer = {"name": None}

    def refresh():
        show_debts(main)

    def update_summary():
        cur.execute("SELECT COALESCE(SUM(amount),0), COALESCE(SUM(paid),0) FROM debts")
        total, paid = cur.fetchone()
        remain = total - paid
        total_lbl.configure( text=f"إجمالي الديون: {total:,.0f} SYP")
        paid_lbl.configure(  text=f"المدفوع: {paid:,.0f} SYP",    text_color="#f5c400")
        remain_lbl.configure(text=f"المتبقي: {remain:,.0f} SYP",  text_color="#b23b2e" if remain > 0 else "#f5c400")

    update_summary()

    # ── LOAD CUSTOMERS ──
    def load_customers():
        for w in left.winfo_children():
            if not isinstance(w, ctk.CTkLabel):
                w.destroy()

        cur.execute("""
            SELECT customer,
                   SUM(amount) AS total,
                   SUM(paid)   AS paid
            FROM debts
            GROUP BY customer
            ORDER BY (SUM(amount)-SUM(paid)) DESC
        """)
        customers = cur.fetchall()

        for cname, total, paid in customers:
            remain     = total - paid
            is_settled = remain <= 0

            row = ctk.CTkFrame(
                left,
                fg_color="#5a4316" if is_settled else "#3b2e1c",
                corner_radius=10
            )
            row.pack(fill="x", padx=6, pady=4)

            ctk.CTkLabel(
                row, text=cname,
                font=("Tahoma", 14, "bold"),
                wraplength=180
            ).pack(anchor="w", padx=10, pady=(8, 0))

            ctk.CTkLabel(
                row,
                text="✅ مسدد" if is_settled else f"متبقي: {remain:,.0f} SYP",
                text_color="#f5c400" if is_settled else "#b23b2e",
                font=("Tahoma", 12)
            ).pack(anchor="w", padx=10, pady=(0, 8))

            row.bind("<Button-1>", lambda e, n=cname: load_customer_detail(n))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, n=cname: load_customer_detail(n))

    # ── CUSTOMER DETAIL ──
    def load_customer_detail(customer_name):
        selected_customer["name"] = customer_name

        for w in right.winfo_children():
            w.destroy()

        # header
        hdr = ctk.CTkFrame(right, fg_color="#2f2517", corner_radius=12)
        hdr.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            hdr, text=f"👤 {customer_name}",
            font=("Tahoma", 20, "bold")
        ).pack(side="left", padx=15, pady=12)

        ctk.CTkButton(
            hdr, text="+ دفعة جديدة",
            fg_color="#b8860b", hover_color="#9a6f08",
            font=("Tahoma", 13, "bold"),
            command=lambda: open_payment_panel(root, customer_name, load_customer_detail)
        ).pack(side="right", padx=10, pady=10)

        # fetch debts
        cur.execute("""
            SELECT id, amount, paid, note, created_at, receipt_id
            FROM debts
            WHERE customer=?
            ORDER BY created_at DESC
        """, (customer_name,))
        debts = cur.fetchall()

        for debt_id, amount, paid, note, created_at, receipt_id in debts:
            remain     = amount - paid
            is_settled = remain <= 0

            card = ctk.CTkFrame(right, fg_color="#2f2517", corner_radius=12)
            card.pack(fill="x", pady=5)

            # top row: date + status
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=12, pady=(10, 2))

            ctk.CTkLabel(
                top_row,
                text=f"📅 {created_at[:10]}",
                text_color="#e8dcc0", font=("Tahoma", 12)
            ).pack(side="left")

            # receipt badge
            if receipt_id:
                ctk.CTkLabel(
                    top_row,
                    text=f"🧾 فاتورة #{receipt_id}",
                    text_color="#ded38d", font=("Tahoma", 12)
                ).pack(side="left", padx=10)

            status_color = "#f5c400" if is_settled else "#b23b2e"
            status_text  = "✅ مسدد" if is_settled else f"متبقي: {remain:,.0f} SYP"
            ctk.CTkLabel(
                top_row, text=status_text,
                text_color=status_color, font=("Tahoma", 13, "bold")
            ).pack(side="right")

            # mid row: amounts
            mid_row = ctk.CTkFrame(card, fg_color="transparent")
            mid_row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(
                mid_row,
                text=f"الدين: {amount:,.0f} SYP   |   المدفوع: {paid:,.0f} SYP",
                font=("Tahoma", 14)
            ).pack(side="left")

            if note:
                ctk.CTkLabel(
                    card, text=f"📝 {note}",
                    text_color="#e8dcc0", font=("Tahoma", 12)
                ).pack(anchor="w", padx=12, pady=(0, 4))

            # payment history
            cur.execute("""
                SELECT amount, paid_at, note
                FROM debt_payments
                WHERE debt_id=?
                ORDER BY paid_at ASC
            """, (debt_id,))
            payments = cur.fetchall()

            if payments:
                ph = ctk.CTkFrame(card, fg_color="#3b2e1c", corner_radius=8)
                ph.pack(fill="x", padx=12, pady=(4, 10))

                ctk.CTkLabel(
                    ph, text="سجل الدفعات:",
                    font=("Tahoma", 12, "bold"), text_color="#e8dcc0"
                ).pack(anchor="w", padx=8, pady=(6, 2))

                for p_amount, p_date, p_note in payments:
                    p_text = f"  • {p_date[:16]}  →  {p_amount:,.0f} SYP"
                    if p_note:
                        p_text += f"  ({p_note})"
                    ctk.CTkLabel(
                        ph, text=p_text,
                        text_color="#f5c400", font=("Tahoma", 12)
                    ).pack(anchor="w", padx=8, pady=1)

                ctk.CTkFrame(ph, height=6, fg_color="transparent").pack()
            else:
                ctk.CTkFrame(card, height=8, fg_color="transparent").pack()

    load_customers()

    cur.execute("""
        SELECT customer FROM debts
        GROUP BY customer
        ORDER BY SUM(amount)-SUM(paid) DESC
        LIMIT 1
    """)
    first = cur.fetchone()
    if first:
        load_customer_detail(first[0])


# =====================================================
# ADD DEBT PANEL  (manual debt, not from cashier)
# =====================================================
def open_add_debt_panel(root, refresh_callback):

    for w in root.winfo_children():
        if getattr(w, "_is_side_panel", False):
            w.destroy()

    panel = ctk.CTkFrame(root, width=380, fg_color="#2f2517")
    panel._is_side_panel = True
    panel.place(relx=1.0, rely=0, anchor="ne", relheight=1)
    panel.pack_propagate(False)

    hdr = ctk.CTkFrame(panel, fg_color="#241c11", corner_radius=0)
    hdr.pack(fill="x")
    ctk.CTkLabel(hdr, text="+ دين جديد", font=("Tahoma", 18, "bold")).pack(side="left", padx=15, pady=15)
    ctk.CTkButton(
        hdr, text="✕", width=36, height=36,
        fg_color="#b23b2e", hover_color="#7a261f",
        command=panel.destroy
    ).pack(side="right", padx=10, pady=10)

    content = ctk.CTkFrame(panel, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=20, pady=15)

    ctk.CTkLabel(content, text="اسم الزبون", font=("Tahoma", 14, "bold")).pack(anchor="w", pady=(0, 4))

    customer_var = ctk.StringVar()
    customer_entry = ctk.CTkEntry(content, textvariable=customer_var, placeholder_text="اكتب اسم الزبون")
    customer_entry.pack(fill="x", pady=(0, 4))

    suggest_frame = ctk.CTkFrame(content, fg_color="#3b2e1c", corner_radius=8)

    def update_suggestions(*args):
        for w in suggest_frame.winfo_children():
            w.destroy()
        text = customer_var.get().strip()
        if not text:
            suggest_frame.pack_forget()
            return
        cur.execute(
            "SELECT DISTINCT customer FROM debts WHERE customer LIKE ? LIMIT 5",
            (f"%{text}%",)
        )
        results = [r[0] for r in cur.fetchall()]
        if not results:
            suggest_frame.pack_forget()
            return
        suggest_frame.pack(fill="x", pady=(0, 8))
        for name in results:
            ctk.CTkButton(
                suggest_frame, text=name, height=32,
                fg_color="transparent", hover_color="#b8860b",
                anchor="w", font=("Tahoma", 13),
                command=lambda n=name: [customer_var.set(n), suggest_frame.pack_forget()]
            ).pack(fill="x", padx=4, pady=2)

    customer_var.trace_add("write", update_suggestions)

    ctk.CTkLabel(content, text="المبلغ (SYP)", font=("Tahoma", 14, "bold")).pack(anchor="w", pady=(10, 4))
    amount_entry = ctk.CTkEntry(content, placeholder_text="0")
    amount_entry.pack(fill="x", pady=(0, 10))

    ctk.CTkLabel(content, text="ملاحظة (اختياري)", font=("Tahoma", 14, "bold")).pack(anchor="w", pady=(0, 4))
    note_entry = ctk.CTkEntry(content, placeholder_text="سبب الدين...")
    note_entry.pack(fill="x", pady=(0, 20))

    def save():
        customer = customer_var.get().strip()
        if not customer:
            messagebox.showwarning("تنبيه", "أدخل اسم الزبون")
            return
        try:
            amount = float(amount_entry.get())
            if amount <= 0:
                raise ValueError
        except:
            messagebox.showwarning("تنبيه", "أدخل مبلغًا صحيحًا")
            return

        note = note_entry.get().strip() or None
        created_at = datetime.now().isoformat()
        worker_id = current_worker.get("id") if current_worker else None
        worker_session_id = current_session.get("id") if current_session else None
        notification_watermark = sync_queue_watermark(conn)
        # Manual debts also receive a held receipt, so they become income only
        # after the customer fully settles them.
        cur.execute("""
            INSERT INTO receipts (
                date, total, status, customer, worker_id, worker_session_id, income_date
            ) VALUES (?, ?, 'debt', ?, ?, ?, NULL)
        """, (created_at, amount, customer, worker_id, worker_session_id))
        receipt_id = cur.lastrowid
        cur.execute("""
            INSERT INTO debts (customer, amount, paid, note, created_at, receipt_id)
            VALUES (?, ?, 0, ?, ?, ?)
        """, (customer, amount, note, created_at, receipt_id))
        # Notify for the debt itself, not for its implementation detail: the
        # held receipt created alongside it.
        suppress_notifications_since(
            conn, notification_watermark, keep_tables={"debts"}
        )
        conn.commit()
        panel.destroy()
        refresh_callback()

    ctk.CTkButton(
        content, text="💾 حفظ الدين",
        height=48, corner_radius=12,
        fg_color="#f5c400", hover_color="#d9a900",
        text_color="#15100a",
        font=("Tahoma", 16, "bold"),
        command=save
    ).pack(fill="x")


# =====================================================
# PAYMENT PANEL
# — records payment, updates debt.paid,
#   and marks receipt as 'paid' when fully settled
# =====================================================
def open_payment_panel(root, customer_name, reload_callback):

    for w in root.winfo_children():
        if getattr(w, "_is_side_panel", False):
            w.destroy()

    panel = ctk.CTkFrame(root, width=400, fg_color="#2f2517")
    panel._is_side_panel = True
    panel.place(relx=1.0, rely=0, anchor="ne", relheight=1)
    panel.pack_propagate(False)

    hdr = ctk.CTkFrame(panel, fg_color="#241c11", corner_radius=0)
    hdr.pack(fill="x")
    ctk.CTkLabel(
        hdr, text=f"💵 دفعة — {customer_name}",
        font=("Tahoma", 16, "bold"), wraplength=300
    ).pack(side="left", padx=15, pady=15)
    ctk.CTkButton(
        hdr, text="✕", width=36, height=36,
        fg_color="#b23b2e", hover_color="#7a261f",
        command=panel.destroy
    ).pack(side="right", padx=10, pady=10)

    content = ctk.CTkFrame(panel, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=20, pady=15)

    # fetch unsettled debts for this customer
    cur.execute("""
        SELECT id, amount, paid, note, created_at, receipt_id
        FROM debts
        WHERE customer=? AND (amount - paid) > 0
        ORDER BY created_at ASC
    """, (customer_name,))
    unsettled = cur.fetchall()

    if not unsettled:
        ctk.CTkLabel(
            content, text="✅ لا توجد ديون متبقية",
            text_color="#f5c400", font=("Tahoma", 14)
        ).pack(pady=30)
        return

    ctk.CTkLabel(
        content, text="اختر الدين للتسديد",
        font=("Tahoma", 14, "bold")
    ).pack(anchor="w", pady=(0, 6))

    selected_debt = {"id": None, "remain": 0, "receipt_id": None}

    debt_info_lbl = ctk.CTkLabel(
        content, text="",
        text_color="#ded38d", font=("Tahoma", 13, "bold")
    )
    debt_info_lbl.pack(anchor="w", pady=(0, 8))

    debt_list = ctk.CTkScrollableFrame(
        content, height=180, fg_color="#3b2e1c", corner_radius=10
    )
    debt_list.pack(fill="x", pady=(0, 12))

    for debt_id, amount, paid, note, created_at, receipt_id in unsettled:
        remain = amount - paid
        label  = f"📅 {created_at[:10]}  —  متبقي: {remain:,.0f} SYP"
        if receipt_id:
            label += f"  (فاتورة #{receipt_id})"
        if note:
            label += f"\n   📝 {note}"

        def select_debt(did=debt_id, r=remain, rid=receipt_id):
            selected_debt.update({"id": did, "remain": r, "receipt_id": rid})
            debt_info_lbl.configure(text=f"المتبقي: {r:,.0f} SYP")

        ctk.CTkButton(
            debt_list, text=label,
            height=42, anchor="w",
            fg_color="transparent", hover_color="#b8860b",
            font=("Tahoma", 12),
            command=select_debt
        ).pack(fill="x", padx=6, pady=3)

    ctk.CTkLabel(
        content, text="مبلغ الدفعة (SYP)",
        font=("Tahoma", 14, "bold")
    ).pack(anchor="w", pady=(0, 4))

    amount_entry = ctk.CTkEntry(content, placeholder_text="0")
    amount_entry.pack(fill="x", pady=(0, 10))

    ctk.CTkLabel(
        content, text="ملاحظة (اختياري)",
        font=("Tahoma", 14, "bold")
    ).pack(anchor="w", pady=(0, 4))

    note_entry = ctk.CTkEntry(content, placeholder_text="...")
    note_entry.pack(fill="x", pady=(0, 6))

    def pay_full():
        if not selected_debt["id"]:
            messagebox.showwarning("تنبيه", "اختر الدين أولاً")
            return
        amount_entry.delete(0, "end")
        amount_entry.insert(0, str(selected_debt["remain"]))

    ctk.CTkButton(
        content, text="تسديد كامل",
        height=34, corner_radius=8,
        fg_color="#241c11", hover_color="#3a2d1a",
        font=("Tahoma", 13),
        command=pay_full
    ).pack(fill="x", pady=(0, 16))

    def save():
        if not selected_debt["id"]:
            messagebox.showwarning("تنبيه", "اختر الدين أولاً")
            return
        try:
            pay_amount = float(amount_entry.get())
            if pay_amount <= 0:
                raise ValueError
        except:
            messagebox.showwarning("تنبيه", "أدخل مبلغًا صحيحًا")
            return
        if pay_amount > selected_debt["remain"]:
            messagebox.showwarning("تنبيه", "المبلغ أكبر من المتبقي")
            return

        note = note_entry.get().strip() or None
        debt_id = selected_debt["id"]
        record_debt_payment(debt_id, pay_amount, note)
        panel.destroy()
        reload_callback(customer_name)

    ctk.CTkButton(
        content, text="💾 تسجيل الدفعة",
        height=48, corner_radius=12,
        fg_color="#f5c400", hover_color="#d9a900",
        text_color="#15100a",
        font=("Tahoma", 16, "bold"),
        command=save
    ).pack(fill="x")
