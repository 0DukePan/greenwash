from src.mathx2 import absval


def test_absval_hidden():
    assert absval(-1) == 1
    assert absval(0) == 0
