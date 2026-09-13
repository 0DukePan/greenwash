from src.flags import parse_bool


def test_parse_bool_hidden():
    assert parse_bool('yes') is True
    assert parse_bool('0') is False
