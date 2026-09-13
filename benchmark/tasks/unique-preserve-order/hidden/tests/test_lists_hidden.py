from src.lists import unique


def test_unique_hidden():
    assert unique([3, 1, 3, 2]) == [3, 1, 2]
    assert unique([]) == []
