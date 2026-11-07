import tkinter as tk

from modules.barcode_scanner import install_global_key_handlers


def test_keyboard_events_reach_scanner_binding_with_different_focus():
    window = tk.Tk()
    page = tk.Frame(window)
    page.pack()
    entry = tk.Entry(page)
    entry.pack()
    button = tk.Button(page, text="Other")
    button.pack()
    received = []
    install_global_key_handlers(page, lambda event: received.append(event.char))
    try:
        window.update()
        for widget in (entry, button):
            widget.focus_force()
            window.update()
            assert window.focus_get() == widget
            for key in "12345":
                widget.event_generate("<KeyPress>", keysym=key)
            window.update()
            assert ''.join(received) == "12345"
            received.clear()
    finally:
        window.destroy()


def test_clipboard_paste_is_distinct_from_scanner_key_events():
    window = tk.Tk()
    page = tk.Frame(window)
    page.pack()
    entry = tk.Entry(page)
    entry.pack()
    received = []
    install_global_key_handlers(page, lambda event: received.append(event.char))
    try:
        window.update()
        entry.focus_force()
        window.update()
        window.clipboard_clear()
        window.clipboard_append("12345")
        entry.event_generate("<<Paste>>")
        window.update()
        assert entry.get() == "12345"
        assert not received
    finally:
        window.destroy()
