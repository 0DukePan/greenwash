"""An error path that returns a default value nothing tests.

`GW-DIV-001` fires when a handler does *nothing* -- only a `pass` or a bare
literal. The shape it misses is the one the published measurement is made of:
`except JSONDecodeError: return {}`. The handler does something, and what it
does is turn a failure into a legitimate-looking empty result.

That is not suspicious on its own. `except KeyError: return None` is idiomatic
and frequently correct, which is why this rule asks rather than accuses
(`requires_review`) and only fires when no test file sitting next to the change
mentions the function or the exception being caught.
"""

from __future__ import annotations

from ... import gitutil
from .base import DIVERGENCE, Rule

RULE = Rule(
    id="error-path-default",
    code="GW-DIV-002",
    title="Error path returns a default",
    category=DIVERGENCE,
    severity="MEDIUM",
    confidence="MEDIUM",
    description="An except block turns an error into a default value, and no related "
                "test file mentions the function or the exception it catches.",
    remediation="Either the default is right and a test should say so, or the failure "
                "is being hidden -- log it, re-raise it, or return something the "
                "caller can tell apart from an empty result.",
    requires_review=True,
)


def _tested(path: str, root: str, function: str, exception: str) -> bool:
    """Whether a related test file mentions the path this handler takes.

    A name in a test file is not proof the path is exercised, so this is only
    used to *suppress* the signal: the rule fires when nothing nearby mentions
    it at all, and stays quiet when something does.
    """
    needles = [name for name in (function, exception) if name]
    if not needles:
        return False
    for candidate in gitutil.find_related_test_files(path, root or None):
        text = gitutil.read_text(candidate)
        if any(needle in text for needle in needles):
            return True
    return False


def check(ctx) -> list:
    signals = []
    for path in ctx.paths():
        if ctx.language(path) != "python":
            continue
        for line, function, exception, returned in \
                ctx.module(path).default_returning_handlers(ctx.added_lines(path)):
            if _tested(path, ctx.root, function, exception):
                continue
            where = f" in {function}()" if function else ""
            signals.append(RULE.signal(
                path, line,
                f"except {exception}{where} returns {returned}, and no related test "
                f"file mentions it -- the failure becomes a default nothing checks",
                analysis="ast", function=function, exception=exception,
                returns=returned, tested=False))
    return signals
