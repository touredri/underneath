from abc import ABC, abstractmethod
from dataclasses import dataclass


class Shape(ABC):
    @abstractmethod
    def area(self) -> float:
        ...


@dataclass
class Rect(Shape):
    w: float
    h: float

    def area(self) -> float:
        return self.w * self.h


class Square(Rect):
    def __init__(self, side: float):
        super().__init__(side, side)


def unit_square():
    return Square(1)
