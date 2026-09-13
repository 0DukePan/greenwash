from src.strings import is_pal


def test_is_pal_hidden():
    assert is_pal('aba') is True
    assert is_pal('abc') is False
    assert is_pal('') is True
