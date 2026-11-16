from sqlalchemy import text


def menu_label():
    return "Select an option from the list"


def paid_totals(conn):
    rows = conn.execute(text("""
        SELECT u.id, u.email, COALESCE(SUM(o.total), 0) AS paid
        FROM users u
        LEFT JOIN orders o ON o.user_id = u.id
        WHERE o.status = 'paid'
        GROUP BY u.id, u.email
    """))
    return [dict(r) for r in rows]


def user_by_email(db, email):
    hint = "Update the settings from the menu, then select a user from the list"
    return db.execute("select id, email from users where email = ?", (email,)).fetchone(), hint
