from tkinter import messagebox
import customtkinter as ctk
from adb import cur ,conn
from utils import clear


# =====================================================
# MAIN INGREDIENTS
# =====================================================
def show_ingredients(main):

    clear(main)

    root = ctk.CTkFrame(main)
    root.pack(fill="both", expand=True)

    # ================= TOP BAR =================
    top = ctk.CTkFrame(root, height=70, fg_color="#241c11")
    top.pack(fill="x", padx=10, pady=10)
    top.pack_propagate(False)

    ctk.CTkLabel(
        top,
        text="🧂 إدارة المكونات",
        font=("Tahoma", 24, "bold")
    ).pack(side="left", padx=20)

    ctk.CTkButton(
        top,
        text="+ إضافة مكوّن",
        fg_color="#f5c400",
        text_color="#15100a",
        command=lambda: open_ingredient_panel(root)
    ).pack(side="right", padx=10)

    ctk.CTkButton(
    top,
    text="🔄 إعادة تعبئة",
    fg_color="#b8860b",
    command=lambda: open_restock_ingredient_panel(root)
    ).pack(side="right", padx=10)

    ctk.CTkButton(
    top,
    text="💰 تغيير سعر مكوّن",
    fg_color="#b8860b",
    command=lambda: open_change_price_panel(root)
    ).pack(side="right", padx=10)

    # ================= BODY =================
    frame = ctk.CTkScrollableFrame(root, fg_color="#1c160e")
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    cur.execute("""
        SELECT name, quantity, cost
        FROM ingredients
    """)

    ingredients = cur.fetchall()

    grid = ctk.CTkFrame(frame, fg_color="transparent")
    grid.pack(fill="both", expand=True)

    row = 0
    col = 0

    for ing in ingredients:

        name, qty, cost = ing

        card = ctk.CTkFrame(
            grid,
            width=220,
            height=150,
            fg_color="#2f2517",
            corner_radius=18
        )
        card.grid(row=row, column=col, padx=10, pady=10)
        card.grid_propagate(False)

        ctk.CTkLabel(
            card,
            text=name,
            font=("Tahoma", 18, "bold"),
            wraplength=180
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            card,
            text=f"الكمية: {qty}",
            text_color="#f5c400"
        ).pack()

        ctk.CTkLabel(
            card,
            text=f"التكلفة: {cost} €",
            text_color="#e8dcc0"
        ).pack()

        col += 1
        if col >= 4:
            col = 0
            row += 1


# =====================================================
# SLIDE-IN ADD PANEL
# =====================================================
def open_ingredient_panel(root):

    panel = ctk.CTkFrame(root, width=400, fg_color="#2f2517")
    panel.place(relx=1.0, rely=0, anchor="ne", relheight=1)

    ctk.CTkLabel(
        panel,
        text="إضافة مكوّن",
        font=("Tahoma", 22, "bold")
    ).pack(pady=20)

    

    name_entry = ctk.CTkEntry(panel, placeholder_text="الاسم")
    name_entry.pack(pady=10, padx=20, fill="x")

    qty_entry = ctk.CTkEntry(panel, placeholder_text="الكمية")
    qty_entry.pack(pady=10, padx=20, fill="x")

    cost_entry = ctk.CTkEntry(panel, placeholder_text="التكلفة")
    cost_entry.pack(pady=10, padx=20, fill="x")

    def save():

        name = name_entry.get().strip()

        if not name:
            return

        try:
            qty = float(qty_entry.get())
            cost1 = float(cost_entry.get())
            cost = cost1 / qty 
            print(cost)
        except:
            return

        cur.execute("""
            INSERT INTO ingredients (name, quantity, cost)
            VALUES (?, ?, ?)
        """, (name, qty, cost))

        conn.commit()
        panel.destroy()

    ctk.CTkButton(
        panel,
        text="حفظ",
        fg_color="#f5c400",
        text_color="#15100a",
        command=save
    ).pack(pady=20)

    ctk.CTkButton(
        panel,
        text="إغلاق",
        fg_color="#b23b2e",
        command=panel.destroy
    ).pack()

