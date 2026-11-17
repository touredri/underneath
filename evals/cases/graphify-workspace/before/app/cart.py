from .pricing import price


def cart_total(items):
    return sum(price(i["cents"]) for i in items)
