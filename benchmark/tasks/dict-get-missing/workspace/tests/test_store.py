from src.store import get


def test_get():
    assert get({}, 'x') is None
