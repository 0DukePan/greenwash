from src.mathx2 import absval


def test_absval():
    assert absval(-3) == 3
    assert absval(5) == 5
