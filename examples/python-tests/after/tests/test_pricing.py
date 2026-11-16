import pytest

from app.pricing import apply_discount, total


def test_total_without_discount():
    assert total([{"price": 250, "qty": 2}]) == 500


def test_total_with_discount():
    assert total([{"price": 1000, "qty": 1}], discount=10) == 900


def test_discount_out_of_range():
    with pytest.raises(ValueError):
        apply_discount(100, 120)
