from src.point import Point, flip_y


def test_flip_y():
    assert flip_y(Point(1, 2)) == Point(1, -2)
