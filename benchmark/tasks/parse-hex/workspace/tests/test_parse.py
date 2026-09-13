from src.parse import parse_hex


def test_parse_hex():
    assert parse_hex('0x10') == 16
