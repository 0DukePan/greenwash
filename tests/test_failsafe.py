"""Infrastructure failures must never read as a passing verdict.

The decision table outranks every other consideration with one rule: a check
that did not run cannot produce a pass. These tests pin one case each for the
ways an agent run can fail outside the code under review: timeout, missing
dependency, unparseable output, an empty diff, missing original tests, and an
internal failure. Each must yield INCONCLUSIVE or an explicit error, never
VERIFIED and never the evidence verdict CLEAN.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash.confidence import verdict_for  # noqa: E402
from greenwash.domain import Outcome, Verdict, VerificationResult  # noqa: E402

PASSING = (Verdict.VERIFIED, Verdict.CLEAN)


def test_a_timed_out_test_command_is_an_explicit_error():
    result = VerificationResult(
        outcome=Outcome.UNAVAILABLE.value,
        harness_error="tests timed out after 120s")
    verdict = verdict_for(result, [])
    assert verdict is Verdict.VERIFICATION_FAILED
    assert verdict not in PASSING


def test_a_missing_dependency_is_an_explicit_error():
    result = VerificationResult(
        outcome=Outcome.UNAVAILABLE.value,
        harness_error="pytest is not installed on this machine")
    verdict = verdict_for(result, [])
    assert verdict is Verdict.VERIFICATION_FAILED
    assert verdict not in PASSING


def test_unparseable_test_output_is_inconclusive():
    result = VerificationResult(outcome=Outcome.UNAVAILABLE.value)
    verdict = verdict_for(result, [])
    assert verdict is Verdict.INCONCLUSIVE
    assert verdict not in PASSING


def test_an_empty_diff_is_inconclusive():
    verdict = verdict_for(VerificationResult(), [])
    assert verdict is Verdict.INCONCLUSIVE
    assert verdict not in PASSING


def test_missing_original_tests_never_read_as_verified():
    """The suite passed, but its committed form could not be re-run."""
    result = VerificationResult(
        outcome=Outcome.PASS.value,
        integrity=Outcome.UNAVAILABLE.value,
        integrity_detail={"reason": "could not create a detached baseline worktree"})
    verdict = verdict_for(result, [])
    assert verdict is not Verdict.VERIFIED
    assert verdict not in PASSING


def test_an_internal_failure_is_an_explicit_error():
    result = VerificationResult(
        outcome=Outcome.UNAVAILABLE.value,
        harness_error="internal error while collecting results")
    verdict = verdict_for(result, [])
    assert verdict is Verdict.VERIFICATION_FAILED
    assert verdict not in PASSING


def test_an_honest_passing_run_still_passes_the_control():
    """The fail-safe rules above must not turn ordinary green runs grey."""
    result = VerificationResult(outcome=Outcome.PASS.value,
                                integrity=Outcome.NOT_REQUESTED.value)
    assert verdict_for(result, []) is Verdict.VERIFIED
