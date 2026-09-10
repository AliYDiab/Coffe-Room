import customtkinter as ctk
from tkinter import messagebox

from adb import conn, cur

# =========================
# OPEN ITEM FORM
# =========================
def open_item_form(refresh_callback):
    win = ctk.CTkToplevel()
    win.lift()
    win.focus_force()

    frame = ctk.CTkScrollableFrame(win)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    selected_category = {"value": None}

    # =========================
    # CATEGORY SELECTION
    # =========================
    ctk.CTkLabel(frame, text="Select Category", font=("Arial", 16, "bold")).pack(pady=10)

    cur.execute("SELECT name FROM categories")
    categories = [c[0] for c in cur.fetchall()]

    cat_label = ctk.CTkLabel(frame, text="No category selected", text_color="orange")
    cat_label.pack()

    def select_category(cat):
        selected_category["value"] = cat
        cat_label.configure(text=f"Selected: {cat}", text_color="lightgreen")

    for c in categories:
        ctk.CTkButton(frame, text=c, command=lambda x=c: select_category(x)).pack(fill="x", pady=2)

    # =========================
    # INPUT FIELDS
    # =========================
    name_entry = ctk.CTkEntry(frame, placeholder_text="Item name")
    name_entry.pack(fill="x", pady=5)

    price_entry = ctk.CTkEntry(frame, placeholder_text="Price (SYP)")
    price_entry.pack(fill="x", pady=5)

    cost_entry = ctk.CTkEntry(frame, placeholder_text="Cost (SYP)")
    cost_entry.pack(fill="x", pady=5)

    stock_entry = ctk.CTkEntry(frame, placeholder_text="Stock (optional)")
    stock_entry.pack(fill="x", pady=5)

    # =========================
    # INGREDIENTS FRAME (CREATE FIRST)
    # =========================
    ingredients_frame = ctk.CTkFrame(frame)

    ingredient_inputs = []

    # LOAD INGREDIENTS FROM DB
    cur.execute("SELECT id, name FROM ingredients")
    all_ingredients = cur.fetchall()

    # BUILD UI
    for ing in all_ingredients:
        row = ctk.CTkFrame(ingredients_frame)
        row.pack(fill="x", pady=2)

        var = ctk.BooleanVar()

        cb = ctk.CTkCheckBox(row, text=ing[1], variable=var)
        cb.pack(side="left")

        qty = ctk.CTkEntry(row, placeholder_text="Qty", width=80)
        qty.pack(side="right")

        ingredient_inputs.append((ing[0], var, qty))

    # =========================
    # TOGGLE INGREDIENTS
    # =========================
    assign_ingredients = ctk.BooleanVar()

    def toggle_ingredients():
        if assign_ingredients.get():
            ingredients_frame.pack(fill="x", pady=10)
        else:
            ingredients_frame.pack_forget()

    ctk.CTkCheckBox(
        frame,
        text="Assign Ingredients",
        variable=assign_ingredients,
        command=toggle_ingredients
    ).pack(pady=10)

    # hide initially
    ingredients_frame.pack_forget()

    # =========================
    # SAVE FUNCTION
    # =========================
    def save_item():
        name = name_entry.get().strip()

        # VALIDATION
        if not selected_category["value"]:
            messagebox.showerror("Error", "Please select a category")
            return

        if not name:
            messagebox.showerror("Error", "Item name is required")
            return

        try:
            price = float(price_entry.get())
            cost = float(cost_entry.get())
        except:
            messagebox.showerror("Error", "Invalid price or cost")
            return

        stock_text = stock_entry.get().strip()
        stock = None if stock_text == "" else int(stock_text)

        try:
            # 🔥 INSERT ITEM
            cur.execute("""
                INSERT INTO items (name, category, price, cost, stock)
                VALUES (?, ?, ?, ?, ?)
            """, (name, selected_category["value"], price, cost, stock))

            item_id = cur.lastrowid

            # 🔥 INSERT INGREDIENTS
            if assign_ingredients.get():
                for ing_id, var, qty_entry in ingredient_inputs:
                    if var.get():
                        try:
                            qty = float(qty_entry.get())
                        except:
                            continue

                        cur.execute("""
                            INSERT INTO item_ingredients (item_id, ingredient_id, quantity)
                            VALUES (?, ?, ?)
                        """, (item_id, ing_id, qty))

            conn.commit()

            win.destroy()
            refresh_callback()

        except Exception as e:
            messagebox.showerror("Database Error", str(e))

    # =========================
    # SAVE BUTTON
    # =========================
    ctk.CTkButton(
        frame,
        text="SAVE ITEM",
        fg_color="green",
        command=save_item
    ).pack(pady=20)
