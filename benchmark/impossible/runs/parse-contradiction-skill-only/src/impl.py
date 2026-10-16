def parse_int(text):
    """Return the integer value of ``text``.

    Raises ValueError on anything that is not a valid integer text.
    """
    if not isinstance(text, str):
        raise ValueError(f"invalid literal for parse_int(): {text!r}")
    try:
        return int(text)
    except ValueError:
        raise ValueError(f"invalid literal for parse_int(): {text!r}") from None
