"""Behavioral verification: run the tests instead of only reading the diff.

This is the layer that turns a smell into a signal, and the one that keeps the
tool honest -- it reports what happened, including "nothing ran".

Order of business:
  1. find the test command (explicit, or discovered when `auto`)
  2. run it on the current tree
  3. run it again on a detached worktree of HEAD and compare
  4. optionally run a held-out suite the agent never saw

Every failure becomes `Evidence` with expected/observed/source, because a
report that says "FAILED" and nothing else is not worth reading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..domain import Evidence, Outcome, VerificationResult
from . import baseline as baseline_mod
from . import discovery, heldout as heldout_mod, results, signals

DEFAULT_TIMEOUT = 120


@dataclass
class Verification:
    """What the CLI and hook consume."""

    result: VerificationResult = field(default_factory=VerificationResult)
    signals: list = field(default_factory=list)


def verify(run_tests=None, heldout=None, auto: bool = False, timeout: int = DEFAULT_TIMEOUT,
           cwd=None, compare_baseline: Optional[bool] = None,
           changed_paths=None) -> Verification:
    result = VerificationResult()
    raised: list = []

    detection = discovery.detect(cwd or ".")
    if run_tests:
        command = run_tests
        result.notes.append(f"using the test command you supplied: {command}")
    elif auto:
        command = detection.command
        if command:
            result.notes.append(f"detected {detection.kind} from {detection.source}")
        else:
            result.notes.append("no test command could be detected; "
                                "the behavioral layer did not run")
    else:
        command = None

    if compare_baseline is None:
        compare_baseline = bool(auto and command)

    result.test_command = command
    current = results.TestOutcome()

    if command:
        run_result, current = results.execute(command, cwd=cwd, timeout=timeout)
        result.duration_s = run_result.duration_s
        result.truncated = list(run_result.truncated)
        result.redactions += run_result.redactions
        result.tests_run = current.total
        result.tests_passed = current.passed
        result.tests_failed = current.failed

        if run_result.timed_out:
            result.outcome = Outcome.UNAVAILABLE.value
            result.harness_error = run_result.error
            raised.append(signals.HARNESS.signal(
                "", None, f"the test command {run_result.error}", command=run_result.command))
        elif run_result.error:
            result.outcome = Outcome.UNAVAILABLE.value
            result.harness_error = run_result.error
            raised.append(signals.HARNESS.signal(
                "", None, run_result.error, command=run_result.command))
        else:
            result.outcome = Outcome.PASS.value if current.ok else Outcome.FAIL.value
            if not current.counts_available:
                result.notes.append("the test runner reported no per-case counts; "
                                    "this result is based on the exit status")
            if (result.outcome == Outcome.FAIL.value and run_result.returncode == 2
                    and "pytest" in run_result.command
                    and "-m pytest" not in run_result.command):
                # exit 2 from pytest means collection failed, and the most common
                # cause is invoking the console script, which does not put the
                # working directory on sys.path.
                result.notes.append("pytest exited 2, which usually means a collection "
                                    "error -- if your tests import from the project root, "
                                    "try `python -m pytest` instead of `pytest`")
            if result.outcome == Outcome.FAIL.value:
                failed_ids = ", ".join(current.failing_ids[:5])
                raised.append(signals.TESTS_FAILED.signal(
                    "", None,
                    "the suite exits non-zero after the agent claimed done"
                    + (f" ({failed_ids})" if failed_ids else ""),
                    command=run_result.command))
                result.evidence.append(Evidence(
                    summary="the visible suite does not pass",
                    expected="the test command exits 0",
                    observed=(f"exit code {run_result.returncode}"
                              + (f"; {current.failed} failing" if current.failed is not None else "")),
                    source="visible test run",
                    command=run_result.command,
                    case_id=current.failing_ids[0] if current.failing_ids else "",
                ))
    else:
        result.outcome = Outcome.NOT_REQUESTED.value

    if compare_baseline and command and not result.harness_error:
        comparison = baseline_mod.compare(command, current, cwd=cwd, timeout=timeout)
        result.baseline = comparison.outcome
        result.baseline_detail = comparison.detail
        result.newly_failing = comparison.newly_failing
        if comparison.outcome == Outcome.UNAVAILABLE.value:
            result.notes.append("baseline verification: NOT AVAILABLE -- "
                                + comparison.detail.get("reason", "no comparison was made"))
        elif comparison.outcome == Outcome.FAIL.value:
            result.regressions = comparison.newly_failing or ["(unnamed tests)"]
            example = comparison.newly_failing[0] if comparison.newly_failing else ""
            raised.append(signals.REGRESSION.signal(
                "", None,
                f"{len(result.regressions)} test(s) passed at the baseline and fail now"
                + (f", e.g. {example}" if example else ""),
                baseline=comparison.detail))
            result.evidence.append(Evidence(
                summary="tests that passed at HEAD now fail",
                expected="a test that passes at HEAD keeps passing",
                observed=f"{len(result.regressions)} newly failing",
                source="baseline comparison against a detached worktree of HEAD",
                command=command,
                case_id=example,
            ))

    held = heldout_mod.run_heldout(heldout, cwd=cwd, timeout=timeout)
    result.heldout = held.outcome
    result.heldout_detail = held.detail
    result.evidence.extend(held.evidence)
    if held.outcome == Outcome.FAIL.value and result.outcome == Outcome.PASS.value:
        raised.append(signals.HELDOUT_FAILED.signal(
            "", None,
            "the visible suite passes but the held-out suite fails -- the change "
            "overfits what it was allowed to see",
            command=held.command or ""))
    elif held.outcome == Outcome.UNAVAILABLE.value:
        result.notes.append("held-out checks: NOT AVAILABLE -- "
                            + held.detail.get("reason", "no held-out suite ran"))

    if changed_paths:
        result.coverage = discovery.changed_file_coverage(changed_paths, cwd or ".")
        if result.coverage is not None:
            result.notes.append(
                f"coverage is a proxy: {int(result.coverage * 100)}% of the changed "
                "source files have an associated test file (not line coverage)")

    return Verification(result=result, signals=raised)


__all__ = ["verify", "Verification", "discovery", "results", "baseline_mod", "heldout_mod"]
