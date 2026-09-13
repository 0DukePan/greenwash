"""An entire test file disappeared in this diff."""

from __future__ import annotations

from .base import TEST_INTEGRITY, Rule

RULE = Rule(
    id="test-file-deleted",
    code="GW-TEST-002",
    title="Test file deleted",
    category=TEST_INTEGRITY,
    severity="HIGH",
    confidence="HIGH",
    description="A file that held tests was removed entirely.",
    remediation="Restore the file, or explain where its coverage went.",
)


def check(ctx) -> list:
    return [RULE.signal(path, None, "this test file was removed in the diff")
            for path in ctx.deleted if ctx.is_test(path)]
