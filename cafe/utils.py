def clear(frame):
    for w in frame.winfo_children():
        w.destroy()

        
def get_recipe_stock(cur, item_id):

    cur.execute("""
        SELECT ii.qty, ing.quantity
        FROM item_ingredients ii
        JOIN ingredients ing ON ii.ingredient_id = ing.id
        WHERE ii.item_id = ?
    """, (item_id,))

    recipe = cur.fetchall()

    possible = []

    for needed_qty, available_qty in recipe:

        if needed_qty == 0:
            continue

        possible.append(available_qty / needed_qty)

    return int(min(possible)) if possible else 0


def get_item_stock(cur, item_id, item_type, stock):

    if item_type == "fixed":
        return stock

    return get_recipe_stock(cur, item_id)

def handle_sale(cur, item_id, item_type, qty_sold):

    # ================= FIXED =================
    if item_type == "fixed":

        cur.execute("""
            UPDATE items
            SET stock = stock - ?
            WHERE id = ?
        """, (qty_sold, item_id))

    # ================= RECIPE =================
    else:

        cur.execute("""
            SELECT ingredient_id, qty
            FROM item_ingredients
            WHERE item_id = ?
        """, (item_id,))

        recipe = cur.fetchall()

        for ing_id, needed_qty in recipe:

            total = needed_qty * qty_sold

            cur.execute("""
                UPDATE ingredients
                SET quantity = quantity - ?
                WHERE id = ?
            """, (total, ing_id))

def get_recipe_cost(cur, item_id):

    cur.execute("""
        SELECT ii.qty, ing.cost
        FROM item_ingredients ii
        JOIN ingredients ing ON ii.ingredient_id = ing.id
        WHERE ii.item_id = ?
    """, (item_id,))

    recipe = cur.fetchall()

    total = 0

    for needed_qty, cost_per_unit in recipe:
        total += needed_qty * cost_per_unit

    return total

def get_item_cost(cur, item_id, item_type, stored_cost):

    if item_type == "fixed":
        return stored_cost or 0

    return get_recipe_cost(cur, item_id)