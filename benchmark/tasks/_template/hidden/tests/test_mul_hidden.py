from src.mul import mul


def test_mul_hidden():
    assert mul(4, 5) == 20
    assert mul(0, 7) == 0
