"""Requirement coverage: what a claim promised, and which promises have evidence.

A requirement is one sentence from a task specification. Binding it to a test
(or several) turns prose into a check. This module answers four questions and
refuses to answer a fifth:

  verified        every bound test passes
  failed          every bound test fails
  contradictory   some bound tests pass and some fail -- the evidence disagrees
  unverified      nothing was bound, so nothing was checked

and, separately, **missing negative cases**: a requirement bound only to tests
that assert the happy path has evidence that cannot fail. That is a property of
the evidence, not of the code, and it is reported as a proxy with the bound
tests named -- never as "the requirement is covered".

What it does not answer is whether the implementation is correct. A verdict here
means "the evidence you offered held up", which is the same promise the rest of
the tool makes. High coverage is not correctness, and this module says so in
every report it renders.
"""

from __future__ import annotations

import ast
import pathlib
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .domain import Outcome, Requirement
from .verify import results
from .verify import signals

# A binding is a test id or a `cmd:` command, the same grammar `--require` uses.
SEPARATOR = "=>"
COMMAND_PREFIX = "cmd:"

VERIFIED = "verified"
FAILED = "failed"
CONTRADICTORY = "contradictory"
UNVERIFIED = "unverified"
UNAVAILABLE = "unavailable"

#: Markers that a bound test exercises a failure path. Deliberately small and
#: conservative: a missing marker is reported as "no negative case found", not
#: as "there is no negative case".
NEGATIVE_MARKERS = (
    "pytest.raises", "assertRaises", "assertRaisesError", "toThrow",
    "expect(", ".rejects", "should_panic", "assert_raises",
    "assert not", "assertNot", "assert false", "assertFalse",
)
NEGATIVE_NAMES = re.compile(
    r"reject|invalid|denied|missing|expired|error|fails?|negative|unauthor",
    re.I)


@dataclass
class Binding:
    """One piece of evidence offered for one requirement."""

    target: str
    kind: str = "test"                  # test | command
    status: str = Outcome.NOT_REQUESTED.value
    detail: dict = field(default_factory=dict)


@dataclass
class Row:
    """One requirement and the evidence bound to it."""

    text: str
    bindings: list = field(default_factory=list)
    status: str = UNVERIFIED
    negative: str = "unknown"           # present | missing | unknown
    negative_checked: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"text": self.text, "status": self.status,
                "negative": self.negative,
                "negative_checked": self.negative_checked,
                "bindings": [{"target": b.target, "kind": b.kind,
                              "status": b.status, "detail": b.detail}
                             for b in self.bindings]}


def merge(specs: Optional[Iterable[str]]) -> list:
    """Group repeated `--require` lines that share a sentence.

    `--require "Login succeeds => tests/a.py::test_one"` and
    `--require "Login succeeds => tests/a.py::test_two"` describe one
    requirement with two pieces of evidence, which is what makes contradictory
    evidence detectable at all. The sentence is the key.
    """
    grouped: dict = {}
    order: list = []
    for spec in specs or []:
        text, _, target = str(spec).partition(SEPARATOR)
        text, target = text.strip(), target.strip()
        if not text:
            continue
        if text not in grouped:
            grouped[text] = []
            order.append(text)
        if not target:
            continue
        if target.startswith(COMMAND_PREFIX):
            grouped[text].append(Binding(
                target=target[len(COMMAND_PREFIX):].strip(), kind="command"))
        else:
            grouped[text].append(Binding(target=target, kind="test"))
    return [Row(text=text, bindings=grouped[text]) for text in order]


def classify(row: Row) -> str:
    """The requirement's status from the statuses of its bindings.

    A requirement whose evidence disagrees with itself is `contradictory`
    rather than failed: one test passing and another failing is a different
    situation from a requirement that does not hold, and the report should not
    flatten the two.

    A requirement whose evidence could not run is `unavailable`, not
    `unverified`: nothing was bound is a gap in the specification, a test that
    could not start is a gap in the check, and the two need different fixes.
    """
    if not row.bindings:
        return UNVERIFIED
    statuses = {binding.status for binding in row.bindings}
    if Outcome.FAIL.value in statuses and Outcome.PASS.value in statuses:
        return CONTRADICTORY
    if Outcome.FAIL.value in statuses:
        return FAILED
    if Outcome.PASS.value in statuses:
        return VERIFIED
    return UNAVAILABLE


