from src.stats import total


def test_total_hidden():
    assert total([5]) == 5
    assert total([]) == 0
