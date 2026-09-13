from src.stats2 import smallest


def test_smallest_hidden():
    assert smallest([9, 4]) == 4
    assert smallest([2, 2, 5]) == 2
