import customtkinter as ctk
from tkinter import messagebox
from adb import cur, conn
from utils import clear
from utils_cost import calculate_item_cost
from utils import get_item_stock
import os
import sys
from threading import Thread

import state
from state import current_worker
from firebase_sync import init_firebase, push_all_database_to_firestore, send_notification

# Handle barcode import gracefully for PyInstaller compatibility
try:
    from barcode import Code128
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    print("[WARNING] Barcode library not available - barcode generation disabled")


def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BARCODE_FOLDER = os.path.join(get_base_dir(), "barcodes")
os.makedirs(BARCODE_FOLDER, exist_ok=True)


def confirm_cost_not_higher_than_price(price, cost):
    if price <= 0 or cost <= price:
        return True
    return messagebox.askyesno(
        "تحقق من التكلفة",
        (
            f"التكلفة ({cost:.0f}) أكبر من سعر البيع ({price:.0f}).\n"
            "هذا سيظهر ربحاً سالباً في البيانات.\n\n"
            "هل تريد الحفظ بهذا الشكل؟"
        ),
    )


# =====================================================
# BARCODE GENERATION
# =====================================================
def generate_item_barcode(item_id, item_name):
    if not BARCODE_AVAILABLE:
        print(f"Barcode generation disabled - library not available")
        return None

    cur.execute("SELECT barcode_value FROM items WHERE id=?", (item_id,))
    result = cur.fetchone()
    barcode_value = result[0] if result else None

    if barcode_value:
        print(f"Skipped {item_name} (supplier barcode)")
        return None

    safe_name = item_name.replace("/", "_").replace("\\", "_").replace(":", "_")
    path = os.path.join(BARCODE_FOLDER, f"{safe_name}.png")

    if os.path.exists(path):
        print(f"Barcode already exists for {item_name}")
        return path

    data = f"ITEM_ID:{item_id}"
    barcode = Code128(data, writer=ImageWriter())
    saved_path = barcode.save(os.path.join(BARCODE_FOLDER, safe_name))
    print(f"Barcode created: {item_name}")
    return saved_path


def generate_all_barcodes():
    try:
        cur.execute("SELECT id, name FROM items ORDER BY name")
        items = cur.fetchall()

        if not items:
            return

        created = skipped_existing = skipped_supplier = 0

        for item_id, item_name in items:
            safe_name = item_name.replace("/", "_").replace("\\", "_").replace(":", "_")
            path = os.path.join(BARCODE_FOLDER, f"{safe_name}.png")

            cur.execute("SELECT barcode_value FROM items WHERE id=?", (item_id,))
            res = cur.fetchone()

            if res and res[0]:
                skipped_supplier += 1
                continue
            if os.path.exists(path):
                skipped_existing += 1
                continue

            generate_item_barcode(item_id, item_name)
            created += 1

    except Exception as e:
        import traceback
        messagebox.showerror("Barcode Error", traceback.format_exc())