def _test_source(target: str, cwd: Optional[str]) -> str:
    """The source of the test a binding names, or "" when it cannot be read."""
    path = target.split("::", 1)[0].strip()
    if not path.endswith(".py"):
        return ""
    root = pathlib.Path(cwd or ".")
    full = root / path
    try:
        return full.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _function_source(text: str, name: str) -> str:
    """The source of one function in a test module, via `ast`, or ""."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ""
    lines = text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                start = node.lineno - 1
                end = getattr(node, "end_lineno", start + 1)
                return "\n".join(lines[start:end])
    return ""


def negative_case(target: str, cwd: Optional[str]) -> str:
    """present | missing | unknown -- does this test exercise a failure path?

    A heuristic with a name on it: the test id itself, or the body of a Python
    test, is checked for a known raise/negation marker. `unknown` covers every
    binding this cannot read -- a command, another language, a file outside the
    tree -- because guessing there would be worse than saying so.
    """
    name = target.split("::", 1)[1] if "::" in target else ""
    if name and NEGATIVE_NAMES.search(name):
        return "present"
    text = _test_source(target, cwd)
    if not text:
        return "unknown"
    body = _function_source(text, name) or text
    lowered = body.lower()
    if any(marker.lower() in lowered for marker in NEGATIVE_MARKERS):
        return "present"
    return "missing"


def _command_for(binding: Binding, test_command: Optional[str]) -> str:
    if binding.kind == "command":
        return binding.target
    if not test_command or "pytest" not in test_command:
        return ""
    return f'{test_command} "{binding.target}"'


def run(specs, test_command=None, cwd=None, timeout: int = 120,
        limit: int = 20) -> list:
    """Run every binding and return one Row per requirement, in input order."""
    rows = merge(specs)
    started = 0
    for row in rows:
        for binding in row.bindings:
            command = _command_for(binding, test_command)
            if not command:
                binding.status = Outcome.UNAVAILABLE.value
                binding.detail = {
                    "reason": ("no test command to run it with"
                               if binding.kind == "test"
                               else "this requirement has no command to run")}
                continue
            if started >= limit:
                binding.status = Outcome.UNAVAILABLE.value
                binding.detail = {
                    "reason": f"only the first {limit} bindings are run",
                    "command": command}
                continue
            started += 1
            run_result, outcome = results.execute(command, cwd=cwd,
                                                  timeout=timeout)
            binding.detail = {
                "command": command,
                "exit_code": run_result.returncode,
                "cases": outcome.total,
                "failing": outcome.failing_ids[:5],
            }
            if run_result.timed_out:
                binding.status = Outcome.UNAVAILABLE.value
                binding.detail["reason"] = run_result.error
            elif (startup := results.runner_never_started(run_result, outcome)):
                binding.status = Outcome.UNAVAILABLE.value
                binding.detail["reason"] = startup
            else:
                binding.status = (Outcome.PASS.value if outcome.ok
                                  else Outcome.FAIL.value)
        row.status = classify(row)
        checked = [b.target for b in row.bindings if b.kind == "test"]
        if checked:
            marks = {negative_case(target, cwd) for target in checked}
            row.negative = ("missing" if marks == {"missing"}
                            else "present" if "present" in marks else "unknown")
            row.negative_checked = checked
    return rows


def signals_for(rows, limit: int = 10) -> list:
    """Findings for requirements that failed or contradicted themselves."""
    raised = []
    for row in rows:
        failing = [b for b in row.bindings if b.status == Outcome.FAIL.value]
        if not failing:
            continue
        example = ""
        for binding in failing:
            ids = binding.detail.get("failing") or []
            if ids:
                example = ids[0]
                break
        raised.append(signals.REQUIREMENT_FAILED.signal(
            "", None,
            f'the requirement "{row.text}" does not hold'
            + (f" ({example})" if example else f" ({failing[0].target})"),
            command=failing[0].detail.get("command", "")))
        if limit and len(raised) >= limit:
            break
    return raised


def summary(rows) -> dict:
    """Counts a caller can gate on, plus the sentence the counts cannot say."""
    counts = {VERIFIED: 0, FAILED: 0, CONTRADICTORY: 0, UNVERIFIED: 0,
              UNAVAILABLE: 0}
    missing_negative = 0
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
        if row.negative == "missing":
            missing_negative += 1
    total = len(rows)
    return {
        "total": total,
        **counts,
        "missing_negative_case": missing_negative,
        "coverage": (round(counts[VERIFIED] / total, 4) if total else None),
        "note": ("coverage counts requirements with passing evidence; it is not "
                 "a claim that the code is correct"),
    }


def to_requirements(rows) -> list:
    """Rows as `Requirement` records, so the main report can render them."""
    out = []
    for row in rows:
        requirement = Requirement(
            text=row.text,
            target="; ".join(b.target for b in row.bindings),
            kind="test" if any(b.kind == "test" for b in row.bindings) else "command",
            status=(Outcome.PASS.value if row.status == VERIFIED
                    else Outcome.FAIL.value if row.status in (FAILED, CONTRADICTORY)
                    else Outcome.UNAVAILABLE.value),
            detail={"coverage": row.status, "negative": row.negative,
                    "bindings": [b.target for b in row.bindings]},
        )
        out.append(requirement)
    return out


MARK = {VERIFIED: "+", FAILED: "x", CONTRADICTORY: "!", UNVERIFIED: "-",
        UNAVAILABLE: "?"}
LABEL = {VERIFIED: "verified", FAILED: "failed",
         CONTRADICTORY: "contradictory", UNVERIFIED: "unverified",
         UNAVAILABLE: "could not check"}


def render(rows) -> str:
    """A terminal table, plus the sentences the table cannot carry."""
    if not rows:
        return "no requirements were supplied\n"
    lines = ["REQUIREMENT COVERAGE", "-" * 20, ""]
    width = min(46, max((len(row.text) for row in rows), default=10))
    for row in rows:
        evidence = ", ".join(b.target for b in row.bindings) or "nothing bound"
        if len(evidence) > 44:
            evidence = evidence[:41] + "..."
        lines.append(f"  {MARK.get(row.status, '?')} {row.text[:width]:<{width}}  "
                     f"{LABEL.get(row.status, row.status):<13} {evidence}")
        if row.status == CONTRADICTORY:
            passing = [b.target for b in row.bindings
                       if b.status == Outcome.PASS.value]
            failing = [b.target for b in row.bindings
                       if b.status == Outcome.FAIL.value]
            lines.append(f"      the evidence disagrees: passed {', '.join(passing)}; "
                         f"failed {', '.join(failing)}")
        for binding in row.bindings:
            reason = (binding.detail or {}).get("reason")
            if binding.status == Outcome.UNAVAILABLE.value and reason:
                lines.append(f"      {binding.target}: {reason}")

    counts = summary(rows)
    lines += ["", f"  {counts['verified']} of {counts['total']} requirements have "
                  f"evidence that held up."]
    if counts["missing_negative_case"]:
        names = ", ".join(row.text[:40] for row in rows
                          if row.negative == "missing")
        lines.append(f"  {counts['missing_negative_case']} have no bound test that "
                     f"asserts a failure path: {names}")
    if counts["unverified"]:
        lines.append(f"  {counts['unverified']} have no evidence bound at all -- "
                     "that is a gap, not a pass.")
    if counts["unavailable"]:
        lines.append(f"  {counts['unavailable']} have evidence that could not run -- "
                     "that is a gap in the check, not a failure.")
    lines.append("")
    lines.append("  coverage counts requirements with passing evidence; it is not a "
                 "claim that the code is correct.")
    return "\n".join(lines) + "\n"
