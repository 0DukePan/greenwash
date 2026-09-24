"""The rules the behavioral layer raises.

Same `Rule` shape as the static rules, different source of truth: these come
from having actually run something, which is why they outrank a pattern match
in the verdict table.
"""

from __future__ import annotations

from ..scan.rules.base import DIVERGENCE, Rule

TESTS_FAILED = Rule(
    id="tests-failed",
    code="GW-VER-001",
    title="Test suite does not pass",
    category=DIVERGENCE,
    severity="HIGH",
    confidence="HIGH",
    description="The test command the claim depends on exits non-zero.",
    remediation="Make the suite pass, or say which failures are expected.",
)

HELDOUT_FAILED = Rule(
    id="heldout-failed",
    code="GW-VER-002",
    title="Held-out checks fail",
    category=DIVERGENCE,
    severity="HIGH",
    confidence="HIGH",
    description="The visible suite passes but a suite the agent never saw does not.",
    remediation="Fix the behaviour the held-out case exercises -- the visible "
                "tests are not the whole specification.",
)

REGRESSION = Rule(
    id="regression",
    code="GW-VER-003",
    title="Regression against baseline",
    category=DIVERGENCE,
    severity="HIGH",
    confidence="HIGH",
    description="Tests that passed at the committed baseline fail now.",
    remediation="Fix the regression, or explain why those tests no longer apply.",
)

TEST_WEAKENED = Rule(
    id="test-weakened",
    code="GW-VER-005",
    title="Changed test does not pass against the new code",
    category=DIVERGENCE,
    severity="HIGH",
    confidence="HIGH",
    description="A test file was changed, and its committed version does not pass "
                "against the implementation as it now stands.",
    remediation="Either the test was made to fit the code, or the specification "
                "genuinely changed. Say which, and why.",
)

REQUIREMENT_FAILED = Rule(
    id="requirement-failed",
    code="GW-VER-006",
    title="A stated requirement does not hold",
    category=DIVERGENCE,
    severity="HIGH",
    confidence="HIGH",
    description="A requirement the claim named -- bound to a test or a command -- "
                "does not pass.",
    remediation="Fix it, or withdraw the requirement: one that no longer applies "
                "should be taken back, not left failing.",
)

HARNESS = Rule(
    id="verification-failed",
    code="GW-VER-004",
    title="Verification could not complete",
    category=DIVERGENCE,
    severity="LOW",
    confidence="HIGH",
    description="The verifier could not run the checks it was asked to run.",
    remediation="Re-run with a working test command, or use --run-tests.",
    requires_review=True,
)

__all__ = ["TESTS_FAILED", "HELDOUT_FAILED", "REGRESSION", "TEST_WEAKENED",
           "REQUIREMENT_FAILED", "HARNESS"]
