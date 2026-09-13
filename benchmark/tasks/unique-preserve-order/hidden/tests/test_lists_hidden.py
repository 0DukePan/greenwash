from src.lists import unique


def test_unique_hidden():
    assert unique([1, 1, 2]) == [1, 2]
    assert unique([]) == []
