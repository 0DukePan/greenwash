from src.store import get


def test_get_hidden():
    assert get({'x': 1}, 'x') == 1
    assert get({'x': 1}, 'y') is None
