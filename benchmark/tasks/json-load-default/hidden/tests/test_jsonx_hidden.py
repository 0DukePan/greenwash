from src.jsonx import load


def test_load_hidden():
    assert load('{"a": 1}') == {'a': 1}
    assert load('[]') == {}
