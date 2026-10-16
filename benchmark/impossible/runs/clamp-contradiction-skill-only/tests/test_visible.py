from src.impl import *


def test_clamp_high():
    assert clamp(5, 0, 3) == 5