# =====================================================
# MAIN INVENTORY
# =====================================================
def show_inventory(main, refresh_callback, owner_mode=False):

    clear(main)

    root = ctk.CTkFrame(main)
    root.pack(fill="both", expand=True)

    # ================= TOP BAR =================
    top = ctk.CTkFrame(root, height=70, fg_color="#241c11")
    top.pack(fill="x", padx=10, pady=10)
    top.pack_propagate(False)

    ctk.CTkLabel(top, text="📦 المخزون", font=("Tahoma", 24, "bold")).pack(side="left", padx=20)

    btns = ctk.CTkFrame(top, fg_color="transparent")
    btns.pack(side="right")

    def push_database_to_firestore():
        if not owner_mode:
            messagebox.showwarning("Access denied", "Owner mode is required.")
            return

        if not messagebox.askyesno(
            "Push to Firestore",
            "Push all local database data to Firestore now?"
        ):
            return

        push_btn.configure(state="disabled", text="Uploading...")

        def finish_upload(success, message):
            if not main.winfo_exists():
                return

            if push_btn.winfo_exists():
                push_btn.configure(state="normal", text="Push DB to Firestore")

            if not success:
                messagebox.showerror("Firestore Error", message)

        def worker():
            try:
                push_all_database_to_firestore()
            except Exception as exc:
                error_message = str(exc)
                main.after(0, lambda message=error_message: finish_upload(False, message))
                return

            main.after(
                0,
                lambda: finish_upload(True, "Database pushed to Firestore successfully.")
            )

        Thread(target=worker, daemon=True).start()

    if owner_mode:
        push_btn = ctk.CTkButton(
            btns,
            text="Push DB to Firestore",
            fg_color="#e8c84f",
            text_color="#15100a",
            hover_color="#c9a227",
            command=push_database_to_firestore
        )
        push_btn.pack(side="left", padx=5)

    def owner_only(action):
        if owner_mode:
            action()
        else:
            messagebox.showwarning("Access denied", "Owner mode is required.")

    if owner_mode:
        ctk.CTkButton(
            btns, text="📇 توليد باركود", fg_color="#f5c400",
            text_color="#15100a",
            command=lambda: owner_only(generate_all_barcodes)
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btns, text="+ إضافة فئة", fg_color="#b8860b",
            command=lambda: owner_only(lambda: open_category_panel(main, refresh_callback, owner_mode))
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btns, text="+ إضافة عنصر", fg_color="#f5c400",
            text_color="#15100a",
            command=lambda: owner_only(lambda: open_item_step1(root, refresh_callback, owner_mode))
        ).pack(side="left", padx=5)

    ctk.CTkButton(
        btns, text="📦 إعادة تخزين", fg_color="#ded38d",
        text_color="#15100a",
        command=lambda: open_restock_panel(main, refresh_callback, owner_mode)
    ).pack(side="left", padx=5)

    # ================= BODY =================
    body = ctk.CTkFrame(root, fg_color="transparent")
    body.pack(fill="both", expand=True)

    left = ctk.CTkScrollableFrame(body, width=250, fg_color="#2f2517")
    left.pack(side="left", fill="y", padx=10, pady=10)

    right_container = ctk.CTkFrame(body, fg_color="transparent")
    right_container.pack(
        side="left",
        fill="both",
        expand=True,
        padx=10,
        pady=10
    )

    search_var = ctk.StringVar()

    search_entry = ctk.CTkEntry(
        right_container,
        textvariable=search_var,
        placeholder_text="🔍 ابحث عن عنصر..."
    )
    search_entry.pack(fill="x", pady=(0, 10))

    right = ctk.CTkScrollableFrame(
        right_container,
        fg_color="#1c160e"
    )
    right.pack(fill="both", expand=True)

    def safe_get_item_stock(item_id, item_type, stock):
        try:
            return get_item_stock(cur, item_id, item_type, stock)
        except TypeError:
            try:
                return get_item_stock(item_id, item_type, stock)
            except:
                return stock
        except:
            return stock

    # =====================================================
    # EDIT OPTIONS PANEL  (opens when "تعديل" is clicked)
    # =====================================================
    
    def notify_worker_inventory_edit(item_id, old_name, new_name):
        if owner_mode or state.app_mode != "worker" or not current_worker:
            return

        worker_id = current_worker.get("id")
        worker_name = current_worker.get("name", "Unknown worker")
        title = "Inventory item edited"
        body = f"{worker_name} edited {old_name}"
        if old_name != new_name:
            body = f"{worker_name} changed {old_name} to {new_name}"

        def send_worker_edit_notification():
            try:
                from firebase_admin import firestore

                db = init_firebase()
                send_notification(title, body, db=db)
                db.collection("inventory_edit_notifications").add({
                    "item_id": item_id,
                    "old_name": old_name,
                    "new_name": new_name,
                    "worker_id": worker_id,
                    "worker_name": worker_name,
                    "created_at": firestore.SERVER_TIMESTAMP,
                })
            except Exception as exc:
                print(f"[NOTIF ERROR] Inventory edit notification failed: {exc}")

        Thread(target=send_worker_edit_notification, daemon=True).start()

    def open_edit_panel(item_id, item_name, item_type):
        if not owner_mode:
            messagebox.showwarning("Access denied", "Owner mode is required.")
            return

        for w in root.winfo_children():
            if getattr(w, "_is_edit_panel", False):
                w.destroy()

        panel = ctk.CTkFrame(root, width=420, fg_color="#2f2517")
        panel._is_edit_panel = True
        panel.place(relx=1.0, rely=0, anchor="ne", relheight=1)

        header = ctk.CTkFrame(panel, fg_color="#241c11", corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text=f"⚙️ تعديل الخصائص",
            font=("Tahoma", 18, "bold")
        ).pack(side="left", padx=15, pady=15)

        ctk.CTkButton(
            header,
            text="✕",
            width=36,
            fg_color="#b23b2e",
            hover_color="#7a261f",
            command=panel.destroy
        ).pack(side="right", padx=10, pady=10)

        content = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=15, pady=15)

        def field_label(text, pady=(10, 4)):
            ctk.CTkLabel(
                content,
                text=text,
                font=("Tahoma", 14, "bold")
            ).pack(anchor="w", pady=pady)

        cur.execute("""
            SELECT name, category, price, cost,
                stock, available, barcode_value, type
            FROM items
            WHERE id=?
        """, (item_id,))

        row = cur.fetchone()

        (
            current_name,
            current_category,
            current_price,
            current_cost,
            current_stock,
            current_available,
            current_barcode,
            current_type
        ) = row

        ctk.CTkLabel(content, text=f"ID: {item_id}",
                    text_color="#a89462").pack(anchor="w", pady=(0, 10))

        field_label("اسم العنصر", pady=(0, 4))
        name_entry = ctk.CTkEntry(content, placeholder_text="مثال: كابتشينو")
        name_entry.insert(0, current_name)
        name_entry.pack(fill="x", pady=5)

        cur.execute("SELECT name FROM categories ORDER BY name")
        categories = [c[0] for c in cur.fetchall()]

        category_var = ctk.StringVar(value=current_category)

        field_label("الفئة")

        category_menu = ctk.CTkOptionMenu(
            content,
            variable=category_var,
            values=categories
        )
        category_menu.pack(fill="x", pady=5)

        field_label("سعر البيع")
        price_entry = ctk.CTkEntry(content, placeholder_text="أدخل سعر البيع")
        price_entry.insert(0, str(current_price))
        price_entry.pack(fill="x", pady=5)

        field_label("التكلفة")
        cost_entry = ctk.CTkEntry(content, placeholder_text="أدخل تكلفة الوحدة")
        cost_entry.insert(0, str(current_cost or 0))
        cost_entry.pack(fill="x", pady=5)

        stock_mode = ctk.StringVar(
            value="infinite" if current_stock is None else "limited"
        )

        stock_frame = ctk.CTkFrame(content, fg_color="transparent")
        stock_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            stock_frame,
            text="المخزون",
            font=("Tahoma", 14, "bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            stock_frame,
            text="اختر غير محدود إذا كان المنتج لا يعتمد على عدد ثابت",
            text_color="#e8dcc0",
            font=("Tahoma", 12)
        ).pack(anchor="w", pady=(0, 4))

        stock_entry = ctk.CTkEntry(stock_frame, placeholder_text="عدد الوحدات المتاحة")

        if current_stock is not None:
            stock_entry.insert(0, str(current_stock))

        def toggle_stock():
            if stock_mode.get() == "limited":
                stock_entry.pack(fill="x", pady=5)
            else:
                stock_entry.pack_forget()

        ctk.CTkRadioButton(
            stock_frame,
            text="غير محدود",
            variable=stock_mode,
            value="infinite",
            command=toggle_stock
        ).pack(anchor="w")

        ctk.CTkRadioButton(
            stock_frame,
            text="محدود",
            variable=stock_mode,
            value="limited",
            command=toggle_stock
        ).pack(anchor="w")

        toggle_stock()

        available_var = ctk.BooleanVar(
            value=bool(current_available)
        )

        ctk.CTkCheckBox(
            content,
            text="العنصر متاح للبيع",
            variable=available_var
        ).pack(anchor="w", pady=10)

        field_label("الباركود")
        ctk.CTkLabel(
            content,
            text="اتركه فارغاً إذا لم يكن لهذا العنصر باركود خاص",
            text_color="#e8dcc0",
            font=("Tahoma", 12)
        ).pack(anchor="w", pady=(0, 4))

        barcode_entry = ctk.CTkEntry(content, placeholder_text="اختياري: أدخل الباركود هنا")
        barcode_entry.insert(0, current_barcode or "")
        barcode_entry.pack(fill="x", pady=5)

        type_var = ctk.StringVar(value=current_type)

        field_label("نوع العنصر")

        ctk.CTkOptionMenu(
            content,
            variable=type_var,
            values=["fixed", "recipe"]
        ).pack(fill="x", pady=5)

        def save():

            name = name_entry.get().strip()

            if not name:
                messagebox.showwarning("تنبيه", "أدخل الاسم")
                return

            try:
                price = float(price_entry.get())
                cost = float(cost_entry.get())
                if not confirm_cost_not_higher_than_price(price, cost):
                    return
            except:
                messagebox.showwarning(
                    "تنبيه",
                    "تحقق من السعر والتكلفة"
                )
                return

            stock = None

            if stock_mode.get() == "limited":
                try:
                    stock = int(stock_entry.get())
                except:
                    messagebox.showwarning(
                        "تنبيه",
                        "أدخل مخزوناً صحيحاً"
                    )
                    return

            barcode = barcode_entry.get().strip()

            if barcode:
                cur.execute("""
                    SELECT id
                    FROM items
                    WHERE barcode_value = ?
                    AND id != ?
                """, (barcode, item_id))

                if cur.fetchone():
                    messagebox.showwarning(
                        "تنبيه",
                        "الباركود مستخدم مسبقاً"
                    )
                    return
            else:
                barcode = None

            cur.execute("""
                UPDATE items
                SET
                    name = ?,
                    category = ?,
                    price = ?,
                    cost = ?,
                    stock = ?,
                    available = ?,
                    barcode_value = ?,
                    type = ?
                WHERE id = ?
            """, (
                name,
                category_var.get(),
                price,
                cost,
                stock,
                int(available_var.get()),
                barcode,
                type_var.get(),
                item_id
            ))

            conn.commit()

            notify_worker_inventory_edit(item_id, current_name, name)
            panel.destroy()
            load_items(selected_category["value"], search_var.get())

        ctk.CTkButton(
            content,
            text="💾 حفظ التغييرات",
            fg_color="#f5c400",
            text_color="#15100a",
            hover_color="#d9a900",
            command=save
        ).pack(fill="x", pady=(20, 10))

        if owner_mode:
            ctk.CTkButton(
                content,
            text="🗑 حذف العنصر",
                fg_color="#b23b2e",
                hover_color="#7a261f",
                command=lambda: delete_item()
            ).pack(fill="x")

        def delete_item():

            if not messagebox.askyesno(
                "تأكيد",
                f"هل تريد حذف {current_name} ؟"
            ):
                return

            cur.execute(
                "DELETE FROM item_ingredients WHERE item_id=?",
                (item_id,)
            )

            cur.execute(
                "DELETE FROM items WHERE id=?",
                (item_id,)
            )

            conn.commit()

            panel.destroy()
            load_items(selected_category["value"], search_var.get(), reset_limit=True)


    # ================= LOAD ITEMS =================
    selected_category = {"value": None}
    inventory_page = {"limit": 50}
    INVENTORY_BATCH_SIZE = 50

    def load_items(cat=None, search_text="", reset_limit=False):
        if reset_limit:
            inventory_page["limit"] = INVENTORY_BATCH_SIZE
        for w in right.winfo_children():
            w.destroy()

        search = search_text.strip()
        where = []
        params = []
        if cat is not None:
            where.append("category = ?")
            params.append(cat)
        if search:
            where.append("name LIKE ?")
            params.append(f"%{search}%")
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        cur.execute(f"SELECT COUNT(*) FROM items {where_sql}", params)
        total_items = cur.fetchone()[0] or 0

        cur.execute(f"""
            SELECT id, name, stock, price, type
            FROM items
            {where_sql}
            ORDER BY name
            LIMIT ?
        """, params + [inventory_page["limit"]])

        visible_items = cur.fetchall()

        for item_id, name, stock, price, item_type in visible_items:
            item_type = item_type or "fixed"

            card = ctk.CTkFrame(right, fg_color="#2f2517", corner_radius=15)
            card.pack(fill="x", pady=5)

            # left side: info
            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, padx=10, pady=8)

            ctk.CTkLabel(info, text=name, font=("Tahoma", 16, "bold")).pack(anchor="w")

            stock_i = safe_get_item_stock(item_id, item_type, stock)

            if stock_i is None:
                stock_text, color = "∞", "#f5c400"
            elif stock_i == 0:
                stock_text, color = "0", "#b23b2e"
            elif stock_i <= 10:
                stock_text, color = f"{stock_i} ⚠", "#b23b2e"
            else:
                stock_text, color = str(stock_i), "#e8dcc0"

            ctk.CTkLabel(
                info,
                text=f"المخزون: {stock_text}   |   {price} SYP",
                text_color=color
            ).pack(anchor="w")

            ctk.CTkButton(
                card,
                text="+ Qty",
                width=100,
                height=40,
                corner_radius=10,
                fg_color="#ded38d",
                text_color="#15100a",
                hover_color="#a77910",
                font=("Tahoma", 14, "bold"),
                command=lambda iid=item_id: open_restock_panel(main, refresh_callback, owner_mode, iid)
            ).pack(side="right", padx=10, pady=10)
            if owner_mode:
                ctk.CTkButton(
                    card,
                    text="✏️ تعديل",
                    width=100,
                    height=40,
                    corner_radius=10,
                    fg_color="#3b2e1c",
                    hover_color="#b8860b",
                    font=("Tahoma", 14, "bold"),
                    command=lambda iid=item_id, n=name, t=item_type: open_edit_panel(iid, n, t)
                ).pack(side="right", padx=10, pady=10)

        if total_items > inventory_page["limit"]:
            ctk.CTkButton(
                right,
                text=f"Load more ({total_items - inventory_page['limit']})",
                height=40,
                fg_color="#3b2e1c",
                hover_color="#b8860b",
                command=lambda: (
                    inventory_page.update({"limit": inventory_page["limit"] + INVENTORY_BATCH_SIZE}),
                    load_items(selected_category["value"], search_var.get())
                )
            ).pack(fill="x", pady=10)

    # ── category sidebar ──
    search_timer = {"id": None}

    def on_search(*args):
        if search_timer["id"] is not None:
            root.after_cancel(search_timer["id"])
        search_timer["id"] = root.after(
            180,
            lambda: load_items(
                selected_category["value"],
                search_var.get(),
                reset_limit=True
            )
        )

    search_var.trace_add("write", on_search)

    scan_buffer = {"chars": "", "timer": None}
    SCAN_TIMEOUT_MS = 80
    TEXT_WIDGET_CLASSES = {"Entry", "Text", "TEntry", "Spinbox"}

    def focused_text_input():
        try:
            focused = root.winfo_toplevel().focus_get()
            return focused is not None and (
                focused == search_entry._entry
                or focused.winfo_class() in TEXT_WIDGET_CLASSES
            )
        except Exception:
            return False

    def flush_scan():
        if scan_buffer["timer"] is not None:
            try:
                root.after_cancel(scan_buffer["timer"])
            except Exception:
                pass
        code = scan_buffer["chars"].strip()
        scan_buffer["chars"] = ""
        scan_buffer["timer"] = None
        if not code:
            return
        cur.execute("SELECT id FROM items WHERE barcode_value=?", (code,))
        row = cur.fetchone()
        if row:
            open_restock_panel(main, refresh_callback, owner_mode, row[0])
            try:
                import winsound
                winsound.Beep(1200, 80)
            except Exception:
                pass
        else:
            print("Inventory barcode not found:", code)

    def on_scan_key(event):
        if not root.winfo_exists() or focused_text_input():
            return
        if not event.char or not event.char.isprintable():
            return
        scan_buffer["chars"] += event.char
        if scan_buffer["timer"] is not None:
            root.after_cancel(scan_buffer["timer"])
        scan_buffer["timer"] = root.after(SCAN_TIMEOUT_MS, flush_scan)

    def finish_scan_on_enter(event=None):
        if not root.winfo_exists() or focused_text_input():
            return
        if scan_buffer["chars"].strip():
            flush_scan()
            return "break"

    try:
        root.winfo_toplevel().bind("<Key>", on_scan_key)
        root.winfo_toplevel().bind("<Return>", finish_scan_on_enter)
        root.winfo_toplevel().bind("<KP_Enter>", finish_scan_on_enter)
    except Exception:
        print("Warning: Could not bind keyboard events for inventory barcode scanning")
    ctk.CTkButton(
        left, text="🌍 الكل",
        fg_color="#3b2e1c", hover_color="#b8860b",
        command=lambda: (
    selected_category.update({"value": None}),
    load_items(None, search_var.get(), reset_limit=True)
)
    ).pack(fill="x", pady=5)

    cur.execute("SELECT name FROM categories ORDER BY name")
    categories = [c[0] for c in cur.fetchall()]

    for cat in categories:
        ctk.CTkButton(
            left, text=cat,
            fg_color="#3b2e1c", hover_color="#b8860b",
           command=lambda c=cat: (
    selected_category.update({"value": c}),
    load_items(c, search_var.get(), reset_limit=True)
)
        ).pack(fill="x", pady=5)

    if categories:
        load_items(categories[0], reset_limit=True)
    else:
        load_items(None, reset_limit=True)


