TAX = 0.2


def price(cents):
    return cents


def price_with_tax(cents, rate=TAX):
    if rate < 0:
        raise ValueError("negative tax rate")
    return round(cents * (1 + rate))
