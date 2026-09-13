from src.flags import parse_bool


def test_parse_bool():
    assert parse_bool('no') is False