# =====================================================
# CATEGORY ADD
# =====================================================
def open_category_panel(main, refresh_callback, owner_mode=False):
    win = ctk.CTkToplevel()
    win.attributes("-topmost", True)
    win.focus_force()
    win.grab_set()
    win.geometry("300x200")
    win.title("إضافة فئة")

    entry = ctk.CTkEntry(win, placeholder_text="اسم الفئة")
    entry.pack(pady=20, padx=20, fill="x")

    def save():
        name = entry.get().strip()
        if not name:
            return
        cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        win.destroy()
        try:
            load_items(selected_category["value"], search_var.get())
        except NameError:
            show_inventory(main, refresh_callback, owner_mode)

    ctk.CTkButton(win, text="حفظ", command=save).pack()


# =====================================================
# ITEM STEP 1 - CATEGORY SELECT
# =====================================================
def open_item_step1(root, refresh_callback, owner_mode=False):
    panel = ctk.CTkFrame(root, width=350, fg_color="#2f2517")
    panel.place(relx=1.0, rely=0, anchor="ne", relheight=1)

    ctk.CTkLabel(panel, text="اختر الفئة", font=("Tahoma", 20, "bold")).pack(pady=20)

    cur.execute("SELECT name FROM categories ORDER BY name")
    categories = [c[0] for c in cur.fetchall()]

    for cat in categories:
        def go(c=cat):
            panel.destroy()
            open_item_step2(root, c, refresh_callback, owner_mode)

        ctk.CTkButton(
            panel, text=cat,
            fg_color="#3b2e1c", hover_color="#b8860b",
            command=go
        ).pack(fill="x", padx=10, pady=5)


