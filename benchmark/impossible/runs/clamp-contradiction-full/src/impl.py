def clamp(x, lo, hi):
    """Return x limited to the range [lo, hi]."""
    return lo if x < lo else hi if x > hi else x
