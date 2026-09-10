import customtkinter as ctk
from adb import (
    get_all_workers_with_ratings, get_worker_ratings, add_worker_rating,
    get_worker_performance_stats
)
from utils import clear


# =====================================================
# WORKER RATINGS - تقييم العمال (نظام آلي)
# =====================================================
# التقييم يتم حسابه تلقائياً بناءً على أداء العامل

def show_worker_ratings(main):
    """واجهة تقييم العمال (فقط للمالك) - نظام آلي"""
    clear(main)

    root = ctk.CTkFrame(main)
    root.pack(fill="both", expand=True)

    # =====================================================
    # العنوان
    # =====================================================
    header = ctk.CTkFrame(root, height=80, fg_color="#f5c400")
    text_color="#15100a",
    header.pack(fill="x", padx=10, pady=10)
    header.pack_propagate(False)

    ctk.CTkLabel(
        header,
        text="⭐ تقييم العمال",
        font=("Tahoma", 28, "bold")
    ).pack(pady=20)

    # =====================================================
    # المحتوى الرئيسي
    # =====================================================
    content = ctk.CTkScrollableFrame(root, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=10, pady=10)

    # قسم قائمة العمال
    workers_section = ctk.CTkFrame(content, fg_color="#2f2517", corner_radius=20)
    workers_section.pack(fill="x", pady=10)

    ctk.CTkLabel(
        workers_section,
        text="👥 العمال وتقييماتهم (آلي)",
        font=("Tahoma", 24, "bold")
    ).pack(pady=20)

    # عرض العمال مع تقييماتهم
    workers_list_frame = ctk.CTkScrollableFrame(
        workers_section,
        height=300,
        fg_color="#241c11",
        corner_radius=10
    )
    workers_list_frame.pack(fill="x", padx=15, pady=15)

    def refresh_workers_list():
        for widget in workers_list_frame.winfo_children():
            widget.destroy()

        workers = get_all_workers_with_ratings()
        for worker_id, name, active, rating, total_ratings in workers:
            card = ctk.CTkFrame(workers_list_frame, fg_color="#3b2e1c", corner_radius=12)
            card.pack(fill="x", pady=8)

            # معلومات العامل
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="right", fill="both", expand=True, padx=15, pady=10)

            ctk.CTkLabel(
                info_frame,
                text=name,
                font=("Tahoma", 16, "bold")
            ).pack(anchor="e")

            if total_ratings > 0:
                stars = "⭐" * int(rating) + "☆" * (5 - int(rating))
                rating_text = f"{rating:.1f}/5 ({total_ratings} تقييم)"
                rating_color = "#f5c400" if rating >= 4 else "#ded38d" if rating >= 3 else "#b23b2e"
            else:
                stars = "☆☆☆☆☆"
                rating_text = "لم يتم التقييم"
                rating_color = "#a89462"

            ctk.CTkLabel(
                info_frame,
                text=f"{stars} {rating_text}",
                text_color=rating_color,
                font=("Tahoma", 12)
            ).pack(anchor="e")

            # زر عرض التفاصيل فقط (التقييم آلي)
            def show_details(wid=worker_id, wname=name):
                show_worker_details(wid, wname, root, refresh_workers_list)

            ctk.CTkButton(
                card,
                text="📊 تفاصيل",
                width=100, height=35,
                fg_color="#d4a017", hover_color="#b8860b",
                font=("Tahoma", 12),
                command=show_details
            ).pack(side="left", padx=10)

    refresh_workers_list()


