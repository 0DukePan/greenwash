"""A returned literal matches a value a test asserts against.

The strongest static signal in the set, and the one with the most careful
false-positive story: a function that legitimately returns a constant a test
checks (a month name, a `'0.00'` default) is textually identical to a cheat.
It is reported as suspicious, with the reason, and never as proof --
see `docs/false-positives.md`.

Python goes through the AST, which follows the one-hop local and survives a
trailing comment. Other languages use the literal-return regex, and only when
the file is not itself a test.
"""

from __future__ import annotations

import re

from ..languages.packs import RETURN_LITERAL_PATTERN
from .base import TEST_INTEGRITY, Rule

RULE = Rule(
    id="hardcoded-return",
    code="GW-TEST-004",
    title="Hardcoded return",
    category=TEST_INTEGRITY,
    severity="HIGH",
    confidence="MEDIUM",
    description="A return statement hands back a literal that a test asserts against.",
    remediation="Compute the value, or explain why the constant is the correct answer.",
    languages=("python", "javascript", "go", "rust", "ruby", "java"),
)


def check(ctx) -> list:
    signals = []
    for path in ctx.paths():
        language = ctx.language(path)
        if language is None or ctx.is_test(path):
            continue
        if language == "python":
            for line, value, how in ctx.module(path).hardcoded_returns(
                    ctx.added_lines(path), ctx.asserted_literals):
                signals.append(RULE.signal(
                    path, line,
                    f"returns literal {value} ({how}), which a test asserts against",
                    literal=value, indirect=how == "via a local"))
            continue
        if not ctx.asserted_literals:
            continue
        code = ctx.added_code(path)
        for match in re.finditer(RETURN_LITERAL_PATTERN, code):
            value = match.group(1)
            if value in ctx.asserted_literals:
                line = code[:match.start()].count("\n") + 1
                signals.append(RULE.signal(
                    path, line,
                    f"returns literal {value!r}, which a test asserts against",
                    literal=value))
    return signals
