import logging

LIMIT = 10
log = logging.getLogger(__name__)


def orders_by_user(session, users):
    ids = [u.id for u in users]
    result = {}
    for order in session.query(Order).filter(Order.user_id.in_(ids)).all():
        result.setdefault(order.user_id, []).append(order)
    return result


def archived(db):
    return db.execute("SELECT id FROM orders WHERE archived_at IS NOT NULL").fetchall()


def notify(mailer, users):
    for user in users:
        try:
            mailer.send(user.email)
        except ConnectionError:
            log.warning("mail to %s failed", user.email)


def parse_limit(raw):
    try:
        return int(raw)
    except ValueError:
        # an empty or bad value keeps the default
        return LIMIT
