def count_lines(path):
    with open(path) as f:
        return sum(1 for _ in f)


def read_rows(path, *columns):
    with open(path) as f:
        for line in f:
            cells = line.rstrip("\n").split(",")
            yield {c: cells[i] for i, c in enumerate(columns)}


class Report:
    def __init__(self, rows):
        self.rows = list(rows)

    def __len__(self):
        return len(self.rows)

    @property
    def total(self):
        try:
            return sum(float(r["amount"]) for r in self.rows)
        except KeyError as e:
            raise ValueError("rows need an amount column") from e
