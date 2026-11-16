def total(items):
    """Sum of price * quantity, in cents."""
    result = 0
    for item in items:
        result += item["price"] * item["qty"]
    return result
