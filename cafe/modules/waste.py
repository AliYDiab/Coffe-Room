import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from adb import cur, conn, create_sync_triggers
from utils import clear


# =====================================================
# INIT TABLES
# =====================================================
def init_waste_tables():
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS waste_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id     INTEGER,
            item_name   TEXT    NOT NULL,
            quantity    REAL    NOT NULL,
            reason      TEXT,
            logged_at   TEXT    NOT NULL
        );
    """)
    conn.commit()
    create_sync_triggers()


# =====================================================
# MAIN WASTE SCREEN
# =====================================================
def show_waste(main):

    init_waste_tables()
    clear(main)

    root = ctk.CTkFrame(main)
    root.pack(fill="both", expand=True)

    # ── TOP BAR ──
    top = ctk.CTkFrame(root, height=70, fg_color="#241c11")
    top.pack(fill="x", padx=10, pady=10)
    top.pack_propagate(False)

    ctk.CTkLabel(
        top, text="🗑️ الهدر",
        font=("Tahoma", 24, "bold")
    ).pack(side="left", padx=20)

    btns = ctk.CTkFrame(top, fg_color="transparent")
    btns.pack(side="right", padx=10)

    ctk.CTkButton(
        btns, text="+ تسجيل هدر",
        fg_color="#b23b2e", hover_color="#7a261f",
        font=("Tahoma", 14, "bold"),
        command=lambda: open_add_waste_panel(root, refresh)
    ).pack(side="left", padx=5)

    # ── TABS: سجل / إحصائيات ──
    tab_var = ctk.StringVar(value="log")

    tab_bar = ctk.CTkFrame(root, fg_color="#2f2517", corner_radius=0)
    tab_bar.pack(fill="x", padx=10, pady=(0, 5))

    body = ctk.CTkFrame(root, fg_color="transparent")
    body.pack(fill="both", expand=True)

    def refresh():
        show_waste(main)

    def show_tab(tab):
        tab_var.set(tab)
        for w in body.winfo_children():
            w.destroy()
        if tab == "log":
            load_log_tab()
        else:
            load_stats_tab()

    ctk.CTkButton(
        tab_bar, text="📋 سجل الهدر",
        width=160, height=38, corner_radius=0,
        fg_color="#3b2e1c", hover_color="#b8860b",
        font=("Tahoma", 14, "bold"),
        command=lambda: show_tab("log")
    ).pack(side="left", padx=2, pady=6)

    ctk.CTkButton(
        tab_bar, text="📊 إحصائيات",
        width=160, height=38, corner_radius=0,
        fg_color="#3b2e1c", hover_color="#b8860b",
        font=("Tahoma", 14, "bold"),
        command=lambda: show_tab("stats")
    ).pack(side="left", padx=2, pady=6)

    # =====================================================
    # LOG TAB
    # =====================================================
    def load_log_tab():
        frame = ctk.CTkScrollableFrame(body, fg_color="#1c160e")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        cur.execute("""
            SELECT item_name, quantity, reason, logged_at
            FROM waste_log
            ORDER BY logged_at DESC
        """)
        rows = cur.fetchall()

        if not rows:
            ctk.CTkLabel(
                frame, text="لا يوجد سجل هدر بعد",
                text_color="#e8dcc0", font=("Tahoma", 16)
            ).pack(pady=40)
            return

        # header row
        hdr = ctk.CTkFrame(frame, fg_color="#2f2517", corner_radius=8)
        hdr.pack(fill="x", pady=(0, 4))

        for txt, w in [("العنصر", 200), ("الكمية", 100), ("السبب", 260), ("التاريخ", 160)]:
            ctk.CTkLabel(
                hdr, text=txt, width=w,
                font=("Tahoma", 13, "bold"),
                text_color="#e8dcc0"
            ).pack(side="left", padx=8, pady=8)

        for item_name, quantity, reason, logged_at in rows:
            row = ctk.CTkFrame(frame, fg_color="#2f2517", corner_radius=8)
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(row, text=item_name,  width=200, font=("Tahoma", 13, "bold"), anchor="w").pack(side="left", padx=8, pady=8)
            ctk.CTkLabel(row, text=str(quantity), width=100, font=("Tahoma", 13), text_color="#ded38d", anchor="w").pack(side="left", padx=8)
            ctk.CTkLabel(row, text=reason or "—", width=260, font=("Tahoma", 13), text_color="#e8dcc0", anchor="w", wraplength=240).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=logged_at[:16], width=160, font=("Tahoma", 12), text_color="#a89462", anchor="w").pack(side="left", padx=8)

    # =====================================================
    # STATS TAB
    # =====================================================
    def load_stats_tab():
        frame = ctk.CTkScrollableFrame(body, fg_color="#1c160e")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ── total summary ──
        cur.execute("SELECT COUNT(*), COALESCE(SUM(quantity), 0) FROM waste_log")
        total_entries, total_qty = cur.fetchone()

        summary = ctk.CTkFrame(frame, fg_color="#2f2517", corner_radius=12)
        summary.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            summary,
            text=f"إجمالي تسجيلات الهدر: {total_entries}   |   إجمالي الكميات: {total_qty:g}",
            font=("Tahoma", 15, "bold")
        ).pack(padx=20, pady=14)

        # ── top wasted items ──
        ctk.CTkLabel(
            frame, text="🏆 أكثر العناصر هدراً",
            font=("Tahoma", 17, "bold")
        ).pack(anchor="w", padx=5, pady=(0, 8))

        cur.execute("""
            SELECT item_name,
                   COUNT(*)        AS entries,
                   SUM(quantity)   AS total_qty
            FROM waste_log
            GROUP BY item_name
            ORDER BY total_qty DESC
            LIMIT 10
        """)
        top_items = cur.fetchall()

        if not top_items:
            ctk.CTkLabel(frame, text="لا توجد بيانات", text_color="#e8dcc0").pack(pady=20)
            return

        max_qty = top_items[0][2] if top_items else 1

        for rank, (item_name, entries, qty) in enumerate(top_items, 1):
            card = ctk.CTkFrame(frame, fg_color="#2f2517", corner_radius=10)
            card.pack(fill="x", pady=4)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=12, pady=(10, 4))

            rank_color = ["#ded38d", "#e8dcc0", "#a77910"] if rank <= 3 else ["#a89462"]
            ctk.CTkLabel(
                top_row,
                text=f"#{rank}",
                width=36,
                font=("Tahoma", 14, "bold"),
                text_color=rank_color[min(rank - 1, len(rank_color) - 1)]
            ).pack(side="left")

            ctk.CTkLabel(
                top_row, text=item_name,
                font=("Tahoma", 15, "bold")
            ).pack(side="left", padx=8)

            ctk.CTkLabel(
                top_row,
                text=f"{qty:g} وحدة  ({entries} مرة)",
                text_color="#ded38d",
                font=("Tahoma", 13)
            ).pack(side="right")

            # progress bar
            bar_bg = ctk.CTkFrame(card, fg_color="#3b2e1c", height=10, corner_radius=5)
            bar_bg.pack(fill="x", padx=12, pady=(0, 10))
            bar_bg.pack_propagate(False)

            fill_pct = qty / max_qty
            bar_fill = ctk.CTkFrame(
                bar_bg, height=10,
                fg_color="#b23b2e" if rank == 1 else "#ded38d",
                corner_radius=5
            )
            bar_fill.place(relx=0, rely=0, relwidth=fill_pct, relheight=1)

        # ── reasons breakdown ──
        ctk.CTkLabel(
            frame, text="📝 أسباب الهدر",
            font=("Tahoma", 17, "bold")
        ).pack(anchor="w", padx=5, pady=(16, 8))

        cur.execute("""
            SELECT COALESCE(reason, 'بدون سبب'),
                   COUNT(*) AS cnt,
                   SUM(quantity) AS total_qty
            FROM waste_log
            GROUP BY reason
            ORDER BY cnt DESC
        """)
        reasons = cur.fetchall()

        for reason, cnt, qty in reasons:
            row = ctk.CTkFrame(frame, fg_color="#2f2517", corner_radius=8)
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(
                row, text=reason,
                font=("Tahoma", 13),
                anchor="w", wraplength=400
            ).pack(side="left", padx=12, pady=8)

            ctk.CTkLabel(
                row,
                text=f"{cnt} مرة  —  {qty:g} وحدة",
                text_color="#e8dcc0",
                font=("Tahoma", 12)
            ).pack(side="right", padx=12)

    # start on log tab
    load_log_tab()


# =====================================================
# ADD WASTE PANEL
# =====================================================
def open_add_waste_panel(root, refresh_callback):

    for w in root.winfo_children():
        if getattr(w, "_is_side_panel", False):
            w.destroy()

    panel = ctk.CTkFrame(root, width=400, fg_color="#2f2517")
    panel._is_side_panel = True
    panel.place(relx=1.0, rely=0, anchor="ne", relheight=1)
    panel.pack_propagate(False)

    # header
    hdr = ctk.CTkFrame(panel, fg_color="#241c11", corner_radius=0)
    hdr.pack(fill="x")
    ctk.CTkLabel(hdr, text="🗑️ تسجيل هدر", font=("Tahoma", 18, "bold")).pack(side="left", padx=15, pady=15)
    ctk.CTkButton(
        hdr, text="✕", width=36, height=36,
        fg_color="#b23b2e", hover_color="#7a261f",
        command=panel.destroy
    ).pack(side="right", padx=10, pady=10)

    content = ctk.CTkFrame(panel, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=20, pady=15)

    # ── item source: inventory item or free text ──
    ctk.CTkLabel(content, text="مصدر العنصر", font=("Tahoma", 14, "bold")).pack(anchor="w", pady=(0, 6))

    source_var = ctk.StringVar(value="inventory")
    src_frame = ctk.CTkFrame(content, fg_color="transparent")
    src_frame.pack(fill="x", pady=(0, 10))

    ctk.CTkRadioButton(
        src_frame, text="من المخزون",
        variable=source_var, value="inventory",
        command=lambda: toggle_source()
    ).pack(side="left", padx=(0, 20))

    ctk.CTkRadioButton(
        src_frame, text="إدخال يدوي",
        variable=source_var, value="manual",
        command=lambda: toggle_source()
    ).pack(side="left")

    # inventory picker
    inv_frame = ctk.CTkFrame(content, fg_color="transparent")
    inv_frame.pack(fill="x")

    selected_item = {"id": None, "name": None}
    item_info_lbl = ctk.CTkLabel(inv_frame, text="لم يتم اختيار عنصر", text_color="#e8dcc0", font=("Tahoma", 12))
    item_info_lbl.pack(anchor="w", pady=(0, 4))

    # fetch all items
    cur.execute("SELECT id, name, type FROM items ORDER BY name")
    all_items = cur.fetchall()

    search_var = ctk.StringVar()
    search_entry = ctk.CTkEntry(inv_frame, textvariable=search_var, placeholder_text="🔍 بحث...")
    search_entry.pack(fill="x", pady=(0, 4))

    item_list_frame = ctk.CTkScrollableFrame(inv_frame, height=160, fg_color="#3b2e1c", corner_radius=8)
    item_list_frame.pack(fill="x", pady=(0, 8))

    def populate_item_list(filter_text=""):
        for w in item_list_frame.winfo_children():
            w.destroy()
        for iid, iname, itype in all_items:
            if filter_text.lower() not in iname.lower():
                continue
            ctk.CTkButton(
                item_list_frame, text=iname,
                height=32, anchor="w",
                fg_color="transparent", hover_color="#b8860b",
                font=("Tahoma", 13),
                command=lambda i=iid, n=iname: [
                    selected_item.update({"id": i, "name": n}),
                    item_info_lbl.configure(text=f"✅ {n}")
                ]
            ).pack(fill="x", padx=4, pady=2)

    populate_item_list()
    search_var.trace_add("write", lambda *a: populate_item_list(search_var.get()))

    # manual entry
    manual_frame = ctk.CTkFrame(content, fg_color="transparent")
    manual_entry = ctk.CTkEntry(manual_frame, placeholder_text="اسم العنصر يدوياً")
    manual_entry.pack(fill="x")

    def toggle_source():
        if source_var.get() == "inventory":
            manual_frame.pack_forget()
            inv_frame.pack(fill="x")
        else:
            inv_frame.pack_forget()
            manual_frame.pack(fill="x", pady=(0, 8))
            selected_item["id"] = None
            selected_item["name"] = None

    # ── quantity ──
    ctk.CTkLabel(content, text="الكمية", font=("Tahoma", 14, "bold")).pack(anchor="w", pady=(10, 4))
    qty_entry = ctk.CTkEntry(content, placeholder_text="0")
    qty_entry.pack(fill="x", pady=(0, 10))

    # ── reason ──
    ctk.CTkLabel(content, text="السبب (اختياري)", font=("Tahoma", 14, "bold")).pack(anchor="w", pady=(0, 4))

    reasons_frame = ctk.CTkFrame(content, fg_color="transparent")
    reasons_frame.pack(fill="x", pady=(0, 6))

    quick_reasons = ["تلف", "انتهاء صلاحية", "خطأ في الطلب", "سقوط / كسر", "أخرى"]
    reason_var = ctk.StringVar()

    for r in quick_reasons:
        ctk.CTkButton(
            reasons_frame, text=r,
            height=30, corner_radius=8,
            fg_color="#3b2e1c", hover_color="#b8860b",
            font=("Tahoma", 12),
            command=lambda rv=r: reason_var.set(rv) or reason_entry.delete(0, "end") or reason_entry.insert(0, rv)
        ).pack(side="left", padx=3, pady=2)

    reason_entry = ctk.CTkEntry(content, textvariable=reason_var, placeholder_text="أو اكتب السبب...")
    reason_entry.pack(fill="x", pady=(4, 20))

    def save():
        # resolve item name
        if source_var.get() == "inventory":
            if not selected_item["name"]:
                messagebox.showwarning("تنبيه", "اختر عنصراً من المخزون")
                return
            item_name = selected_item["name"]
            item_id   = selected_item["id"]
        else:
            item_name = manual_entry.get().strip()
            if not item_name:
                messagebox.showwarning("تنبيه", "أدخل اسم العنصر")
                return
            item_id = None

        try:
            qty = float(qty_entry.get())
            if qty <= 0:
                raise ValueError
        except:
            messagebox.showwarning("تنبيه", "أدخل كمية صحيحة")
            return

        reason = reason_var.get().strip() or None

        # log waste
        cur.execute("""
            INSERT INTO waste_log (item_id, item_name, quantity, reason, logged_at)
            VALUES (?, ?, ?, ?, ?)
        """, (item_id, item_name, qty, reason, datetime.now().isoformat()))

        conn.commit()
        panel.destroy()
        refresh_callback()

    ctk.CTkButton(
        content, text="💾 تسجيل الهدر",
        height=48, corner_radius=12,
        fg_color="#b23b2e", hover_color="#7a261f",
        font=("Tahoma", 16, "bold"),
        command=save
    ).pack(fill="x")
