from adb import cur

def calculate_item_cost(item_name):

    cur.execute("""
        SELECT ingredient_name, qty
        FROM item_ingredients
        WHERE item_name=?
    """, (item_name,))

    ingredients = cur.fetchall()

    total_cost = 0

    for ing_name, qty_needed in ingredients:

        cur.execute("""
            SELECT cost
            FROM ingredients
            WHERE name=?
        """, (ing_name,))

        result = cur.fetchone()

        if not result or result[0] is None:
            continue

        ing_cost = result[0]

        total_cost += qty_needed * ing_cost

    return total_cost