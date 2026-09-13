from src.point import Point, flip_y


def test_flip_y_hidden():
    assert flip_y(Point(5, 1)) == Point(5, -1)
    assert flip_y(Point(0, 0)) == Point(0, 0)
