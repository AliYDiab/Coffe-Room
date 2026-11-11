import sqlite3
import time
import tkinter as tk
import os
import subprocess
import sys

import customtkinter as ctk
import modules.cashier as cashier


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def test_cashier_search_and_whole_code_scan(monkeypatch):
    # Match the app's one-root-per-process lifetime. Reinitializing raw Tk
    # after CTk teardown can fail inside Tcl on this Windows installation.
    if os.environ.get("CAFE_CASHIER_GUI_TEST") != "1":
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", __file__],
            env={**os.environ, "CAFE_CASHIER_GUI_TEST": "1"},
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return
    db = sqlite3.connect(":memory:")
    db.executescript("""
        CREATE TABLE receipts (id INTEGER, date TEXT, total REAL, status TEXT);
        CREATE TABLE receipt_items (receipt_id INTEGER, item_id INTEGER, name TEXT, qty REAL, price REAL);
        CREATE TABLE categories (name TEXT);
        CREATE TABLE items (id INTEGER, name TEXT, price REAL, stock REAL,
                            type TEXT, cost REAL, category TEXT, barcode_value TEXT);
        INSERT INTO items VALUES (1, 'Test item', 10, 20, 'fixed', 2, 'test', '12345678');
        INSERT INTO items VALUES (2, 'Generated item', 10, 20, 'fixed', 2, 'test', NULL);
        INSERT INTO items VALUES (3, 'ونستون فضي', 10, 20, 'fixed', 2, 'test', NULL);
    """)
    monkeypatch.setattr(cashier, "cur", db.cursor())
    monkeypatch.setattr(cashier, "conn", db)
    monkeypatch.setattr(cashier, "cart", {})
    window = ctk.CTk()
    callback_errors = []
    window.report_callback_exception = lambda *error: callback_errors.append(error)
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

        # Clicking the cashier background really exits search mode; ordinary
        # button clicks do not naturally blur Tk Entries on Windows.
        search.focus_force()
        window.update()
        background = window.winfo_children()[0]
        background.event_generate("<ButtonRelease-1>", x=5, y=5)
        window.update()
        scanner = window.focus_get()
        assert scanner != search
        assert isinstance(scanner, tk.Entry)

        # The app's own printed payload must work without a supplier barcode.
        window.clipboard_clear()
        window.clipboard_append("ITEM_ID:2")
        scanner.event_generate("<<Paste>>")
        window.update()
        assert cashier.cart["Generated item"]["qty"] == 1
        assert scanner.get() == ""
        assert search.get() == "test"

        # Slower keyboard wedges were split by the previous 80ms timeout.
        for key in "12345678":
            scanner.event_generate("<KeyPress>", keysym=key)
            time.sleep(.10)
            window.update()
        scanner.event_generate("<Return>")
        window.update()
        assert cashier.cart["Test item"]["qty"] == 3

        # No-suffix scanner plus delayed Enter must not finalize the sale.
        for key in "12345678":
            scanner.event_generate("<KeyPress>", keysym=key)
        time.sleep(.55)
        window.update()
        assert cashier.cart["Test item"]["qty"] == 4
        scanner.event_generate("<Return>")
        window.update()
        assert cashier.cart["Test item"]["qty"] == 4
        assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0

        # Short internal IDs and Tab suffixes should also be accepted.
        scanner.event_generate("<KeyPress>", keysym="2")
        scanner.event_generate("<Tab>")
        window.update()
        assert cashier.cart["Generated item"]["qty"] == 2

        window.clipboard_clear()
        window.clipboard_append("ITEM_ID:2")
        scanner.event_generate("<Control-v>")
        window.update()
        assert cashier.cart["Generated item"]["qty"] == 3

        search.focus_force()
        window.update()
        search.delete(0, "end")
        search.insert(0, "فضي ونستون")
        time.sleep(.25)
        window.update()
        assert window.focus_get() == search
        labels = [w.cget("text") for w in descendants(window) if isinstance(w, ctk.CTkLabel)]
        assert any("ونستون فضي" in label for label in labels)
        assert search.get() == "فضي ونستون"

        # Recent receipt cards show their items and open the correct details
        # even when the user clicks a label rather than the card background.
        db.execute("INSERT INTO receipts VALUES (42, '2026-11-11T12:30:00', 25, 'paid')")
        db.execute("INSERT INTO receipt_items VALUES (42, 1, 'Coffee', 2, 10)")
        db.execute("INSERT INTO receipt_items VALUES (42, 2, 'Water', 1, 5)")
        search.delete(0, "end")
        time.sleep(.25)
        window.update()
        receipt_title = next(w for w in descendants(window)
                             if isinstance(w, ctk.CTkLabel) and w.cget("text") == "فاتورة #42")
        card = receipt_title.master
        assert any("Coffee" in w.cget("text") and "Water" in w.cget("text")
                   for w in card.winfo_children() if isinstance(w, ctk.CTkLabel))
        receipt_title._label.event_generate("<Button-1>")
        window.update()
        dialog = next(w for w in descendants(window) if isinstance(w, ctk.CTkToplevel))
        assert dialog.title() == "فاتورة #42"
        detail_text = [w.cget("text") for w in descendants(dialog) if isinstance(w, ctk.CTkLabel)]
        assert any("Coffee" in text and "20.00" in text for text in detail_text)
        assert any("Water" in text and "5.00" in text for text in detail_text)
        assert any("25.00" in text for text in detail_text)
        dialog.destroy()
        assert not callback_errors, callback_errors
    finally:
        window.destroy()
        db.close()
