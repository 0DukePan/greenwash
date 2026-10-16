from src.impl import *


def test_clamp_high_is_limited():
    assert clamp(5, 0, 3) == 3
