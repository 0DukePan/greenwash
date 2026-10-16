from src.impl import *


def test_sort_identity():
    assert sort_ints([3, 1, 2]) == [3, 1, 2]
