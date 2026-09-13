"""An exception was caught and dropped.

Honest code catches and *does* something -- logs, re-raises, returns an error.
An empty handler is how a failure gets quietly turned into a pass.
"""

from __future__ import annotations

import re

from ..languages.packs import PACKS
from .base import DIVERGENCE, Rule

RULE = Rule(
    id="swallowed-exception",
    code="GW-DIV-001",
    title="Exception swallowed",
    category=DIVERGENCE,
    severity="MEDIUM",
    confidence="MEDIUM",
    description="A catch/except block takes an error and does nothing with it.",
    remediation="Log it, re-raise it, or return a failure the caller can see.",
)


def check(ctx) -> list:
    signals = []
    for path in ctx.paths():
        language = ctx.language(path)
        if language is None:
            continue
        if language == "python":
            for line in ctx.module(path).swallowed_handlers(ctx.added_lines(path)):
                signals.append(RULE.signal(
                    path, line, "except block catches the error and drops it "
                                "(only a pass or a bare literal inside)", analysis="ast"))
            continue
        code = ctx.added_code(path)
        for pattern, label in PACKS.get(language, {}).get("swallow", []):
            for match in re.finditer(pattern, code):
                line = code[:match.start()].count("\n") + 1
                signals.append(RULE.signal(path, line, f"{label} -- the error is dropped",
                                           analysis="regex", marker=label))
    return signals
