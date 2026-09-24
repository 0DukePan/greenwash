"""Derived held-out checks: the committed version of a test, against the code as it stands.

The strongest evidence greenwash can produce is a suite the agent never saw, and
almost nobody has one configured. The repository's own history supplies the next
best thing: the committed version of every test file the agent edited is a suite
the agent *did* see -- and then changed.

Neither existing check can see that. `baseline` runs HEAD's tests against HEAD's
code; the agent's own run uses the agent's tests against the agent's code. A test
loosened to fit the code passes in both. Running HEAD's tests against the agent's
code is the missing combination, and it is the signature of a weakened test: the
committed version fails while the edited version passes.

The worktree is a checkout of HEAD, so its copies of the test files are already
the committed ones. Only the changed *implementation* files are overlaid onto it,
which is what makes the comparison mean anything.

An unavailable comparison says so. A collection error -- a refactor that renamed
the import target -- is not evidence that a test was weakened, and is never
reported as one.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field

from ..domain import Evidence, Outcome
from ..scan.languages.packs import is_test_file
from . import results, signals

DEFAULT_LIMIT = 3


def test_side(path: str) -> bool:
    """Whether a path belongs to the test harness rather than the implementation.

    `conftest.py` at a repository root is not matched by the test-file pattern,
    and it is exactly the file an agent patches to make a suite pass without
    fixing anything -- so it is held at HEAD along with the tests.
    """
    return is_test_file(path) or os.path.basename(path) == "conftest.py"


@dataclass
class IntegrityOutcome:
    outcome: str = Outcome.NOT_REQUESTED.value
    detail: dict = field(default_factory=dict)
    evidence: list = field(default_factory=list)
    signals: list = field(default_factory=list)


def _overlay(worktree: str, changes, root: str) -> list:
    """Place the changed implementation files into the worktree.

    Returns the paths it could not place, so the caller can say the comparison
    ran against a tree it could not fully build rather than quietly reporting on
    one that is not what it claims to be.
    """
    failed = []
    for change in changes:
        target = os.path.join(worktree, change.path)
        if change.kind == "deleted":
            try:
                os.remove(target)
            except OSError:
                pass
            continue
        origin = os.path.join(root, change.path) if root else change.path
        try:
            parent = os.path.dirname(target)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(origin, target)
        except OSError:
            failed.append(change.path)
    return failed


FILE_EXTENSIONS = (".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".java", ".go", ".rs")


def _stem(path: str) -> str:
    """`tests/test_calc.py` -> `test_calc`."""
    return os.path.splitext(os.path.basename(path))[0]


def _path_for(case_id: str, test_paths=()) -> str:
    """The file a `path::case` id belongs to, when it can be known precisely.

    pytest's JUnit report gives `classname` as a dotted module path -- never a
    file path -- and `splitext` reads the `.test_calc` in `tests.test_calc` as an
    extension, so the two shapes are told apart by hand. A path is printed only
    when it can be resolved exactly: the id carries one, or its module name
    matches exactly one of the test files this diff changed. A report must never
    name a location it cannot actually point at.
    """
    if "::" not in case_id:
        return ""
    head = case_id.split("::", 1)[0]
    if "/" in head or "\\" in head or head.endswith(FILE_EXTENSIONS):
        return head

    segments = set(head.split("."))
    matches = [path for path in test_paths if _stem(path) in segments]
    return matches[0] if len(matches) == 1 else ""


def _failed(detail: dict, weakened: list, command: str, limit: int) -> IntegrityOutcome:
    outcome = IntegrityOutcome(Outcome.FAIL.value, dict(detail))
    outcome.detail["weakened"] = weakened[:limit]

    test_paths = detail.get("test_files") or []
    for case in weakened[:limit]:
        path = _path_for(case, test_paths)
        where = f"the committed version of {path}" if path else "a committed test"
        outcome.signals.append(signals.TEST_WEAKENED.signal(
            path, None,
            f"{where} does not pass against the current implementation"
            + (f" ({case})" if case else ""),
            command=command,
            case_id=case))

    if not weakened:
        outcome.signals.append(signals.TEST_WEAKENED.signal(
            "", None,
            "the committed suite fails where the edited suite passes "
            "(per-case detail unavailable)",
            command=command))

    first = weakened[0] if weakened else ""
    outcome.evidence.append(Evidence(
        summary="the committed test does not pass against the current code",
        expected="a test file that was changed still passes in its committed form",
        observed=(f"{len(weakened)} case(s) fail in the committed version and pass in the "
                  f"edited one" + (f", e.g. {first}" if first else "")
                  if weakened else
                  "the committed suite exits non-zero where the edited suite exits zero"),
        source="derived held-out verification (committed tests, current code)",
        command=command,
        case_id=first,
    ))
    return outcome


def check(command, current: results.TestOutcome, changes, worktree, cwd=None,
          timeout: int = 120, limit: int = DEFAULT_LIMIT) -> IntegrityOutcome:
    """Run the committed tests against the implementation as it now stands.

    `current` is the agent's own run. Only the cases the committed test fails
    *and* the edited test passes are the signature of a weakened test; anything
    failing in both is already reported as `tests-failed` or `regression`.
    """
    changes = list(changes or [])
    test_changes = [c for c in changes if test_side(c.path)]
    source_changes = [c for c in changes if not test_side(c.path)]

    if not test_changes:
        return IntegrityOutcome(Outcome.NOT_REQUESTED.value,
                                {"reason": "no test file changed in this diff"})
    if not command:
        return IntegrityOutcome(Outcome.NOT_REQUESTED.value,
                                {"reason": "no test command to re-run"})
    if not worktree:
        return IntegrityOutcome(Outcome.UNAVAILABLE.value,
                                {"reason": "could not create a detached worktree at HEAD"})

    root = cwd or "."
    overlay_failed = _overlay(worktree, source_changes, root)
    run_result, committed = results.execute(command, cwd=worktree, timeout=timeout)

    detail = {
        "test_files": [c.path for c in test_changes],
        "committed_counts": {"passed": committed.passed, "failed": committed.failed},
        "current_counts": {"passed": current.passed, "failed": current.failed},
    }
    if overlay_failed:
        detail["overlay_failed"] = overlay_failed

    if run_result.timed_out:
        return IntegrityOutcome(Outcome.UNAVAILABLE.value,
                                {**detail, "reason": run_result.error})
    if (startup := results.runner_never_started(run_result, committed)):
        return IntegrityOutcome(Outcome.UNAVAILABLE.value, {**detail, "reason": startup})

    if not committed.counts_available:
        # Exit status alone still separates "weakened" from "broken either way".
        detail["reason"] = ("compared by exit status only; the runner reported no "
                            "per-case counts")
        if not committed.ok and current.ok:
            return _failed(detail, [], command, limit)
        return IntegrityOutcome(
            Outcome.PASS.value if committed.ok else Outcome.UNAVAILABLE.value, detail)

    weakened = sorted(set(committed.failing_ids) - set(current.failing_ids))
    if weakened:
        return _failed(detail, weakened, command, limit)
    return IntegrityOutcome(Outcome.PASS.value, detail)


__all__ = ["check", "test_side", "IntegrityOutcome", "DEFAULT_LIMIT"]
