from src.impl import *


def test_slug_double_space_collapses():
    assert slug('Hello  World') == 'hello-world'
