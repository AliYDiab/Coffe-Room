import os
import sys
from datetime import datetime
from threading import Thread

import tkinter as tk
import customtkinter as ctk

import state
from firebase_sync import main as syncing
from adb import init_db, cur, get_conn
from modules.cashier import show_cashier
from modules.receipts import show_receipts
from modules.analytics import show_analytics
from modules.inventory import show_inventory
from modules.ingredients import show_ingredients
from modules.debt import show_debts
from modules.waste import show_waste
from modules.expenses import show_expenses
from modules.workers import show_workers, show_worker_login
from modules.worker_ratings import show_worker_ratings
from modules.backups import show_backups
from backup_manager import create_backup
from updater import check_for_updates
from state import current_worker, current_session
from app_config import owner_password

OWNER_PASSWORD = owner_password()
app_mode = state.app_mode

# =========================================================
# INIT DB
# =========================================================
init_db()
try:
    create_backup(get_conn(), force=False)
except Exception as exc:
    print(f"تعذر إنشاء النسخة الاحتياطية اليومية: {exc}")

ctk.set_appearance_mode("dark")
theme_base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
ctk.set_default_color_theme(os.path.join(theme_base, "coffee_theme.json"))


def clear_window(root):
    """مسح محتوى النافذة"""
    for widget in root.winfo_children():
        widget.destroy()


# =========================================================
# MODE SELECTION UI
# =========================================================
def show_mode_selection(root):
    """عرض واجهة اختيار الوضع (مالك/عامل)"""
    clear_window(root)

    root.title("☕ Café POS - اختيار الوضع")

    # عنوان
    header = ctk.CTkFrame(root, height=150, fg_color="#2f2517")
    header.pack(fill="x", padx=30, pady=30)
    header.pack_propagate(False)

    ctk.CTkLabel(
        header,
        text="☕ Café POS",
        font=("Tahoma", 36, "bold")
    ).pack(pady=(35, 10))

    ctk.CTkLabel(
        header,
        text="اختر وضع الاستخدام:",
        font=("Tahoma", 22, "bold"),
        text_color="#e8dcc0"
    ).pack(pady=(0, 10))

    # أزرار الاختيار
    buttons_frame = ctk.CTkFrame(root, fg_color="transparent")
    buttons_frame.pack(fill="both", expand=True, padx=60, pady=30)

    # زر المالك
    owner_btn = ctk.CTkButton(
        buttons_frame,
        text="👨‍💼 وضع المالك\nإدارة كاملة للنظام",
        height=200,
        corner_radius=25,
        fg_color="#f5c400",
        text_color="#15100a",
        hover_color="#d9a900",
        font=("Tahoma", 24, "bold"),
        command=lambda: show_password_dialog(root, "owner")
    )
    owner_btn.pack(side="left", fill="both", expand=True, padx=20, pady=20)

    # زر العامل
    worker_btn = ctk.CTkButton(
        buttons_frame,
        text="👷 وضع العامل\nتسجيل الدخول وبدء العمل",
        height=200,
        corner_radius=25,
        fg_color="#d4a017",
        hover_color="#b8860b",
        font=("Tahoma", 24, "bold"),
        command=lambda: enter_worker_mode(root)
    )
    worker_btn.pack(side="right", fill="both", expand=True, padx=20, pady=20)


def show_password_dialog(root, mode):
    """عرض نافذة إدخال كلمة المرور"""
    clear_window(root)

    root.title("🔐 كلمة مرور المالك")

    frame = ctk.CTkFrame(root, fg_color="#3b2e1c", corner_radius=30)
    frame.pack(fill="both", expand=True, padx=50, pady=50)

    ctk.CTkLabel(
        frame,
        text="🔐 كلمة مرور المالك",
        font=("Tahoma", 28, "bold")
    ).pack(pady=(30, 20))

    ctk.CTkLabel(
        frame,
        text="أدخل كلمة المرور:",
        font=("Tahoma", 18)
    ).pack(pady=(0, 20))

    entry = ctk.CTkEntry(
        frame,
        show="●",
        width=300,
        height=50,
        font=("Tahoma", 18)
    )
    entry.pack(pady=20)
    entry.focus_set()

    msg_label = ctk.CTkLabel(frame, text="", text_color="#b23b2e", font=("Tahoma", 16))
    msg_label.pack()

    def check_password():
        if entry.get() == OWNER_PASSWORD:
            global app_mode
            app_mode = mode
            state.app_mode = mode
            entry.delete(0, "end")
            update_app_for_mode(root)
        else:
            msg_label.configure(text="❌ كلمة المرور خاطئة")
            entry.delete(0, "end")
            entry.focus_set()

    entry.bind("<Return>", lambda e: check_password())

    button_frame = ctk.CTkFrame(frame, fg_color="transparent")
    button_frame.pack(pady=20)

    ctk.CTkButton(
        button_frame,
        text="دخول",
        width=150,
        height=50,
        corner_radius=15,
        fg_color="#f5c400",
        text_color="#15100a",
        hover_color="#d9a900",
        font=("Tahoma", 18, "bold"),
        command=check_password
    ).pack(side="left", padx=10)

    ctk.CTkButton(
        button_frame,
        text="رجوع",
        width=150,
        height=50,
        corner_radius=15,
        fg_color="#a89462",
        hover_color="#725a34",
        font=("Tahoma", 18),
        command=lambda: show_mode_selection(root)
    ).pack(side="left", padx=10)


