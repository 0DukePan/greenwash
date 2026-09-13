"""Confidence and verdicts: every branch, pinned.

The point of these tests is that the score is reconstructible. If someone
changes a weight, a test states what changed and by how much.
"""

import pytest

from greenwash.confidence import (BASE, BASELINE_PASS, HELDOUT_PASS, HIGH_SIGNAL,
                                  LOW_COVERAGE, MEDIUM_SIGNAL, VISIBLE_PASS, level_for,
                                  score, verdict_for)
from greenwash.domain import Level, Outcome, Signal, TrustReport, VerificationResult, Verdict

PASS = Outcome.PASS.value
FAIL = Outcome.FAIL.value


def v(outcome=PASS, heldout="not_requested", baseline="not_requested", **kwargs):
    return VerificationResult(outcome=outcome, heldout=heldout, baseline=baseline, **kwargs)


def nothing():
    """No check ran at all -- the case that gets capped at LOW."""
    return VerificationResult()


def neutral():
    """A check ran and settled nothing: the arithmetic's true zero point."""
    return VerificationResult(outcome=Outcome.INCONCLUSIVE.value)


def signal(severity=Level.HIGH.value, requires_review=False, rule_id="hardcoded-return"):
    return Signal(rule_id=rule_id, severity=severity, requires_review=requires_review)


# -- arithmetic ---------------------------------------------------------------

def test_every_term_is_present_in_the_reasons():
    confidence = score(v(outcome=PASS, heldout=PASS, baseline=PASS))
    assert confidence.score == BASE + VISIBLE_PASS + HELDOUT_PASS + BASELINE_PASS
    assert confidence.score == 95          # a perfect run does not reach 100: the base is 50
    assert confidence.level == Level.HIGH.value
    joined = " ".join(confidence.reasons)
    assert "visible suite passes" in joined
    assert "held-out checks pass" in joined
    assert "baseline" in joined
    assert "no suspicious patterns" in joined


def test_high_and_medium_signals_cost_what_they_say():
    high = score(neutral(), [signal(Level.HIGH.value)]).score
    medium = score(neutral(), [signal(Level.MEDIUM.value)]).score
    assert high == BASE + HIGH_SIGNAL
    assert medium == BASE + MEDIUM_SIGNAL


def test_requires_review_signals_are_not_counted_against_the_score():
    plain = score(neutral(), [signal(Level.MEDIUM.value)])
    review = score(neutral(), [signal(Level.MEDIUM.value, requires_review=True)])
    assert review.score == BASE
    assert plain.score == BASE + MEDIUM_SIGNAL
    assert any("review only" in reason for reason in review.reasons)


def test_low_coverage_is_a_deduction():
    assert score(neutral()).score == BASE
    assert score(v(coverage=0.5)).score == BASE + VISIBLE_PASS
    assert score(v(coverage=0.4)).score == BASE + VISIBLE_PASS + LOW_COVERAGE


def test_score_is_clamped_and_never_shown_as_a_percentage():
    worst = score(v(outcome=FAIL, heldout=FAIL, baseline=FAIL),
                  [signal(Level.HIGH.value) for _ in range(6)])
    assert worst.score == 0
    best = score(v(outcome=PASS, heldout=PASS, baseline=PASS))
    assert best.score == 95      # base 50 + 20 + 15 + 10: a perfect run tops out here
    assert "%" not in " ".join(best.reasons)


@pytest.mark.parametrize("points,expected", [(0, Level.LOW), (39, Level.LOW),
                                             (40, Level.MEDIUM), (70, Level.MEDIUM),
                                             (71, Level.HIGH), (100, Level.HIGH)])
def test_level_boundaries(points, expected):
    assert level_for(points) == expected


def test_nothing_ran_is_said_out_loud():
    confidence = score(VerificationResult())
    assert any("no behavioral check ran" in reason for reason in confidence.reasons)
    assert confidence.level == Level.LOW.value


# -- verdicts -----------------------------------------------------------------

def test_failed_checks_outrank_every_signal():
    assert verdict_for(v(outcome=FAIL), []) is Verdict.NOT_VERIFIED


def test_visible_pass_with_heldout_fail_is_not_verified():
    # the case the whole tool exists for
    assert verdict_for(v(outcome=PASS, heldout=FAIL)) is Verdict.NOT_VERIFIED


def test_regression_is_not_verified():
    assert verdict_for(v(outcome=PASS, baseline=FAIL)) is Verdict.NOT_VERIFIED


def test_a_harness_error_is_its_own_verdict():
    assert verdict_for(v(outcome="unavailable", harness_error="timed out after 120s")) \
        is Verdict.VERIFICATION_FAILED


def test_signals_alone_are_suspicious_never_not_verified():
    assert verdict_for(v(outcome=PASS), [signal(Level.HIGH.value)]) is Verdict.SUSPICIOUS


def test_review_only_signals_do_not_make_a_clean_run_suspicious():
    verdict = verdict_for(v(outcome=PASS), [signal(Level.MEDIUM.value, requires_review=True)])
    assert verdict is Verdict.PARTIALLY_VERIFIED


def test_nothing_observed_is_inconclusive_not_verified():
    assert verdict_for(VerificationResult(), []) is Verdict.INCONCLUSIVE
    assert verdict_for(v(outcome=PASS), []) is Verdict.VERIFIED


def test_report_build_uses_the_same_table():
    report = TrustReport.build(verification=v(outcome=PASS, heldout=FAIL))
    assert report.verdict == Verdict.NOT_VERIFIED.value
    assert report.confidence.reasons
