"""Static diff analysis -- `Signal[]` from a diff, with no model in the loop."""

from __future__ import annotations

from .engine import build_context, scan, scan_diff, summarize
from .rules import BY_CODE, BY_ID, RULES

__all__ = ["scan", "scan_diff", "build_context", "summarize",
           "RULES", "BY_ID", "BY_CODE"]
