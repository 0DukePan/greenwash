from src.impl import *


def test_slug_double_space():
    assert slug('Hello  World') == 'hello--world'
