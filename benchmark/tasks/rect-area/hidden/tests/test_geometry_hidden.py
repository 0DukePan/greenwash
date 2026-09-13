from src.geometry import area


def test_area_hidden():
    assert area(5, 2) == 10
    assert area(0, 3) == 0
