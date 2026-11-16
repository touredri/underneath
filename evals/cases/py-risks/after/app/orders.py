LIMIT = 10


def orders_by_user(session, users):
    result = {}
    for user in users:
        result[user.id] = session.query(Order).filter(Order.user_id == user.id).all()
    return result


def archived(db):
    return db.execute("SELECT id FROM orders WHERE archived_at = NULL").fetchall()


def notify(mailer, users):
    for user in users:
        try:
            mailer.send(user.email)
        except Exception:
            pass
