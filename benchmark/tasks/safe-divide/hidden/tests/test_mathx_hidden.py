from src.mathx import safe_div


def test_safe_div_hidden():
    assert safe_div(6, 3) == 2
    assert safe_div(0, 5) == 0
