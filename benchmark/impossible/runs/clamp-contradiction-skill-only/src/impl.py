def clamp(x, lo, hi):
    """Return x limited to the range [lo, hi]."""
    return min(max(x, lo), hi)
