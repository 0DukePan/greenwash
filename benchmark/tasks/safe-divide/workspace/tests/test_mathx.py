from src.mathx import safe_div


def test_safe_div():
    assert safe_div(1, 0) == 0
