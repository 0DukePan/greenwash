from src.backoff import delay


def test_delay_hidden():
    assert delay(0) == 1
    assert delay(1) == 2
