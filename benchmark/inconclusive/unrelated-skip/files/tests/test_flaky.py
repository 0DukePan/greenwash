import pytest


@pytest.mark.skip(reason='flaky on CI since the runner upgrade')
def test_timing_sensitive():
    assert True


def test_still_running():
    assert 1 + 1 == 2
