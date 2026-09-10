from datetime import date, datetime
from tkinter import messagebox

import customtkinter as ctk

from adb import (
    conn,
    create_worker,
    cur,
    get_active_workers,
    get_all_workers,
    get_worker_logs,
    get_worker_session_totals,
    start_worker_session,
)
from state import current_session, current_worker
from utils import clear


def _money(value):
    return f"{value or 0:,.0f} SYP"


def show_worker_login(main, on_success):
    """Worker sign-in with no shift or schedule selection."""
    clear(main)
    root = ctk.CTkFrame(main)
    root.pack(fill="both", expand=True)

    ctk.CTkLabel(root, text="👷 تسجيل دخول العامل", font=("Tahoma", 30, "bold")).pack(pady=(60, 12))
    ctk.CTkLabel(
        root,
        text="اختر اسمك لبدء أو متابعة سجل عمل اليوم",
        text_color="#e8dcc0",
        font=("Tahoma", 17),
    ).pack(pady=(0, 24))

    workers = get_active_workers()
    if not workers:
        ctk.CTkLabel(root, text="لا يوجد عمال نشطون", text_color="#b23b2e", font=("Tahoma", 18)).pack(pady=20)
        return

    worker_map = {name: worker_id for worker_id, name in workers}
    worker_var = ctk.StringVar(value=workers[0][1])
    ctk.CTkOptionMenu(root, values=list(worker_map), variable=worker_var, width=340, height=48).pack(pady=12)

    def sign_in():
        worker_name = worker_var.get()
        worker_id = worker_map[worker_name]
        session_id, start_time, work_date = start_worker_session(worker_id)
        current_worker.clear()
        current_worker.update({"id": worker_id, "name": worker_name})
        current_session.clear()
        current_session.update({
            "id": session_id,
            "worker_id": worker_id,
            "work_date": work_date,
            "start_time": start_time,
            **get_worker_session_totals(session_id),
        })
        on_success()

    ctk.CTkButton(
        root,
        text="▶ بدء العمل",
        height=54,
        width=340,
        fg_color="#f5c400",
        hover_color="#d9a900",
        text_color="#15100a",
        font=("Tahoma", 18, "bold"),
        command=sign_in,
    ).pack(pady=28)


def show_workers(main, refresh_callback=None):
    """Owner worker management and selectable permanent daily logs."""
    clear(main)
    root = ctk.CTkFrame(main, fg_color="#15100a")
    root.pack(fill="both", expand=True)

    header = ctk.CTkFrame(root, fg_color="#2f2517")
    header.pack(fill="x", padx=12, pady=12)
    ctk.CTkLabel(header, text="👷 العمال وسجلات العمل اليومية", font=("Tahoma", 25, "bold")).pack(
        side="right", padx=18, pady=15
    )

    add_frame = ctk.CTkFrame(header, fg_color="transparent")
    add_frame.pack(side="left", padx=12)
    name_entry = ctk.CTkEntry(add_frame, placeholder_text="اسم العامل الجديد", width=220)
    name_entry.pack(side="left", padx=6)

    def add_worker():
        name = name_entry.get().strip()
        if not name:
            return
        try:
            create_worker(name)
        except Exception:
            messagebox.showwarning("تنبيه", "اسم العامل موجود مسبقاً")
            return
        show_workers(main, refresh_callback)

    ctk.CTkButton(add_frame, text="+ إضافة عامل", command=add_worker, fg_color="#f5c400", text_color="#15100a").pack(
        side="left", padx=6
    )

    body = ctk.CTkFrame(root, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    workers_panel = ctk.CTkScrollableFrame(body, width=300, fg_color="#241c11")
    workers_panel.pack(side="right", fill="y", padx=(8, 0))
    ctk.CTkLabel(workers_panel, text="إدارة العمال", font=("Tahoma", 19, "bold")).pack(pady=10)

    def toggle_worker(worker_id, active):
        cur.execute("UPDATE workers SET active = ? WHERE id = ?", (0 if active else 1, worker_id))
        conn.commit()
        show_workers(main, refresh_callback)

    for worker_id, worker_name, active in get_all_workers():
        card = ctk.CTkFrame(workers_panel, fg_color="#2f2517")
        card.pack(fill="x", padx=6, pady=5)
        ctk.CTkLabel(card, text=worker_name, font=("Tahoma", 15, "bold")).pack(side="right", padx=10, pady=10)
        ctk.CTkButton(
            card,
            text="نشط" if active else "متوقف",
            width=76,
            fg_color="#4d7c45" if active else "#8f2f25",
            command=lambda wid=worker_id, enabled=active: toggle_worker(wid, enabled),
        ).pack(side="left", padx=8, pady=7)

    logs = get_worker_logs()
    available_days = sorted({row["work_date"] for row in logs} | {date.today().isoformat()}, reverse=True)
    selected_day = ctk.StringVar(value=available_days[0])

    log_panel = ctk.CTkScrollableFrame(body, fg_color="#1c160e")
    log_panel.pack(side="left", fill="both", expand=True)

    controls = ctk.CTkFrame(log_panel, fg_color="#2f2517")
    controls.pack(fill="x", padx=8, pady=8)
    ctk.CTkLabel(controls, text="اختر اليوم", font=("Tahoma", 15, "bold")).pack(side="right", padx=10)

    cards_holder = ctk.CTkFrame(log_panel, fg_color="transparent")
    cards_holder.pack(fill="both", expand=True, padx=8, pady=4)

    def render_day(_choice=None):
        for widget in cards_holder.winfo_children():
            widget.destroy()
        rows = [row for row in logs if row["work_date"] == selected_day.get()]
        merged = {
            "receipts": sum(row["receipts"] for row in rows),
            "items": sum(row["items"] for row in rows),
            "revenue": sum(row["revenue"] for row in rows),
            "held": sum(row["held_revenue"] for row in rows),
        }
        summary = ctk.CTkFrame(cards_holder, fg_color="#5a4316", corner_radius=12)
        summary.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            summary,
            text=(f"المجموع لكل العمال — فواتير: {merged['receipts']} | عناصر: {merged['items']:g} | "
                  f"دخل مستلم: {_money(merged['revenue'])} | ديون معلقة: {_money(merged['held'])}"),
            font=("Tahoma", 15, "bold"),
        ).pack(padx=12, pady=14)

        if not rows:
            ctk.CTkLabel(cards_holder, text="لا توجد سجلات عمل لهذا اليوم", text_color="gray").pack(pady=35)
            return

        for row in rows:
            start = row["start_time"][11:16] if row["start_time"] else "-"
            end = row["end_time"][11:16] if row["end_time"] else "مستمر"
            card = ctk.CTkFrame(cards_holder, fg_color="#2f2517", corner_radius=12)
            card.pack(fill="x", pady=5)
            ctk.CTkLabel(card, text=row["worker_name"], font=("Tahoma", 18, "bold")).pack(
                anchor="e", padx=14, pady=(10, 2)
            )
            ctk.CTkLabel(
                card,
                text=(f"{start} → {end} | فواتير: {row['receipts']} | عناصر: {row['items']:g} | "
                      f"دخل: {_money(row['revenue'])} | معلق: {_money(row['held_revenue'])}"),
                text_color="#ded38d",
                font=("Tahoma", 13),
            ).pack(anchor="e", padx=14, pady=(0, 10))

    ctk.CTkOptionMenu(
        controls, values=available_days, variable=selected_day, command=render_day, width=160
    ).pack(side="right", padx=8, pady=8)
    render_day()