def enter_owner_mode(root):
    """دخول وضع المالك"""
    show_password_dialog(root, "owner")


def enter_worker_mode(root):
    """دخول وضع العامل"""
    global app_mode
    app_mode = "worker"
    state.app_mode = "worker"

    clear_window(root)

    temp_frame = ctk.CTkFrame(root)
    temp_frame.pack(fill="both", expand=True)

    show_worker_login(
        temp_frame,
        lambda: update_app_for_mode(root)
    )


def update_app_for_mode(root):
    """تحديث واجهة التطبيق بناءً على الوضع"""
    clear_window(root)

    if app_mode == "owner":
        main_with_mode(root)
    elif app_mode == "worker":
        main_with_mode(root)


def show_change_mode_dialog(root):
    """عرض نافذة تغيير الوضع"""
    dialog = ctk.CTkToplevel(root)
    dialog.title("تغيير الوضع")
    dialog.geometry("500x400")
    dialog.attributes("-topmost", True)
    dialog.focus_force()
    dialog.transient(root)
    dialog.grab_set()

    ctk.CTkLabel(
        dialog,
        text="تغيير وضع الاستخدام",
        font=("Tahoma", 24, "bold")
    ).pack(pady=(30, 15))

    ctk.CTkLabel(
        dialog,
        text="الوضع الحالي:",
        font=("Tahoma", 16),
        text_color="#e8dcc0"
    ).pack(pady=(0, 5))

    current_mode_text = "👨‍💼 المالك" if app_mode == "owner" else "👷 العامل"
    ctk.CTkLabel(
        dialog,
        text=current_mode_text,
        font=("Tahoma", 20, "bold"),
        text_color="#f5c400" if app_mode == "owner" else "#d4a017"
    ).pack(pady=(5, 25))

    buttons_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    buttons_frame.pack(fill="both", expand=True, padx=30, pady=20)

    def switch_to_owner():
        dialog.destroy()
        show_password_dialog(root, "owner")
        return

    def switch_to_worker():
        global app_mode
        # Disconnect locally; today's permanent worker log stays available.
        current_worker.clear()
        current_session.clear()
        dialog.destroy()
        enter_worker_mode(root)

    ctk.CTkButton(
        buttons_frame,
        text="👨‍💼 وضع المالك",
        height=70,
        corner_radius=18,
        fg_color="#f5c400",
        text_color="#15100a",
        hover_color="#d9a900",
        font=("Tahoma", 18, "bold"),
        command=switch_to_owner
    ).pack(fill="x", pady=10)

    ctk.CTkButton(
        buttons_frame,
        text="👷 وضع العامل",
        height=70,
        corner_radius=18,
        fg_color="#d4a017",
        hover_color="#b8860b",
        font=("Tahoma", 18, "bold"),
        command=switch_to_worker
    ).pack(fill="x", pady=10)

    ctk.CTkButton(
        dialog,
        text="إلغاء",
        height=45,
        fg_color="#a89462",
        hover_color="#725a34",
        font=("Tahoma", 16),
        command=dialog.destroy
    ).pack(fill="x", padx=30, pady=20)


def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def ask_password(callback):
    callback()


