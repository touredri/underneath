from .pricing import price_with_tax


def cart_total(items):
    return sum(price_with_tax(i["cents"]) for i in items)
