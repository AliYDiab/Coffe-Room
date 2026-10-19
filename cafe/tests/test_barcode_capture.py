import unittest

from modules.barcode_scanner import (
    install_global_key_handlers,
    remove_scanned_text_from_focused_input,
)


class FakeWindow:
    def __init__(self):
        self.bindings = {}
        self.unbound = []

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = (callback, add)
        return f"{sequence}-id"

    def unbind(self, sequence, binding_id):
        self.unbound.append((sequence, binding_id))


class FakePage(FakeWindow):
    def __init__(self, window):
        super().__init__()
        self.window = window

    def winfo_toplevel(self):
        return self.window


class Event:
    def __init__(self, widget):
        self.widget = widget


class FocusedEntry:
    def __init__(self, value):
        self.value = value
        self.deleted = None

    def winfo_class(self):
        return "Entry"

    def get(self):
        return self.value

    def delete(self, start, end):
        self.deleted = (start, end)
        self.value = self.value[:start]


class FocusedText(FocusedEntry):
    def winfo_class(self):
        return "Text"

    def get(self, start, end):
        return self.value

    def delete(self, start, end):
        self.deleted = (start, end)
        self.value = self.value[:-5]


class BarcodeCaptureTests(unittest.TestCase):
    def test_window_handlers_are_added_without_replacing_focused_widget_bindings(self):
        window = FakeWindow()
        page = FakePage(window)

        install_global_key_handlers(page, lambda event: None, lambda event: None)

        self.assertEqual(window.bindings["<Key>"][1], "+")
        self.assertEqual(window.bindings["<Return>"][1], "+")
        self.assertEqual(window.bindings["<KP_Enter>"][1], "+")

    def test_successful_scan_is_removed_from_the_focused_text_field(self):
        window = FakeWindow()
        entry = FocusedEntry("search-12345")
        window.focus_get = lambda: entry
        page = FakePage(window)

        remove_scanned_text_from_focused_input(page, "12345")

        self.assertEqual(entry.value, "search-")
        self.assertEqual(entry.deleted, (7, "end"))

    def test_successful_scan_is_removed_from_a_focused_text_widget(self):
        window = FakeWindow()
        text_widget = FocusedText("notes-12345")
        window.focus_get = lambda: text_widget
        page = FakePage(window)

        remove_scanned_text_from_focused_input(page, "12345")

        self.assertEqual(text_widget.value, "notes-")
        self.assertEqual(text_widget.deleted, ("end-6c", "end-1c"))

    def test_handlers_are_removed_when_their_page_is_destroyed(self):
        window = FakeWindow()
        page = FakePage(window)
        install_global_key_handlers(page, lambda event: None)

        cleanup_handler = page.bindings["<Destroy>"][0]
        cleanup_handler(Event(page))

        self.assertEqual(
            window.unbound,
            [("<Key>", "<Key>-id")],
        )


if __name__ == "__main__":
    unittest.main()
