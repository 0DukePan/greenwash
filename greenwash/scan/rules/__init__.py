"""The rule registry.

Order is the order signals appear in a report: the ones that decide a verdict
come first, and the ones that only ask for a look come last.
"""

from __future__ import annotations

from . import (assertion_weakened, conftest_changed, hardcoded_return, known_exploit,
               mock_in_test, swallowed_exception, test_file_deleted, test_skipped)

MODULES = [
    test_skipped,
    test_file_deleted,
    assertion_weakened,
    hardcoded_return,
    swallowed_exception,
    known_exploit,
    mock_in_test,
    conftest_changed,
]

RULES = [module.RULE for module in MODULES]

BY_ID = {rule.id: rule for rule in RULES}
BY_CODE = {rule.code: rule for rule in RULES}


def run_all(ctx) -> list:
    signals = []
    for module in MODULES:
        try:
            signals.extend(module.check(ctx))
        except OSError:
            continue
    return dedupe(signals)


def dedupe(signals) -> list:
    seen, out = set(), []
    for signal in signals:
        key = (signal.rule_id, signal.path, signal.line, signal.explanation)
        if key not in seen:
            seen.add(key)
            out.append(signal)
    return out


__all__ = ["MODULES", "RULES", "BY_ID", "BY_CODE", "run_all", "dedupe"]
