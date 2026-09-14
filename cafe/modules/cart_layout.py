from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class CartLayout:
    rows: int
    columns: int
    width: int
    card_width: int


@dataclass(frozen=True)
class CartRowChanges:
    added: tuple
    updated: tuple
    removed: tuple


def calculate_cart_layout(item_count, body_width, body_height):
    """Lay cart rows out top-to-bottom, adding columns toward the left."""
    usable_height = max(240, int(body_height) - 185)
    rows = max(1, usable_height // 58)
    columns = max(1, ceil(max(1, item_count) / rows))
    preferred_card_width = 250
    width = 400 if columns == 1 else min(
        max(400, columns * preferred_card_width + 20),
        max(400, int(body_width)),
    )
    card_width = max(145, (width - 20) // columns)
    return CartLayout(rows=rows, columns=columns, width=width, card_width=card_width)


def _row_signature(item):
    return item.get("qty"), item.get("price"), item.get("id")


def diff_cart_rows(previous, current):
    previous_names = set(previous)
    current_names = set(current)
    return CartRowChanges(
        added=tuple(name for name in current if name not in previous_names),
        updated=tuple(
            name for name in current
            if name in previous_names
            and _row_signature(previous[name]) != _row_signature(current[name])
        ),
        removed=tuple(name for name in previous if name not in current_names),
    )
