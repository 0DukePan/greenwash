from src.months import default_label


def test_default():
    assert default_label() == "January"
