from src.backoff import delay


def test_delay():
    assert delay(2) == 4