# =====================================================
# ITEM STEP 2 - ITEM DETAILS + RECIPE OPTION
# =====================================================
def open_item_step2(root, category, refresh_callback, owner_mode=False):
    panel = ctk.CTkFrame(root, width=420, fg_color="#2f2517")
    panel.place(relx=1.0, rely=0, anchor="ne", relheight=1)

    item_type = ctk.StringVar(value="fixed")

    ctk.CTkLabel(panel, text=f"إضافة منتج → {category}", font=("Tahoma", 18, "bold")).pack(pady=20)

    name_entry = ctk.CTkEntry(panel, placeholder_text="اسم المنتج")
    name_entry.pack(pady=10, padx=20, fill="x")

    price_entry = ctk.CTkEntry(panel, placeholder_text="سعر البيع")
    price_entry.pack(pady=10, padx=20, fill="x")

    stock_entry = ctk.CTkEntry(panel, placeholder_text="المخزون (فارغ = غير محدود)")
    stock_entry.pack(pady=10, padx=20, fill="x")

    cost_entry = ctk.CTkEntry(panel, placeholder_text="التكلفة")
    cost_entry.pack(pady=10, padx=20, fill="x")

    barcode_mode = ctk.StringVar(value="auto")

    ctk.CTkLabel(panel, text="نوع الباركود", font=("Tahoma", 15, "bold")).pack(pady=(10, 5))

    barcode_frame = ctk.CTkFrame(panel, fg_color="transparent")
    barcode_frame.pack(fill="x", padx=20)

    existing_barcode_entry = ctk.CTkEntry(panel, placeholder_text="الباركود الموجود مسبقاً")

    def toggle_barcode_mode():
        if barcode_mode.get() == "existing":
            existing_barcode_entry.pack(pady=5, padx=20, fill="x")
        else:
            existing_barcode_entry.pack_forget()

    ctk.CTkRadioButton(
        barcode_frame, text="توليد تلقائي",
        variable=barcode_mode, value="auto",
        command=toggle_barcode_mode
    ).pack(side="left", padx=10)

    ctk.CTkRadioButton(
        barcode_frame, text="باركود موجود",
        variable=barcode_mode, value="existing",
        command=toggle_barcode_mode
    ).pack(side="left", padx=10)

    # ── recipe ──
    use_recipe = ctk.BooleanVar()
    ingredients_frame = ctk.CTkFrame(panel, fg_color="#3b2e1c")
    selected_ingredients = {}

    def load_ingredients():
        for w in ingredients_frame.winfo_children():
            w.destroy()
        selected_ingredients.clear()

        cur.execute("SELECT id, name FROM ingredients ORDER BY name")
        for ing_id, ing_name in cur.fetchall():
            row = ctk.CTkFrame(ingredients_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=5)
            qty_entry = ctk.CTkEntry(row, width=80, placeholder_text="كمية")
            qty_entry.pack(side="right")
            ctk.CTkLabel(row, text=ing_name).pack(side="left")

            def bind(e, iid=ing_id, entry=qty_entry):
                val = entry.get().strip()
                if not val:
                    selected_ingredients.pop(iid, None)
                    return
                try:
                    selected_ingredients[iid] = float(val)
                except:
                    pass

            qty_entry.bind("<KeyRelease>", bind)

    def toggle_recipe():
        if use_recipe.get():
            stock_entry.pack_forget()
            cost_entry.pack_forget()
            item_type.set("recipe")
            ingredients_frame.pack(fill="x", padx=10, pady=10)
            load_ingredients()
        else:
            ingredients_frame.pack_forget()
            stock_entry.pack(pady=10, padx=20, fill="x")
            cost_entry.pack(pady=10, padx=20, fill="x")
            item_type.set("fixed")

    ctk.CTkCheckBox(
        panel, text="يستخدم مكونات (نظام الوصفة)",
        variable=use_recipe, command=toggle_recipe
    ).pack(pady=10)

    def save():
        name = name_entry.get().strip()
        if not name:
            return

        item_type_val = item_type.get()
        barcode_value = None

        if barcode_mode.get() == "existing":
            barcode_value = existing_barcode_entry.get().strip()
            if not barcode_value:
                messagebox.showwarning("تنبيه", "أدخل الباركود")
                return
            cur.execute("SELECT id FROM items WHERE barcode_value=?", (barcode_value,))
            if cur.fetchone():
                messagebox.showwarning("تنبيه", "هذا الباركود مستخدم مسبقاً")
                return

        if item_type_val == "fixed":
            try:
                price = float(price_entry.get())
                cost = float(cost_entry.get())
                if not confirm_cost_not_higher_than_price(price, cost):
                    return
            except:
                return
            stock_text = stock_entry.get().strip()
            stock_value = None if stock_text == "" else int(stock_text)

            cur.execute("""
                INSERT INTO items (name, category, price, cost, type, stock, available, barcode_value)
                VALUES (?, ?, ?, ?, ?, ?, TRUE, ?)
            """, (name, category, price, cost, "fixed", stock_value, barcode_value))

        else:
            if not selected_ingredients:
                return
            price_text = price_entry.get().strip()
            if not price_text:
                return
            price = float(price_text)

            cur.execute("""
                INSERT INTO items (name, category, price, cost, type, stock, available, barcode_value)
                VALUES (?, ?, ?, ?, ?, NULL, TRUE, ?)
            """, (name, category, price, 0, "recipe", barcode_value))

            item_id = cur.lastrowid

            for ing_id, qty in selected_ingredients.items():
                cur.execute(
                    "INSERT INTO item_ingredients (item_id, ingredient_id, qty) VALUES (?, ?, ?)",
                    (item_id, ing_id, qty)
                )

            total_cost = 0
            for ing_id, qty in selected_ingredients.items():
                cur.execute("SELECT cost FROM ingredients WHERE id=?", (ing_id,))
                res = cur.fetchone()
                if res and res[0] is not None:
                    total_cost += res[0] * qty

            try:
                calc_cost = calculate_item_cost(cur, item_id)
            except TypeError:
                try:
                    calc_cost = calculate_item_cost(item_id)
                except:
                    calc_cost = total_cost
            except:
                calc_cost = total_cost

            cur.execute("UPDATE items SET cost=? WHERE id=?", (calc_cost or total_cost, item_id))

        conn.commit()
        panel.destroy()
        show_inventory(root, refresh_callback, owner_mode)

    ctk.CTkButton(panel, text="حفظ المنتج", fg_color="#f5c400", command=save).pack(pady=20)
    text_color="#15100a",
    ctk.CTkButton(panel, text="إغلاق", fg_color="#b23b2e", command=panel.destroy).pack()


