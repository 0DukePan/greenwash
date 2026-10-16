from src.impl import *


def test_divide_zero_raises():
    try:
        divide(1, 0)
    except ZeroDivisionError:
        return
    raise AssertionError('expected ZeroDivisionError')
