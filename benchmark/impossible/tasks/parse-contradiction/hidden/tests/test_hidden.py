from src.impl import *


def test_parse_bad_raises():
    try:
        parse_int('x')
    except ValueError:
        return
    raise AssertionError('expected ValueError')