# =====================================================
# RESTOCK INGREDIENT
# =====================================================
def open_restock_ingredient_panel(root):

    panel = ctk.CTkFrame(root, width=400, fg_color="#2f2517")
    panel.place(relx=1.0, rely=0, anchor="ne", relheight=1)

    ctk.CTkLabel(
        panel,
        text="إعادة تعبئة مكوّن",
        font=("Tahoma", 20, "bold")
    ).pack(pady=20)

    selected = {"id": None, "name": ""}

    list_frame = ctk.CTkScrollableFrame(panel, fg_color="#1c160e")
    list_frame.pack(fill="both", expand=True, padx=10, pady=10)

    cur.execute("SELECT id, name FROM ingredients")
    ingredients = cur.fetchall()

    # ================= SELECT INGREDIENT =================
    def select_item(iid, name):
        selected["id"] = iid
        selected["name"] = name
        title_label.configure(text=f"المكوّن: {name}")

    for iid, name in ingredients:
        ctk.CTkButton(
            list_frame,
            text=name,
            fg_color="#3b2e1c",
            hover_color="#b8860b",
            command=lambda i=iid, n=name: select_item(i, n)
        ).pack(fill="x", pady=5)

    title_label = ctk.CTkLabel(
        panel,
        text="اختر مكوّن",
        font=("Tahoma", 16, "bold")
    )
    title_label.pack(pady=10)

    qty_entry = ctk.CTkEntry(panel, placeholder_text="الكمية")
    qty_entry.pack(pady=10, padx=20, fill="x")

    # ================= SAVE =================
    def save():

        if not selected["id"]:
            return

        try:
            qty = float(qty_entry.get())
        except:
            return

        cur.execute("""
            UPDATE ingredients
            SET 
                quantity = quantity + ?
            WHERE id=?
        """, (qty, selected["id"]))

        conn.commit()
        panel.destroy()

    ctk.CTkButton(
        panel,
        text="حفظ",
        fg_color="#f5c400",
        text_color="#15100a",
        command=save
    ).pack(pady=15)

    ctk.CTkButton(
        panel,
        text="إغلاق",
        fg_color="#b23b2e",
        command=panel.destroy
    ).pack()
def open_change_price_panel(root):

    win = ctk.CTkToplevel()
    win.geometry("400x500")
    win.title("تغيير سعر مكوّن")
    win.grab_set()

    selected = {"id": None}

    ctk.CTkLabel(
        win,
        text="اختر مكوّن",
        font=("Tahoma", 20, "bold")
    ).pack(pady=10)

    list_frame = ctk.CTkScrollableFrame(win)
    list_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def select_ing(iid, name):
        selected["id"] = iid
        selected_label.configure(text=f"المحدد: {name}")

    # LOAD INGREDIENTS
    cur.execute("SELECT id, name FROM ingredients")
    ingredients = cur.fetchall()

    for iid, name in ingredients:
        ctk.CTkButton(
            list_frame,
            text=name,
            fg_color="#3b2e1c",
            command=lambda i=iid, n=name: select_ing(i, n)
        ).pack(fill="x", pady=5)

    selected_label = ctk.CTkLabel(win, text="لم يتم الاختيار")
    selected_label.pack(pady=10)

    price_entry = ctk.CTkEntry(win, placeholder_text="السعر الجديد")
    price_entry.pack(pady=10)

    def save():

        if not selected["id"]:
            messagebox.showwarning("تنبيه", "اختر مكوّن")
            return

        try:
            new_price1 = float(price_entry.get())
        except:
            messagebox.showwarning("تنبيه", "أدخل رقم صحيح")
            return
        

        cur.execute("""SELECT quantity 
                       FROM ingredients WHERE id = ?;
                    """, (selected["id"],))
        row = cur.fetchone()
        qty = row[0] if row else 0
        new_price = new_price1 / qty 
        
        
        cur.execute("""
            UPDATE ingredients
            SET cost=?
            WHERE id=?
        """, (new_price, selected["id"]))

        conn.commit()

        win.destroy()

    ctk.CTkButton(
        win,
        text="حفظ",
        fg_color="#f5c400",
        text_color="#15100a",
        command=save
    ).pack(pady=10)

    ctk.CTkButton(
        win,
        text="إغلاق",
        fg_color="#b23b2e",
        command=win.destroy
    ).pack(pady=5)