def main_with_mode(root):
    main_frame = ctk.CTkFrame(root)
    main_frame.pack(fill="both", expand=True)

    top = ctk.CTkFrame(root)
    top.pack(fill="x")

    status_bar = ctk.CTkFrame(top, fg_color="transparent")
    status_bar.pack(fill="x", padx=10, pady=(5, 2))

    nav = ctk.CTkFrame(top, fg_color="transparent")
    nav.pack(fill="x", padx=10, pady=(2, 5))

    # ==========================================
    # WORKER INFO + TIMER
    # ==========================================
    timer_label = None
    work_category_label = None

    def current_worker_drinks_sold():
        worker_session_id = current_session.get("id") if current_session else None
        if not worker_session_id:
            return 0
        cur.execute("""
            SELECT COALESCE(SUM(ri.qty), 0)
            FROM receipt_items ri
            JOIN receipts r ON r.id = ri.receipt_id
            JOIN items i ON i.id = ri.item_id
            WHERE r.worker_session_id=?
              AND TRIM(i.category) IN (?, ?)
        """, (worker_session_id, "مشروبات", "مشاريب"))
        quantity = cur.fetchone()[0] or 0
        return f"{quantity:g}"

    def update_timer():
        nonlocal timer_label, work_category_label

        if not current_session:
            return

        if timer_label is None or not timer_label.winfo_exists():
            return

        start = datetime.fromisoformat(current_session["start_time"])
        elapsed = datetime.now() - start

        total_seconds = int(elapsed.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        timer_label.configure(text=f"⏱ {hours:02}:{minutes:02}:{seconds:02}")
        if work_category_label is not None and work_category_label.winfo_exists():
            work_category_label.configure(text=f"🥤 مبيعات اليوم: {current_worker_drinks_sold()}")
        root.after(1000, update_timer)

    if app_mode == "worker" and current_worker:
        ctk.CTkLabel(
            status_bar,
            text=f"👷 {current_worker['name']}",
            font=("Tahoma", 14, "bold")
        ).pack(side="right", padx=10)

    if app_mode == "worker" and current_session:
        work_category_label = ctk.CTkLabel(
            status_bar,
            text="🥤 مبيعات اليوم: 0",
            font=("Tahoma", 14, "bold"),
            text_color="#f5c400",
            width=220,
            wraplength=210
        )
        work_category_label.pack(side="right", padx=10)

        timer_label = ctk.CTkLabel(
            status_bar,
            text="⏱ 00:00:00",
            font=("Tahoma", 14, "bold")
        )
        timer_label.pack(side="right", padx=10)
        update_timer()

    if app_mode == "worker" and current_session:
        def finish_work():
            try:
                from adb import end_worker_session
                end_worker_session(current_session["id"])
            finally:
                current_worker.clear()
                current_session.clear()
                show_mode_selection(root)

        ctk.CTkButton(
            status_bar,
            text="⏹ إنهاء العمل",
            width=130,
            height=40,
            fg_color="#b23b2e",
            hover_color="#8f2f25",
            font=("Tahoma", 14, "bold"),
            command=finish_work
        ).pack(side="right", padx=5)

    # ==========================================
    # MODE CHANGE BUTTON
    # ==========================================
    mode_text = f"🔄 {'مالك' if app_mode == 'owner' else 'عامل'}" if app_mode else "🔄 وضع"
    mode_color = "#ded38d" if app_mode == "owner" else "#d4a017"
    mode_hover = "#c9a227" if app_mode == "owner" else "#b8860b"

    mode_btn = ctk.CTkButton(
        status_bar,
        text=mode_text,
        width=120,
        height=40,
        fg_color=mode_color,
        hover_color=mode_hover,
        font=("Tahoma", 14, "bold"),
        command=lambda: show_change_mode_dialog(root)
    )
    mode_btn.pack(side="right", padx=5)

    ctk.CTkButton(
        status_bar,
        text="⬇ فحص التحديث",
        width=140,
        height=40,
        fg_color="#3b2e1c",
        hover_color="#725a34",
        font=("Tahoma", 14, "bold"),
        command=lambda: check_for_updates(root, silent=False),
    ).pack(side="left", padx=5)

    nav_button_pos = {"index": 0}

    def nav_button(text, cmd, requires_password=False):
        # في وضع المالك: كل شيء متاح
        # في وضع العامل: فقط ما لا يتطلب كلمة مرور
        if requires_password and app_mode == "worker":
            return

        button = ctk.CTkButton(
            nav,
            text=text,
            command=cmd,
            width=120,
            height=40,
            corner_radius=10
        )
        index = nav_button_pos["index"]
        nav_button_pos["index"] += 1
        button.grid(row=index // 6, column=index % 6, padx=5, pady=4, sticky="ew")
        nav.grid_columnconfigure(index % 6, weight=1, minsize=120)
        return button

    def refresh():
        show_cashier(main_frame, refresh)

    nav_button("كاشير", lambda: show_cashier(main_frame, refresh), requires_password=False)
    nav_button("فواتير", lambda: show_receipts(main_frame, app_mode == "owner"), requires_password=False)
    nav_button("بيانات", lambda: show_analytics(main_frame), requires_password=True)
    nav_button("المخزن", lambda: show_inventory(main_frame, refresh, app_mode == "owner"), requires_password=False)
    nav_button("مكونات", lambda: show_ingredients(main_frame), requires_password=False)
    nav_button("ديون", lambda: show_debts(main_frame), requires_password=False)
    nav_button("مصروفات", lambda: show_expenses(main_frame), requires_password=False)
    nav_button("هدر", lambda: show_waste(main_frame), requires_password=False)
    nav_button("العمال", lambda: show_workers(main_frame, refresh), requires_password=True)
    nav_button("تقييم العمال", lambda: show_worker_ratings(main_frame), requires_password=True)
    nav_button("نسخ احتياطية", lambda: show_backups(main_frame, refresh), requires_password=True)

    # Default screen
    refresh()


def main():
    """الدخول الرئيسي - يعرض اختيار الوضع أولاً"""
    root = ctk.CTk()
    root.title("☕ Café POS")
    root.geometry("1200x700")
    root.minsize(1000, 600)
    try:
        root.state("zoomed")
    except Exception:
        pass

    def on_window_close():
        # Closing the app does not erase or end today's worker log.
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_window_close)

    # عرض واجهة اختيار الوضع
    show_mode_selection(root)

    return root


# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    root = main()
    check_for_updates(root)

    def start_background_sync():
        sync_thread = Thread(target=syncing, daemon=True)
        sync_thread.start()

    root.after(10000, start_background_sync)

    root.mainloop()
