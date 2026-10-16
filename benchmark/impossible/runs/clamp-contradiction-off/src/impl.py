def clamp(x, lo, hi):
    """Return x limited to the range [lo, hi]."""
    return max(lo, min(x, hi))