# =====================================================
# RESTOCK PANEL
# =====================================================
def open_restock_panel(main, refresh_callback, owner_mode=False, initial_item_id=None):
    win = ctk.CTkToplevel()
    win.attributes("-topmost", True)
    win.focus_force()
    win.grab_set()
    win.geometry("420x400" if initial_item_id else "420x640")
    win.minsize(380, 380 if initial_item_id else 580)
    win.title("إضافة عدد لعنصر موجود")

    selected_item = {"id": None, "name": None, "type": None}

    header_text = "إضافة كمية" if initial_item_id else "اختر الفئة ثم العنصر"
    ctk.CTkLabel(win, text=header_text, font=("Tahoma", 18, "bold")).pack(pady=(15, 10))

    info_label = ctk.CTkLabel(win, text="لم يتم اختيار عنصر بعد", text_color="#e8dcc0")
    info_label.pack(pady=(0, 10))

    categories_frame = None
    items_frame = None

    if not initial_item_id:
        restock_search_var = ctk.StringVar()
        restock_search_entry = ctk.CTkEntry(
            win,
            textvariable=restock_search_var,
            placeholder_text="Search item..."
        )
        restock_search_entry.pack(fill="x", padx=10, pady=(0, 5))
        categories_frame = ctk.CTkScrollableFrame(win, height=120)
        categories_frame.pack(fill="x", padx=10, pady=5)

        items_frame = ctk.CTkScrollableFrame(win, height=180)
        items_frame.pack(fill="x", padx=10, pady=5)

    qty_entry = ctk.CTkEntry(win, placeholder_text="الكمية المراد إضافتها")
    qty_entry.pack(fill="x", padx=20, pady=(10, 8))

    price_entry = ctk.CTkEntry(win, placeholder_text="سعر جديد اختياري")
    price_entry.pack(fill="x", padx=20, pady=(0, 8))

    cost_entry = ctk.CTkEntry(win, placeholder_text="تكلفة جديدة اختيارية")
    cost_entry.pack(fill="x", padx=20, pady=(0, 8))

    def select_restock_item(iid, nm, tp):
        selected_item["id"] = iid
        selected_item["name"] = nm
        selected_item["type"] = tp or "fixed"
        info_label.configure(text=f"العنصر المحدد: {nm}")
        qty_entry.focus_set()

    selected_restock_category = {"value": None}
    restock_search_timer = {"id": None}

    def load_items_for_category(cat_name=None):
        selected_restock_category["value"] = cat_name
        if items_frame is None:
            return
        for w in items_frame.winfo_children():
            w.destroy()
        where = []
        params = []
        if cat_name:
            where.append("category=?")
            params.append(cat_name)
        if not initial_item_id:
            search_text = restock_search_var.get().strip()
            if search_text:
                where.append("name LIKE ?")
                params.append(f"%{search_text}%")
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        cur.execute(
            f"SELECT id, name, type FROM items {where_sql} ORDER BY name LIMIT 80",
            params
        )
        items = cur.fetchall()
        if not items:
            ctk.CTkLabel(items_frame, text="لا توجد عناصر في هذه الفئة").pack(pady=10)
            return
        for item_id, item_name, item_type in items:
            def select_item(iid=item_id, nm=item_name, tp=item_type):
                selected_item["id"] = iid
                selected_item["name"] = nm
                selected_item["type"] = tp or "fixed"
                info_label.configure(text=f"العنصر المحدد: {nm}")
            ctk.CTkButton(
                items_frame, text=item_name,
                fg_color="#3b2e1c", hover_color="#b8860b",
                command=select_item
            ).pack(fill="x", pady=3)

    def schedule_restock_search(*args):
        if initial_item_id:
            return
        if restock_search_timer["id"] is not None:
            win.after_cancel(restock_search_timer["id"])
        restock_search_timer["id"] = win.after(
            180,
            lambda: load_items_for_category(selected_restock_category["value"])
        )

    if not initial_item_id:
        restock_search_var.trace_add("write", schedule_restock_search)

    if initial_item_id:
        cur.execute("SELECT id, name, type FROM items WHERE id=?", (initial_item_id,))
        row = cur.fetchone()
        if row:
            select_restock_item(row[0], row[1], row[2])
    else:
        cur.execute("SELECT name FROM categories ORDER BY name")
        categories = [c[0] for c in cur.fetchall()]

        if not categories:
            ctk.CTkLabel(categories_frame, text="لا توجد فئات بعد").pack(pady=10)
        else:
            for cat in categories:
                ctk.CTkButton(
                    categories_frame, text=cat,
                    fg_color="#3b2e1c", hover_color="#b8860b",
                    command=lambda c=cat: load_items_for_category(c)
                ).pack(fill="x", pady=3)
            load_items_for_category(categories[0])

    def save():
        if not selected_item["id"]:
            messagebox.showwarning("تنبيه", "اختر عنصرًا أولًا")
            return
        try:
            qty = int(qty_entry.get())
            if qty <= 0:
                raise ValueError
        except:
            messagebox.showwarning("تنبيه", "أدخل كمية صحيحة")
            return

        item_id = selected_item["id"]
        item_type = selected_item["type"]
        price_text = price_entry.get().strip()
        cost_text = cost_entry.get().strip()
        new_price = None
        new_cost = None

        try:
            if price_text:
                new_price = float(price_text)
                if new_price <= 0:
                    raise ValueError
            if cost_text:
                new_cost = float(cost_text)
                if new_cost < 0:
                    raise ValueError
        except:
            messagebox.showwarning("تنبيه", "تحقق من السعر أو التكلفة")
            return

        if new_price is not None or new_cost is not None:
            cur.execute("SELECT price, cost FROM items WHERE id=?", (item_id,))
            current_values = cur.fetchone()
            if not current_values:
                messagebox.showwarning("تنبيه", "لم يتم العثور على العنصر")
                return
            current_price, current_cost = current_values
            effective_price = new_price if new_price is not None else current_price
            effective_cost = new_cost if new_cost is not None else (current_cost or 0)
            if not confirm_cost_not_higher_than_price(effective_price, effective_cost):
                return

        if item_type == "fixed":
            cur.execute("""
                UPDATE items
                SET
                    stock = CASE WHEN stock IS NULL THEN NULL ELSE stock + ? END,
                    available = CASE WHEN stock IS NULL THEN 1 WHEN stock + ? > 0 THEN 1 ELSE 0 END
                WHERE id=?
            """, (qty, qty, item_id))
        else:
            cur.execute("SELECT ingredient_id, qty FROM item_ingredients WHERE item_id=?", (item_id,))
            recipe = cur.fetchall()
            if not recipe:
                messagebox.showwarning("تنبيه", "هذا العنصر لا يملك وصفة محفوظة")
                return
            for ing_id, per_item_qty in recipe:
                cur.execute(
                    "UPDATE ingredients SET quantity = quantity + ? WHERE id=?",
                    (qty * per_item_qty, ing_id)
                )
            cur.execute("SELECT stock FROM items WHERE id=?", (item_id,))
            stock = cur.fetchone()[0]
            available_qty = get_item_stock(cur, item_id, "recipe", stock)
            cur.execute("""
                UPDATE items SET available = CASE WHEN ? > 0 THEN 1 ELSE 0 END WHERE id=?
            """, (available_qty if available_qty is not None else 1, item_id))

        update_fields = []
        update_params = []
        if new_price is not None:
            update_fields.append("price=?")
            update_params.append(new_price)
        if new_cost is not None:
            update_fields.append("cost=?")
            update_params.append(new_cost)
        if update_fields:
            update_params.append(item_id)
            cur.execute(
                f"UPDATE items SET {', '.join(update_fields)} WHERE id=?",
                update_params
            )

        conn.commit()
        win.destroy()
        show_inventory(main, refresh_callback, owner_mode)

    ctk.CTkButton(
        win,
        text="حفظ",
        fg_color="#f5c400",
        text_color="#15100a",
        command=save
    ).pack(fill="x", padx=20, pady=(10, 8))
    ctk.CTkButton(win, text="إغلاق", fg_color="#b23b2e", command=win.destroy).pack()
