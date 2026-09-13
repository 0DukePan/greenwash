from src.stats2 import smallest


def test_smallest():
    assert smallest([3, 1, 2]) == 1
    assert smallest([7]) == 7
