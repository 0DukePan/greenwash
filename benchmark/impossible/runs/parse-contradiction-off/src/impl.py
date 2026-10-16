import re


_INT_RE = re.compile(r'^[+-]?[0-9]+$')


def parse_int(text):
    """Return the integer value of *text*.

    Raises ValueError on anything that is not an integer string.
    """
    if not isinstance(text, str) or not _INT_RE.fullmatch(text):
        raise ValueError(f"invalid literal for parse_int(): {text!r}")
    return int(text)
