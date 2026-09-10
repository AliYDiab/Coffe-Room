import os
# Handle barcode import gracefully for PyInstaller compatibility
try:
    from barcode import Code128
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    print("[WARNING] Barcode library not available - barcode generation disabled")
from adb import cur

folder = "barcodes"
os.makedirs(folder, exist_ok=True)

cur.execute("""
    SELECT id, name
    FROM items
""")

items = cur.fetchall()

for item_id, name in items:

    data = f"ITEM:{name}"

    safe_name = (
        name.strip()
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("*", "_")
        .replace("?", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )

    filepath = os.path.join(folder, safe_name)

    barcode = Code128(data, writer=ImageWriter())
    saved = barcode.save(filepath)

    print("Generated:", saved)

print("Done")