from datetime import datetime

import customtkinter as ctk

from adb import conn, cur
from utils import clear


def init_expense_table():
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


def _money(value):
    return f"{value or 0:,.0f} ل.س"


def show_expenses(main):
    init_expense_table()
    clear(main)

    root = ctk.CTkFrame(main, fg_color="#15100a")
    root.pack(fill="both", expand=True)

    form = ctk.CTkFrame(root, fg_color="#241c11", corner_radius=8)
    form.pack(fill="x", padx=12, pady=12)

    ctk.CTkLabel(
        form,
        text="إضافة مصروف",
        font=("Tahoma", 22, "bold"),
        anchor="e",
    ).pack(anchor="e", padx=14, pady=(12, 8))

    fields = ctk.CTkFrame(form, fg_color="transparent")
    fields.pack(fill="x", padx=12, pady=8)

    category_var = ctk.StringVar(value="كهرباء")
    amount_var = ctk.StringVar()
    vendor_var = ctk.StringVar()
    note_var = ctk.StringVar()

    categories = ["غاز", "ماء", "كهرباء", "إيجار", "مستلزمات", "صيانة", "مكونات", "أخرى"]

    def labeled_field(parent, label, build_widget):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(side="right", padx=5)
        ctk.CTkLabel(box, text=label, anchor="e", font=("Tahoma", 12, "bold")).pack(fill="x", pady=(0, 3))
        widget = build_widget(box)
        widget.pack(fill="x")
        return box

    labeled_field(fields, "نوع المصروف", lambda box: ctk.CTkOptionMenu(box, variable=category_var, values=categories, width=150))
    labeled_field(fields, "المبلغ", lambda box: ctk.CTkEntry(box, textvariable=amount_var, placeholder_text="مثال: 50000", width=140))
    labeled_field(fields, "الجهة / المورد", lambda box: ctk.CTkEntry(box, textvariable=vendor_var, placeholder_text="مثال: شركة الكهرباء", width=180))
    labeled_field(fields, "ملاحظة", lambda box: ctk.CTkEntry(box, textvariable=note_var, placeholder_text="تفاصيل اختيارية", width=260))

    message = ctk.CTkLabel(form, text="", text_color="#f5c400")
    message.pack(anchor="e", padx=14, pady=(0, 8))

    list_frame = ctk.CTkScrollableFrame(root, fg_color="#15100a")
    list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def open_edit_expense(expense_id, expense_date, category, amount, vendor, note):
        win = ctk.CTkToplevel(root)
        win.title("تعديل مصروف")
        win.geometry("430x420")
        win.attributes("-topmost", True)
        win.focus_force()
        win.grab_set()

        ctk.CTkLabel(win, text=f"تعديل مصروف #{expense_id}", font=("Tahoma", 20, "bold")).pack(pady=(18, 10))

        date_var = ctk.StringVar(value=expense_date or datetime.now().isoformat())
        edit_category_var = ctk.StringVar(value=category or "أخرى")
        edit_amount_var = ctk.StringVar(value=str(amount or ""))
        edit_vendor_var = ctk.StringVar(value=vendor or "")
        edit_note_var = ctk.StringVar(value=note or "")

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=8)

        def labeled_edit(label, widget):
            ctk.CTkLabel(body, text=label, anchor="e", font=("Tahoma", 12, "bold")).pack(fill="x", pady=(6, 2))
            widget.pack(fill="x")

        labeled_edit("التاريخ", ctk.CTkEntry(body, textvariable=date_var, placeholder_text="2026-06-28"))
        labeled_edit("نوع المصروف", ctk.CTkOptionMenu(body, variable=edit_category_var, values=categories))
        labeled_edit("المبلغ", ctk.CTkEntry(body, textvariable=edit_amount_var, placeholder_text="مثال: 50000"))
        labeled_edit("الجهة / المورد", ctk.CTkEntry(body, textvariable=edit_vendor_var, placeholder_text="مثال: شركة الكهرباء"))
        labeled_edit("ملاحظة", ctk.CTkEntry(body, textvariable=edit_note_var, placeholder_text="تفاصيل اختيارية"))

        edit_message = ctk.CTkLabel(body, text="", text_color="#f5c400")
        edit_message.pack(anchor="e", pady=(4, 8))

        def save_edit():
            try:
                new_amount = float(edit_amount_var.get().strip())
            except ValueError:
                edit_message.configure(text="أدخل مبلغاً صحيحاً")
                return

            if new_amount <= 0:
                edit_message.configure(text="يجب أن يكون المبلغ أكبر من صفر")
                return

            cur.execute(
                """
                UPDATE expenses
                SET date=?, category=?, amount=?, vendor=?, note=?
                WHERE id=?
                """,
                (
                    date_var.get().strip() or datetime.now().isoformat(),
                    edit_category_var.get(),
                    new_amount,
                    edit_vendor_var.get().strip() or None,
                    edit_note_var.get().strip() or None,
                    expense_id,
                ),
            )
            conn.commit()
            win.destroy()
            message.configure(text="تم تعديل المصروف")
            load_expenses()

        ctk.CTkButton(
            body,
            text="حفظ التعديلات",
            command=save_edit,
            height=40,
            fg_color="#8a5a1f",
            hover_color="#a66c25",
        ).pack(fill="x", pady=(6, 4))

    def load_expenses():
        for widget in list_frame.winfo_children():
            widget.destroy()

        cur.execute("""
            SELECT id, date, category, amount, vendor, note, source
            FROM expenses
            ORDER BY date DESC, id DESC
            LIMIT 200
        """)
        rows = cur.fetchall()

        total = sum(row[3] or 0 for row in rows)
        ctk.CTkLabel(
            list_frame,
            text=f"إجمالي المصروفات المعروضة: {_money(total)}",
            text_color="#f5c400",
            font=("Tahoma", 16, "bold"),
            anchor="e",
        ).pack(fill="x", padx=8, pady=8)

        if not rows:
            ctk.CTkLabel(list_frame, text="لا توجد مصروفات بعد", text_color="#e8dcc0").pack(pady=30)
            return

        for expense_id, expense_date, category, amount, vendor, note, source in rows:
            card = ctk.CTkFrame(list_frame, fg_color="#2f2517", corner_radius=8)
            card.pack(fill="x", padx=8, pady=5)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(top, text=_money(amount), text_color="#ffb36b", font=("Tahoma", 16, "bold")).pack(side="left")
            ctk.CTkLabel(top, text=f"{category}  #{expense_id}", text_color="#fff8e8", font=("Tahoma", 14, "bold")).pack(side="right")
            ctk.CTkButton(
                top,
                text="تعديل",
                width=70,
                height=28,
                fg_color="#5a4528",
                hover_color="#725a34",
                command=lambda eid=expense_id, d=expense_date, c=category, a=amount, v=vendor, n=note: open_edit_expense(eid, d, c, a, v, n),
            ).pack(side="right", padx=8)

            details = " | ".join(part for part in [expense_date, vendor, note, source] if part)
            ctk.CTkLabel(card, text=details, text_color="#c9b891", anchor="e", justify="right").pack(
                fill="x", padx=10, pady=(0, 8)
            )

    def save_expense():
        try:
            amount = float(amount_var.get().strip())
        except ValueError:
            message.configure(text="أدخل مبلغاً صحيحاً")
            return

        if amount <= 0:
            message.configure(text="يجب أن يكون المبلغ أكبر من صفر")
            return

        cur.execute(
            """
            INSERT INTO expenses (date, category, amount, vendor, note, source, created_at)
            VALUES (?, ?, ?, ?, ?, 'desktop', ?)
            """,
            (
                datetime.now().isoformat(),
                category_var.get(),
                amount,
                vendor_var.get().strip() or None,
                note_var.get().strip() or None,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        amount_var.set("")
        vendor_var.set("")
        note_var.set("")
        message.configure(text="تم حفظ المصروف")
        load_expenses()

    ctk.CTkButton(
        form,
        text="حفظ المصروف",
        command=save_expense,
        width=150,
        height=38,
        fg_color="#8a5a1f",
        hover_color="#a66c25",
    ).pack(anchor="e", padx=14, pady=(0, 12))

    load_expenses()
