from src.parse import parse_hex


def test_parse_hex_hidden():
    assert parse_hex('0xff') == 255
    assert parse_hex('0x0') == 0
