from src.text import count_words


def test_count_words_hidden():
    assert count_words('one two') == 2
    assert count_words('') == 0
