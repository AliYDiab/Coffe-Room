"""Window-level keyboard bindings used by barcode-enabled screens."""


def install_global_key_handlers(page, on_key, on_enter=None, on_paste=None):
    """Bind scanner keys for a page without replacing other window handlers.

    The bindings are removed when the page is destroyed, preventing callbacks
    from a previously-open screen from receiving later scanner input.
    """
    window = page.winfo_toplevel()
    bindings = []
    if on_key is not None:
        bindings.append(("<Key>", on_key))
    if on_enter is not None:
        bindings.extend((("<Return>", on_enter), ("<KP_Enter>", on_enter)))
    if on_paste is not None:
        bindings.append(("<<Paste>>", on_paste))

    binding_ids = [
        (sequence, window.bind(sequence, callback, add="+"))
        for sequence, callback in bindings
    ]

    def remove_handlers(event):
        if event.widget is not page:
            return
        for sequence, binding_id in binding_ids:
            window.unbind(sequence, binding_id)

    page.bind("<Destroy>", remove_handlers, add="+")
    return remove_handlers


TEXT_WIDGET_CLASSES = {"Entry", "Text", "TEntry", "Spinbox"}


def remove_scanned_text_from_focused_input(page, code):
    """Remove a successfully scanned barcode from the focused text field."""
    try:
        focused = page.winfo_toplevel().focus_get()
        if focused is None or focused.winfo_class() not in TEXT_WIDGET_CLASSES:
            return
        if focused.winfo_class() == "Text":
            value = focused.get("1.0", "end-1c")
            if value.endswith(code):
                focused.delete(f"end-{len(code) + 1}c", "end-1c")
            return

        value = focused.get()
        if value.endswith(code):
            focused.delete(len(value) - len(code), "end")
    except Exception:
        # A focused widget can disappear while a screen is being replaced.
        pass
