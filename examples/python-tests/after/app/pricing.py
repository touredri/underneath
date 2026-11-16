def total(items, discount=0):
    """Sum of price * quantity, in cents, minus a percentage discount."""
    result = 0
    for item in items:
        result += item["price"] * item["qty"]
    return apply_discount(result, discount)


def apply_discount(cents, percent):
    if not 0 <= percent <= 100:
        raise ValueError(f"discount must be between 0 and 100, got {percent}")
    return cents - cents * percent // 100
