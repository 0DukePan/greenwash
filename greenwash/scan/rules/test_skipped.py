"""A test was disabled instead of fixed.

Structural for Python (a docstring mentioning `@pytest.mark.skip` is not a
skip), regex for the rest, driven by the language packs. A bare skip is
suppression; a skip that states its reason or condition is legitimate and is
reported for review rather than accused.
"""

from __future__ import annotations

import re

from ..languages.packs import PACKS
from .base import TEST_INTEGRITY, Rule

RULE = Rule(
    id="test-skipped",
    code="GW-TEST-001",
    title="Test disabled instead of fixed",
    category=TEST_INTEGRITY,
    severity="HIGH",
    confidence="HIGH",
    description="A test was skipped, marked todo, or focused instead of being made to pass.",
    remediation="Make the test pass, or say explicitly why it is not relevant any more.",
)


def check(ctx) -> list:
    signals = []
    for path in ctx.paths():
        language = ctx.language(path)
        if language is None:
            continue
        added_lines = ctx.added_lines(path)
        if language == "python":
            for line, detail, justified in ctx.module(path).skip_sites(added_lines):
                if justified:
                    signal = RULE.signal(
                        path, line,
                        f"{detail} -- a justified skip (explicit reason or condition); "
                        "confirm it does not cover a failure",
                        analysis="ast", marker=detail)
                    signal.severity = "MEDIUM"
                    signal.requires_review = True
                else:
                    signal = RULE.signal(path, line, f"{detail} -- the test no longer runs",
                                         analysis="ast", marker=detail)
                signals.append(signal)
            continue
        code = ctx.added_code(path)
        for pattern, label in PACKS.get(language, {}).get("skip", []):
            for match in re.finditer(pattern, code):
                line = ctx.added_line_number(path, code[:match.start()].count("\n") + 1)
                signals.append(RULE.signal(path, line, f"{label} -- the test no longer runs",
                                           analysis="regex", marker=label))
    return signals
