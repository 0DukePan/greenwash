"""Held-out checks: a suite the agent never saw.

This is the strongest evidence the tool can produce. Visible tests passing
while a held-out suite fails is the signature of a change that fits the tests
it was shown, and it is the one signal that cannot be explained away by a
reader who trusts the agent.

The spec is deliberately loose: a path (run with pytest) or any command.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from ..domain import Evidence, Outcome
from . import results


@dataclass
class HeldoutOutcome:
    outcome: str = Outcome.NOT_REQUESTED.value
    detail: dict = field(default_factory=dict)
    evidence: list = field(default_factory=list)
    command: str = ""


def _as_command(spec) -> str:
    """A held-out spec is a path or a whole command; tell them apart carefully.

    `endswith(".py")` alone is not enough: a command like
    `python -m pytest -q tests/test_calc_hidden.py` ends in `.py` too, and
    wrapping that in another pytest invocation is how you get "file or
    directory not found: python -m pytest ...".
    """
    if isinstance(spec, (list, tuple)):
        return " ".join(str(part) for part in spec)
    spec = str(spec)
    looks_like_a_path = " " not in spec.strip() and (os.path.isfile(spec) or spec.endswith(".py"))
    if looks_like_a_path:
        return f'"{sys.executable}" -m pytest -q "{spec}"'
    return spec


def run_heldout(spec, cwd=None, timeout: int = 120, label: str = "") -> HeldoutOutcome:
    if not spec:
        return HeldoutOutcome(Outcome.NOT_REQUESTED.value)

    command = _as_command(spec)
    result, outcome = results.execute(command, cwd=cwd, timeout=timeout)
    held = HeldoutOutcome(command=command,
                          detail={"passed": outcome.passed, "failed": outcome.failed,
                                  "cases": outcome.total, "source": label or str(spec),
                                  "counts_available": outcome.counts_available})
    if result.timed_out:
        held.outcome = Outcome.UNAVAILABLE.value
        held.detail["reason"] = result.error
        return held

    failed = outcome.failed if outcome.counts_available else None
    if failed is None:
        held.outcome = Outcome.PASS.value if outcome.ok else Outcome.FAIL.value
        held.detail["reason"] = "judged by exit status; the runner reported no per-case counts"
    else:
        held.outcome = Outcome.FAIL.value if failed else Outcome.PASS.value

    if held.outcome == Outcome.FAIL.value:
        cases = ", ".join(outcome.failing_ids[:6]) or "unnamed case"
        held.evidence.append(Evidence(
            summary=f"held-out suite failed: {cases}",
            expected="the held-out cases pass on a correct implementation",
            observed=(outcome.first_failure or
                      f"{failed} of {outcome.total or '?'} held-out case(s) failed"),
            source=f"held-out verification ({label or str(spec)})",
            command=command,          # the configured command, not the temp junit wrapper
            case_id=outcome.failing_ids[0] if outcome.failing_ids else "",
        ))
    return held
