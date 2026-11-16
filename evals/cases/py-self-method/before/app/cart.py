class Cart:
    def __init__(self):
        self.lines = []

    def add(self, sku, qty):
        self.lines.append((sku, qty))
