from src.util import label


def test_label_hidden():
    assert label(9) == 'n=9'
    assert label(0) == 'n=0'
