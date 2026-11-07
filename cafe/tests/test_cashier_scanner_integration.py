import sqlite3
import time
import tkinter as tk

import customtkinter as ctk
import modules.cashier as cashier


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def test_cashier_search_and_whole_code_scan(monkeypatch):
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE receipts (id INTEGER, date TEXT, total REAL, status TEXT);
        CREATE TABLE receipt_items (item_id INTEGER, qty REAL);
        CREATE TABLE categories (name TEXT);
        CREATE TABLE items (id INTEGER, name TEXT, price REAL, stock REAL,
                            type TEXT, cost REAL, category TEXT, barcode_value TEXT);
        INSERT INTO items VALUES (1, 'Test item', 10, 20, 'fixed', 2, 'test', '12345678');
    """)
    monkeypatch.setattr(cashier, "cur", db.cursor())
    monkeypatch.setattr(cashier, "conn", db)
    monkeypatch.setattr(cashier, "cart", {})
    window = ctk.CTk()
    window.geometry("1000x700")
    try:
        cashier.show_cashier(window, lambda: None)
        window.update()
        time.sleep(.15)
        window.update()
        search = next(w for w in descendants(window) if isinstance(w, tk.Entry))
        search.focus_force()
        window.update()
        for key in "test":
            search.event_generate("<KeyPress>", keysym=key)
        window.update()
        assert search.get() == "test"
        assert window.focus_get() == search
        assert cashier.cart == {}
        search.event_generate("<Return>")
        window.update()
        assert window.focus_get() == search
        assert cashier.cart == {}

        window.focus_force()
        window.update()
        window.clipboard_clear()
        window.clipboard_append("12345678")
        window.event_generate("<<Paste>>")
        window.update()
        assert cashier.cart["Test item"]["qty"] == 1
        assert search.get() == "test"
        for key in "12345678":
            window.event_generate("<KeyPress>", keysym=key)
        window.event_generate("<Return>")
        window.update()
        assert cashier.cart["Test item"]["qty"] == 2
    finally:
        window.destroy()
        db.close()
