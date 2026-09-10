import customtkinter as ctk
from tkinter import messagebox

from adb import conn, init_db
from backup_manager import (
    backup_display_name,
    create_backup,
    list_backups,
    restore_backup,
)


def show_backups(main, refresh_callback=None):
    for widget in main.winfo_children():
        widget.destroy()

    container = ctk.CTkFrame(main, fg_color="#241c11")
    container.pack(fill="both", expand=True, padx=18, pady=18)

    ctk.CTkLabel(
        container,
        text="🛡️ النسخ الاحتياطية",
        font=("Tahoma", 26, "bold"),
        text_color="#f5c400",
    ).pack(anchor="e", padx=18, pady=(18, 4))
    ctk.CTkLabel(
        container,
        text="يُنشئ النظام نسخة آمنة يومياً ويحتفظ بآخر 14 نسخة.",
        font=("Tahoma", 14),
        text_color="#e8dcc0",
    ).pack(anchor="e", padx=18, pady=(0, 14))

    list_frame = ctk.CTkScrollableFrame(container, fg_color="#2f2517")
    list_frame.pack(fill="both", expand=True, padx=18, pady=10)

    def reload_list():
        for child in list_frame.winfo_children():
            child.destroy()
        backups = list_backups()
        if not backups:
            ctk.CTkLabel(
                list_frame,
                text="لا توجد نسخ احتياطية بعد",
                font=("Tahoma", 15),
            ).pack(pady=30)
            return
        for path in backups:
            row = ctk.CTkFrame(list_frame, fg_color="#3b2e1c")
            row.pack(fill="x", padx=8, pady=5)
            ctk.CTkLabel(
                row,
                text=backup_display_name(path),
                font=("Tahoma", 14, "bold"),
            ).pack(side="right", padx=12, pady=12)
            ctk.CTkButton(
                row,
                text="استعادة",
                width=100,
                fg_color="#b23b2e",
                hover_color="#8f2f25",
                command=lambda selected=path: restore_selected(selected),
            ).pack(side="left", padx=10, pady=8)

    def make_backup():
        try:
            path = create_backup(conn, force=True)
            reload_list()
            messagebox.showinfo("تم", f"تم إنشاء النسخة الاحتياطية:\n{path.name}")
        except Exception as exc:
            messagebox.showerror("خطأ", f"تعذر إنشاء النسخة الاحتياطية:\n{exc}")

    def restore_selected(path):
        answer = messagebox.askyesno(
            "تأكيد الاستعادة",
            "سيتم حفظ نسخة من البيانات الحالية أولاً، ثم استعادة النسخة المحددة.\n"
            "هل تريد المتابعة؟",
        )
        if not answer:
            return
        try:
            restore_backup(path, conn)
            init_db()
            reload_list()
            messagebox.showinfo("تم", "تمت استعادة قاعدة البيانات بنجاح.")
            if refresh_callback:
                refresh_callback()
        except Exception as exc:
            messagebox.showerror("خطأ", f"تعذرت الاستعادة:\n{exc}")

    ctk.CTkButton(
        container,
        text="إنشاء نسخة احتياطية الآن",
        height=44,
        fg_color="#f5c400",
        text_color="#15100a",
        hover_color="#d9a900",
        font=("Tahoma", 15, "bold"),
        command=make_backup,
    ).pack(fill="x", padx=18, pady=(4, 18))

    reload_list()
