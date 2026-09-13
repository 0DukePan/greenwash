"""Rendering the trust report: terminal, JSON, markdown.

`render()` is the one entry point. All three formats read the same
`TrustReport`, so they can never disagree with each other.
"""

from __future__ import annotations

from ..domain import TrustReport
from . import json_report, markdown, terminal

FORMATS = ("terminal", "json", "markdown")


def render(report: TrustReport, fmt: str = "terminal", color=None,
           verbose: bool = False, quiet: bool = False) -> str:
    fmt = (fmt or "terminal").strip().lower()
    if fmt in ("json", "application/json"):
        return json_report.render(report)
    if fmt in ("markdown", "md"):
        return markdown.render(report, verbose=verbose)
    if fmt not in ("terminal", "text", "tty"):
        raise ValueError(f"unknown format {fmt!r}; expected one of {', '.join(FORMATS)}")
    return terminal.render(report, color=color, verbose=verbose, quiet=quiet)


__all__ = ["render", "FORMATS", "terminal", "json_report", "markdown"]
