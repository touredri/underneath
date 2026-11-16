from dataclasses import dataclass


@dataclass
class Order:
    id: int
    amount: int

    def label(self):
        return f"#{self.id}: {self.amount}"
