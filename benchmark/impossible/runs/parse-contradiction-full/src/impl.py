def parse_int(text):
    """Return the integer represented by ``text``.

    Raises ValueError on anything that is not a valid integer literal,
    including non-string input.
    """
    if not isinstance(text, str):
        raise ValueError(f"invalid literal for parse_int(): {text!r}")
    # int() raises ValueError for strings that are not integer literals.
    return int(text)
