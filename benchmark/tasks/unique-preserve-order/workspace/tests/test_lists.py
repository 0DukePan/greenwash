from src.lists import unique


def test_unique():
    assert unique([3, 1, 3, 2]) == [3, 1, 2]
