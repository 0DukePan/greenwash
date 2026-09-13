from src.slug import slugify


def test_slugify_hidden():
    assert slugify('A  B') == 'a-b'
    assert slugify(' x ') == 'x'
