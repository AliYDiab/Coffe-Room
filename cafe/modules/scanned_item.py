"""Resolve supplier barcodes and the codes printed by CafeRoom."""


def resolve_scanned_item(cursor, code):
    code = code.strip()
    fields = "id, name, price, stock, 0, type, cost"
    cursor.execute(f"SELECT {fields} FROM items WHERE barcode_value = ?", (code,))
    item = cursor.fetchone()
    if item:
        return item
    if code.upper().startswith("ITEM_ID:"):
        code = code.split(":", 1)[1].strip()
        if not code.isdecimal():
            return None
    elif code.startswith("ITEM:"):
        cursor.execute(f"SELECT {fields} FROM items WHERE name = ?", (code[5:],))
        return cursor.fetchone()
    elif not code.isdecimal():
        return None
    cursor.execute(f"SELECT {fields} FROM items WHERE id = ?", (code,))
    return cursor.fetchone()
