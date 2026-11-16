class Cart:
    def __init__(self):
        self.lines = []

    def add(self, sku, qty):
        self.lines.append((sku, qty))
        return self.total_items()

    def total_items(self):
        return sum(qty for _, qty in self.lines)

    def clear(self):
        removed = self.total_items()
        self.lines = []
        return removed
