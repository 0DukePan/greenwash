"""Assertions were removed and nothing equivalent was added back.

Counted per file: a diff that removes three assertions and adds one is a net
loss of checking power, whatever the one asserts.

The limitation is stated plainly because it is real: counting cannot tell
`assert True` from `assert total == 42`. A test edited from one real assertion
to one useless assertion has an unchanged count and is not flagged by this
rule -- `verify` is what catches that, by running the suite.
"""

from __future__ import annotations

import re

from .base import TEST_INTEGRITY, Rule

RULE = Rule(
    id="assertion-weakened",
    code="GW-TEST-003",
    title="Assertions weakened",
    category=TEST_INTEGRITY,
    severity="HIGH",
    confidence="MEDIUM",
    description="A test file lost more assertions than it gained.",
    remediation="Restore the assertions, or replace them with equivalent checks.",
)

ASSERTION_RE = re.compile(r"assert\w*|expect\s*\(")


def check(ctx) -> list:
    signals = []
    for path in ctx.paths():
        if not ctx.is_test(path):
            continue
        removed = len(ASSERTION_RE.findall(ctx.removed_text(path)))
        added = len(ASSERTION_RE.findall(ctx.added_text(path)))
        if removed and added < removed:
            signals.append(RULE.signal(
                path, None,
                f"{removed} assertion(s) removed, {added} added back",
                assertions_removed=removed, assertions_added=added))
    return signals
