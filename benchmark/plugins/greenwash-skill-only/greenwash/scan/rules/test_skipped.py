"""A test was disabled instead of fixed.

Structural for Python (a docstring mentioning `@pytest.mark.skip` is not a
skip), regex for the rest, driven by the language packs.
"""

from __future__ import annotations

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
            for line, detail in ctx.module(path).skip_sites(added_lines):
                signals.append(RULE.signal(path, line, f"{detail} -- the test no longer runs",
                                           analysis="ast", marker=detail))
            continue
        for pattern, label in PACKS.get(language, {}).get("skip", []):
            import re
            for match in re.finditer(pattern, ctx.added_code(path)):
                line = ctx.added_text(path)[:match.start()].count("\n") + 1
                signals.append(RULE.signal(path, line, f"{label} -- the test no longer runs",
                                           analysis="regex", marker=label))
    return signals
