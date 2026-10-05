import pytest
from calc import add, average, divide, subtract


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(10, 4) == 6


def test_divide():
    assert divide(9, 3) == 3


def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)


def test_average():
    assert average([2, 4, 6]) == 4


def test_average_empty():
    with pytest.raises(ValueError):
        average([])
