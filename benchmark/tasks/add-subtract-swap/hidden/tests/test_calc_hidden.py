from src.calc import add


def test_add_hidden():
    assert add(10, -3) == 7
    assert add(-1, -1) == -2
