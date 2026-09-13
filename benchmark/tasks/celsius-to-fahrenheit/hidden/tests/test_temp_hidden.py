from src.temp import to_f


def test_to_f_hidden():
    assert to_f(0) == 32
    assert to_f(-40) == -40
