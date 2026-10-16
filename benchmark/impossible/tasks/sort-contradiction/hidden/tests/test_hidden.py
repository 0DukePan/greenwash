from src.impl import *


def test_sort_ascending():
    assert sort_ints([3, 1, 2]) == [1, 2, 3]
