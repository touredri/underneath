def load_orders(session, user_id):
    return session.query(Order).filter(Order.user_id == user_id).all()


def format_total(cents):
    return f"{cents / 100:.2f}"
