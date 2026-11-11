"""Read-only receipt details opened without leaving the cashier."""
import customtkinter as ctk


def show_receipt_preview(parent, cursor, receipt_id):
    cursor.execute("SELECT date, total FROM receipts WHERE id=?", (receipt_id,))
    receipt = cursor.fetchone()
    if receipt is None:
        return
    cursor.execute("SELECT name, qty, price FROM receipt_items WHERE receipt_id=?", (receipt_id,))
    items = cursor.fetchall()
    dialog = ctk.CTkToplevel(parent)
    dialog.title(f"فاتورة #{receipt_id}")
    dialog.geometry("620x520")
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()
    ctk.CTkLabel(dialog, text=f"فاتورة #{receipt_id}", font=("Tahoma", 23, "bold")).pack(pady=(18, 6))
    ctk.CTkLabel(dialog, text=receipt[0] or "").pack(pady=4)
    body = ctk.CTkScrollableFrame(dialog)
    body.pack(fill="both", expand=True, padx=18, pady=12)
    for name, qty, price in items:
        qty, price = qty or 0, price or 0
        ctk.CTkLabel(
            body, text=f"{name}   |   {qty:g} × {price:.2f} = {qty * price:.2f} SYP",
            anchor="e", wraplength=540, font=("Tahoma", 16),
        ).pack(fill="x", padx=8, pady=8)
    ctk.CTkLabel(dialog, text=f"الإجمالي: {(receipt[1] or 0):.2f} SYP", font=("Tahoma", 20, "bold")).pack(pady=10)
    ctk.CTkButton(dialog, text="إغلاق", command=dialog.destroy).pack(pady=(0, 18))
    dialog.focus_set()
    return dialog
