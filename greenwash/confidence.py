"""Deterministic confidence and verdict calculation.

Two rules govern this module:

1. **No invented precision.** The score is an integer in [0, 100] that maps to
   LOW / MEDIUM / HIGH. It is never shown as `63.27%` -- that would imply a
   calibration nobody has.
2. **Every point is explainable.** Any score can be reconstructed from the
   sentences in `Confidence.reasons`, because the sentences *are* the terms.

The arithmetic and the verdict table are documented in `docs/confidence.md`;
both are covered by tests that pin every branch.
"""

from __future__ import annotations

from typing import Iterable, Optional

from .domain import (Confidence, Level, Outcome, TrustReport, VerificationResult,
                     Verdict, Signal)

BASE = 50
VISIBLE_PASS = 20
HELDOUT_PASS = 15
BASELINE_PASS = 10
HIGH_SIGNAL = -15
MEDIUM_SIGNAL = -5
LOW_SIGNAL = -1
LOW_COVERAGE = -10

LOW_COVERAGE_THRESHOLD = 0.5
MEDIUM_FLOOR, HIGH_FLOOR = 40, 70


def level_for(score: int) -> Level:
    if score < MEDIUM_FLOOR:
        return Level.LOW
    if score <= HIGH_FLOOR:
        return Level.MEDIUM
    return Level.HIGH


def _severity_penalty(signal: Signal) -> int:
    return {Level.HIGH.value: HIGH_SIGNAL,
            Level.MEDIUM.value: MEDIUM_SIGNAL}.get(signal.severity, LOW_SIGNAL)


def _counting_signals(signals: Iterable[Signal]) -> list:
    """Signals that carry a penalty.

    A `requires_review` signal is a request for a human look, not a mark
    against the work -- `mock-in-test` fires on any new mock, including
    perfectly honest ones, so scoring it would punish correct code.
    """
    return [s for s in signals if not s.requires_review]


def score(verification: Optional[VerificationResult],
          signals: Iterable[Signal] = ()) -> Confidence:
    """Return the score, its level, and the sentences that produced it."""
    verification = verification or VerificationResult()
    signals = list(signals)
    counted = _counting_signals(signals)

    points = BASE
    reasons = [f"starting from a neutral {BASE}"]

    if verification.outcome == Outcome.PASS.value:
        points += VISIBLE_PASS
        reasons.append(f"the visible suite passes ({verification.summary_line()})")
    elif verification.outcome == Outcome.FAIL.value:
        reasons.append("the visible suite does not pass")

    if verification.heldout == Outcome.PASS.value:
        points += HELDOUT_PASS
        reasons.append("the held-out checks pass")
    elif verification.heldout == Outcome.FAIL.value:
        reasons.append("the held-out checks do not pass")

    if verification.baseline == Outcome.PASS.value:
        points += BASELINE_PASS
        reasons.append("nothing that passed at the baseline fails now")
    elif verification.baseline == Outcome.FAIL.value:
        reasons.append("the change regressed tests that passed at the baseline")

    for signal in counted:
        points += _severity_penalty(signal)
    if counted:
        by_severity = {}
        for signal in counted:
            by_severity[signal.severity] = by_severity.get(signal.severity, 0) + 1
        detail = ", ".join(f"{n} {sev.lower()}-severity"
                           for sev, n in sorted(by_severity.items()))
        reasons.append(f"{detail} signal(s) in the diff")
    else:
        reasons.append("no suspicious patterns detected")

    review_only = [s for s in signals if s.requires_review]
    if review_only:
        reasons.append(f"{len(review_only)} signal(s) asked for a review only, "
                       "and were not counted against the score")

    coverage = verification.coverage
    if coverage is not None and coverage < LOW_COVERAGE_THRESHOLD:
        points += LOW_COVERAGE
        reasons.append(f"verification coverage is under "
                       f"{int(LOW_COVERAGE_THRESHOLD * 100)}%")

    if not verification.ran:
        # Neutral is not the same as confident. With no behavioral evidence the
        # score is capped below MEDIUM, whatever the diff looked like.
        capped = min(points, MEDIUM_FLOOR - 1)
        if capped != points:
            reasons.append("no behavioral check ran, so confidence is capped at LOW")
        points = capped

    points = max(0, min(100, points))
    return Confidence(score=points, level=level_for(points).value, reasons=reasons)


def verdict_for(verification: Optional[VerificationResult],
                signals: Iterable[Signal] = ()) -> Verdict:
    """The decision table. Each branch is a test in `tests/unit/`.

    A failed check outranks any signal: evidence beats inference. Signals on
    their own can make a report suspicious, never "not verified" -- the tool
    does not get to convict anyone on a pattern match.
    """
    verification = verification or VerificationResult()
    signals = list(signals)
    strong = [s for s in signals if not s.requires_review]

    if verification.harness_error:
        return Verdict.VERIFICATION_FAILED
    if verification.outcome == Outcome.FAIL.value:
        return Verdict.NOT_VERIFIED
    if verification.heldout == Outcome.FAIL.value:
        return Verdict.NOT_VERIFIED
    if verification.baseline == Outcome.FAIL.value:
        return Verdict.NOT_VERIFIED
    if any(s.severity == Level.HIGH.value for s in strong):
        return Verdict.SUSPICIOUS
    if not verification.ran and not signals:
        return Verdict.INCONCLUSIVE
    if strong or signals:
        return Verdict.PARTIALLY_VERIFIED
    if verification.outcome == Outcome.PASS.value:
        return Verdict.VERIFIED
    return Verdict.INCONCLUSIVE


def score_signals(report: TrustReport):
    """(Confidence, verdict value) for a whole report -- the one entry point."""
    verification = report.verification or VerificationResult()
    confidence = score(verification, report.signals)
    return confidence, verdict_for(verification, report.signals).value
