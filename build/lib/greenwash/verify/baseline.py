"""Baseline comparison: did this change break something that used to pass?

A detached worktree of HEAD is the honest baseline -- it is the committed
state, not "whatever the agent left behind". If it cannot be created, the
result is `unavailable`, which the report says out loud. A comparison that did
not happen is never reported as a pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import gitutil
from ..domain import Outcome
from . import results


@dataclass
class BaselineComparison:
    outcome: str = Outcome.NOT_REQUESTED.value
    detail: dict = field(default_factory=dict)
    newly_failing: list = field(default_factory=list)
    fixed: list = field(default_factory=list)


def compare(command, current: results.TestOutcome, cwd=None, timeout: int = 120) -> BaselineComparison:
    if not command:
        return BaselineComparison(Outcome.NOT_REQUESTED.value,
                                  {"reason": "no test command to compare with"})

    worktree = gitutil.baseline_worktree(cwd)
    if not worktree:
        return BaselineComparison(Outcome.UNAVAILABLE.value, {
            "reason": "could not create a detached worktree at HEAD",
            "baseline_itself_passed": None,
        })

    try:
        _, baseline = results.execute(command, cwd=worktree, timeout=timeout)
    finally:
        gitutil.drop_worktree(worktree, cwd)

    comparison = BaselineComparison()
    comparison.detail = {
        "baseline_itself_passed": baseline.ok,
        "baseline_counts": {"passed": baseline.passed, "failed": baseline.failed},
        "current_counts": {"passed": current.passed, "failed": current.failed},
    }

    if not baseline.counts_available or not current.counts_available:
        # Exit codes alone still tell us whether the suite was green before
        # and is not now -- that is a regression, just not a named one.
        if baseline.ok and not current.ok:
            comparison.outcome = Outcome.FAIL.value
            comparison.detail["reason"] = (
                "the suite passed at the baseline and fails now (per-test detail unavailable)")
        else:
            comparison.outcome = Outcome.PASS.value if baseline.ok else Outcome.UNAVAILABLE.value
            comparison.detail["reason"] = "compared by exit status only"
        return comparison

    before, after = set(baseline.failing_ids), set(current.failing_ids)
    comparison.newly_failing = sorted(after - before)
    comparison.fixed = sorted(before - after)
    comparison.outcome = Outcome.FAIL.value if comparison.newly_failing else Outcome.PASS.value
    return comparison
