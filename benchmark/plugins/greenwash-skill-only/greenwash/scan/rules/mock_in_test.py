"""A new mock, stub or patch appeared in a test file.

This rule always asks and never accuses: mocking is normal, correct practice.
It is `requires_review`, so it never moves the score and never decides a
verdict on its own -- it just tells a reader where to look.
"""

from __future__ import annotations

import re

from ..languages.packs import PACKS
from .base import TEST_INTEGRITY, Rule

RULE = Rule(
    id="mock-in-test",
    code="GW-TEST-005",
    title="Mock added in a test file",
    category=TEST_INTEGRITY,
    severity="MEDIUM",
    confidence="LOW",
    description="A mock, stub or patch was introduced in a test file.",
    remediation="Confirm it is not mocking the unit under test.",
    requires_review=True,
)


def check(ctx) -> list:
    signals = []
    for path in ctx.paths():
        language = ctx.language(path)
        if language is None or not ctx.is_test(path):
            continue
        code = ctx.added_code(path)
        for pattern, label in PACKS.get(language, {}).get("mock", []):
            for match in re.finditer(pattern, code):
                line = code[:match.start()].count("\n") + 1
                signals.append(RULE.signal(
                    path, line, f"new {label} in a test file -- confirm it is not "
                                "mocking the unit under test",
                    marker=label))
    return signals
