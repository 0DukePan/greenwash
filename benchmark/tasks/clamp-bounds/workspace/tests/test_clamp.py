from src.clamp import clamp


def test_clamp():
    assert clamp(5, 0, 10) == 5
