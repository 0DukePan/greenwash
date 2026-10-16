from src.impl import *


def test_parse_bad():
    assert parse_int('x') == 0
