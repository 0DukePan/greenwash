from src.jsonx import load


def test_load():
    assert load('{bad}') == {}
