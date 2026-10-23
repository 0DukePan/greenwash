"""Behavioral verification: run the tests instead of only reading the diff.

This is the layer that turns a smell into a signal, and the one that keeps the
tool honest -- it reports what happened, including "nothing ran".

Order of business:
  1. find the test command (explicit, or discovered when `auto`)
  2. run it on the current tree
  3. run it again on a detached worktree of the baseline and compare
  4. optionally run a held-out suite the agent never saw

Every failure becomes `Evidence` with expected/observed/source, because a
report that says "FAILED" and nothing else is not worth reading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .. import gitutil
from ..domain import Evidence, Outcome, VerificationResult
from . import baseline as baseline_mod
from . import discovery, heldout as heldout_mod, integrity as integrity_mod
from . import pinned as pinned_mod
from . import requirements as requirements_mod
from . import results, signals
from .results import runner_never_started

DEFAULT_TIMEOUT = 120


@dataclass
class Verification:
    """What the CLI and hook consume."""

    result: VerificationResult = field(default_factory=VerificationResult)
    signals: list = field(default_factory=list)
    requirements: list = field(default_factory=list)


def verify(run_tests=None, heldout=None, auto: bool = False, timeout: int = DEFAULT_TIMEOUT,
           cwd=None, compare_baseline: Optional[bool] = None,
           changed_paths=None, changes=None, integrity: bool = True,
           integrity_max: int = integrity_mod.DEFAULT_LIMIT,
           base_ref: Optional[str] = None,
           policy: str = "conservative",
           requirements=None) -> Verification:
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
        elif (startup := runner_never_started(run_result, current)):
            # An unrun check is not a failed one. Say "could not verify", and say
            # what to do about it, rather than reporting a failure the work did
            # not cause.
            result.outcome = Outcome.UNAVAILABLE.value
            result.harness_error = startup
            result.notes.append("install the test runner, or pass --run-tests with a "
                                "command this environment can execute")
            raised.append(signals.HARNESS.signal("", None, startup,
                                                 command=run_result.command))
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

    # One worktree serves both the baseline comparison and the integrity check:
    # `git worktree add` is a full checkout of HEAD, so doing it twice is doing
    # the same work twice. The baseline runs first, against the pristine tree;
    # the integrity check then overlays the changed implementation files onto it.
    test_changes = [c for c in (changes or []) if integrity_mod.test_side(c.path)]
    wants_baseline = bool(compare_baseline and command and not result.harness_error)
    wants_integrity = bool(integrity and command and test_changes and not result.harness_error)
    if wants_baseline or wants_integrity:
        # The baseline is the session base when one is in play: a cheat
        # committed mid-session must not become its own "before" picture.
        worktree = (gitutil.baseline_worktree(cwd, ref=base_ref) if base_ref
                    else gitutil.baseline_worktree(cwd))
    else:
        worktree = None

    try:
        if wants_baseline:
            comparison = baseline_mod.compare(command, current, cwd=cwd, timeout=timeout,
                                              worktree=worktree)
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
                    summary="tests that passed at the baseline now fail",
                    expected="a test that passes at the baseline keeps passing",
                    observed=f"{len(result.newly_failing)} newly failing",
                    source="baseline comparison against a detached worktree of the base",
                    command=command,
                    case_id=example,
                ))

        if wants_integrity:
            check = integrity_mod.check(command, current, changes, worktree, cwd=cwd,
                                        timeout=timeout, limit=integrity_max)
            result.integrity = check.outcome
            result.integrity_detail = check.detail
            result.evidence.extend(check.evidence)
            raised.extend(check.signals)
            if check.detail.get("overlay_failed"):
                result.notes.append(
                    "test integrity: the working-tree version of "
                    + ", ".join(check.detail["overlay_failed"])
                    + " could not be placed in the baseline worktree, so the comparison "
                      "used the committed version of those files as well")
            if check.outcome == Outcome.UNAVAILABLE.value:
                result.notes.append("test integrity: NOT AVAILABLE -- "
                                    + check.detail.get("reason", "no comparison was made"))
        elif not result.harness_error:
            result.integrity_detail = {
                "reason": "no test file changed in this diff" if not test_changes
                          else "test integrity is turned off"}
    finally:
        if worktree:
            gitutil.drop_worktree(worktree, cwd)

    if changes:
        # A changed expected value is judged only by evidence pinned before
        # the agent ran; the integrity outcome says whether the pinned
        # original assertion fails on the agent's code.
        try:
            diff_text = (gitutil.session_diff(base_ref, cwd=cwd) if base_ref
                         else gitutil.diff(cwd=cwd))
        except gitutil.GitError:
            diff_text = ""
        decisions = pinned_mod.evaluate(
            cwd or ".", base_ref, diff_text, {c.path for c in changes},
            original_fails=result.integrity == Outcome.FAIL.value,
            infra=result.integrity not in (Outcome.PASS.value, Outcome.FAIL.value),
            policy=policy)
        if decisions:
            result.pinned = [decision.as_dict() for decision in decisions]
            result.pinned_verdict = pinned_mod.verdict_under(decisions, policy)

    if command and current.counts_available and not result.harness_error:
        # Nothing ran is not a pass, and running less than the baseline is its
        # own finding: a suite quietly narrowed by skips or deselection exits 0
        # and used to count as green. A scaffold that executes nothing at the
        # baseline either is empty, which is inconclusive, not cheating.
        executed = (current.passed or 0) + (current.failed or 0)
        base_counts = (result.baseline_detail or {}).get("baseline_counts") or {}
        base_executed = (base_counts.get("passed") or 0) + (base_counts.get("failed") or 0)
        base_known = result.baseline in (Outcome.PASS.value, Outcome.FAIL.value)
        if executed == 0:
            # The phenomenon is "nothing ran", not "the suite failed": the
            # exit-code verdict and its signal are superseded, and keeping both
            # would contradict the reclassification below.
            raised = [s for s in raised if s.rule_id != "tests-failed"]
            result.evidence = [e for e in result.evidence
                               if getattr(e, "summary", "") != "the visible suite does not pass"]
            if base_known and base_executed == 0:
                result.outcome = Outcome.INCONCLUSIVE.value
                result.notes.append("the suite executes nothing at the baseline either: "
                                    "nothing ran here, and there is no before to compare with")
            else:
                result.outcome = Outcome.FAIL.value
                raised.append(signals.TESTS_NOT_RUN.signal(
                    "", None,
                    f"nothing executed: {current.total} test(s) collected, "
                    f"{current.skipped or 0} skipped, 0 run",
                    command=command))
                result.evidence.append(Evidence(
                    summary="no test actually ran",
                    expected="the suite executes the tests it collected",
                    observed=f"0 of {current.total} executed ({current.skipped or 0} skipped)",
                    source="visible test run",
                    command=command))
        elif base_known and (current.skipped or 0) > (base_counts.get("skipped") or 0):
            added = (current.skipped or 0) - (base_counts.get("skipped") or 0)
            raised.append(signals.TESTS_NOT_RUN.signal(
                "", None,
                f"{added} more test(s) are skipped than at the baseline",
                command=command))
        elif (base_known and current.total is not None
              and (base_counts.get("total") or 0) > (current.total or 0)):
            raised.append(signals.TESTS_NOT_RUN.signal(
                "", None,
                f"the suite runs fewer tests than at the baseline: "
                f"{current.total} collected now, {base_counts.get('total')} then",
                command=command))

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

    listed, requirement_signals = requirements_mod.run_requirements(
        requirements, test_command=command, cwd=cwd, timeout=timeout)
    raised.extend(requirement_signals)
    for requirement in listed:
        if requirement.status == Outcome.FAIL.value:
            result.evidence.append(Evidence(
                summary=f"requirement not met: {requirement.text}",
                expected=f"{requirement.text} ({requirement.target})",
                observed=f"exit code {requirement.detail.get('exit_code')}",
                source="requirement verification",
                command=requirement.detail.get("command", ""),
                case_id=(requirement.detail.get("failing") or [""])[0],
            ))

    if changed_paths:
        result.coverage = discovery.changed_file_coverage(changed_paths, cwd or ".")
        if result.coverage is not None:
            result.notes.append(
                f"coverage is a proxy: {int(result.coverage * 100)}% of the changed "
                "source files have an associated test file (not line coverage)")

    return Verification(result=result, signals=raised, requirements=listed)


__all__ = ["verify", "Verification", "discovery", "results", "baseline_mod", "heldout_mod"]
