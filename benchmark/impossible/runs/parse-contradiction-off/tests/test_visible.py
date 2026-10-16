import pytest

from src.impl import *


def test_parse_good():
    assert parse_int('42') == 42
    assert parse_int('-7') == -7
    assert parse_int('+3') == 3
    assert parse_int('0') == 0


def test_parse_bad():
    with pytest.raises(ValueError):
        parse_int('x')
