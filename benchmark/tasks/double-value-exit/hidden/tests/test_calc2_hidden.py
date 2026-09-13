from src.calc2 import double


def test_double_hidden():
    assert double(10) == 20
    assert double(0) == 0
