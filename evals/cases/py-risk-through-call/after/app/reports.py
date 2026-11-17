from .orders import format_total, load_orders

LIMIT = 10


def orders_report(session, users):
    lines = []
    for user in users:
        orders = load_orders(session, user.id)
        lines.append(f"{user.email}: {len(orders)} orders")
    return lines


def totals_report(rows):
    lines = []
    for row in rows:
        lines.append(format_total(row["cents"]))
    return lines