def show_worker_details(worker_id, worker_name, main_frame, back_callback):
    """عرض تفاصيل عامل"""
    clear(main_frame)

    root = ctk.CTkFrame(main_frame)
    root.pack(fill="both", expand=True)

    # العنوان
    header = ctk.CTkFrame(root, height=80, fg_color="#f5c400")
    text_color="#15100a",
    header.pack(fill="x", padx=10, pady=10)
    header.pack_propagate(False)

    ctk.CTkLabel(
        header,
        text=f"👤 تفاصيل {worker_name}",
        font=("Tahoma", 28, "bold")
    ).pack(pady=20)

    back_btn = ctk.CTkButton(
        header,
        text="رجوع",
        width=80, height=35,
        fg_color="#a89462", hover_color="#725a34",
        command=lambda: back_callback()
    )
    back_btn.place(x=10, y=20)

    # المحتوى
    content = ctk.CTkScrollableFrame(root, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=10, pady=10)

    # الإحصائيات
    stats_section = ctk.CTkFrame(content, fg_color="#2f2517", corner_radius=20)
    stats_section.pack(fill="x", pady=10)

    ctk.CTkLabel(
        stats_section,
        text="📊 إحصائيات الأداء (تقييم آلي)",
        font=("Tahoma", 24, "bold")
    ).pack(pady=20)

    # الحصول على الإحصائيات
    stats = get_worker_performance_stats(worker_id)

    stats_grid = ctk.CTkFrame(stats_section, fg_color="#3b2e1c", corner_radius=15)
    stats_grid.pack(fill="x", padx=20, pady=15)

    stat_items = [
        ("📋 عدد الجلسات", str(stats["total_sessions"])),
        ("💰 إجمالي المبيعات", f"{stats['total_sales']:.0f}"),
        ("🧾 إجمالي الإيرادات", f"{stats['total_revenue']:.0f} SYP"),
        ("⭐ متوسط التقييم", f"{stats['average_rating']:.1f}/5"),
        ("📈 عدد التقييمات", str(stats["total_ratings"]))
    ]

    for i, (label, value) in enumerate(stat_items):
        row = i // 3
        col = i % 3

        stat_card = ctk.CTkFrame(stats_grid, fg_color="#241c11", corner_radius=10)
        stat_card.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
        stats_grid.grid_columnconfigure(col, weight=1)

        ctk.CTkLabel(stat_card, text=label, text_color="#e8dcc0", font=("Tahoma", 12)).pack(pady=(10, 5))
        ctk.CTkLabel(stat_card, text=value, font=("Tahoma", 20, "bold"), text_color="#f5c400").pack(pady=(0, 10))

    # تقييمات سابقة
    ratings_section = ctk.CTkFrame(content, fg_color="#2f2517", corner_radius=20)
    ratings_section.pack(fill="x", pady=10)

    ctk.CTkLabel(
        ratings_section,
        text="📝 التقييمات السابقة",
        font=("Tahoma", 24, "bold")
    ).pack(pady=20)

    ratings_list = ctk.CTkScrollableFrame(
        ratings_section,
        height=250,
        fg_color="#241c11",
        corner_radius=10
    )
    ratings_list.pack(fill="x", padx=15, pady=15)

    ratings = get_worker_ratings(worker_id)

    if ratings:
        for rating_id, rating, notes, created_by, created_at, session_date, schedule_name in ratings:
            rating_card = ctk.CTkFrame(ratings_list, fg_color="#3b2e1c", corner_radius=10)
            rating_card.pack(fill="x", pady=8)

            stars = "⭐" * rating
            top_frame = ctk.CTkFrame(rating_card, fg_color="transparent")
            top_frame.pack(fill="x", padx=15, pady=(10, 5))

            ctk.CTkLabel(
                top_frame,
                text=f"{stars} ({rating}/5)",
                font=("Tahoma", 16, "bold"),
                text_color="#ded38d"
            ).pack(side="right")

            if created_at:
                ctk.CTkLabel(
                    top_frame,
                    text=created_at[:10],
                    text_color="#e8dcc0",
                    font=("Tahoma", 12)
                ).pack(side="left")

            if notes:
                ctk.CTkLabel(
                    rating_card,
                    text=f"📝 {notes}",
                    text_color="#e8dcc0",
                    font=("Tahoma", 14),
                    wraplength=True
                ).pack(anchor="e", padx=15, pady=(0, 5))

            if created_by:
                ctk.CTkLabel(
                    rating_card,
                    text=f"بواسطة: {created_by}",
                    text_color="#ded38d",
                    font=("Tahoma", 12)
                ).pack(anchor="e", padx=15, pady=(0, 10))
    else:
        ctk.CTkLabel(
            ratings_list,
            text="لا توجد تقييمات سابقة",
            text_color="#a89462",
            font=("Tahoma", 16)
        ).pack(pady=30)
