"""Turning a test run into counts we can quote.

pytest gets a JUnit report because `47 passed` is a claim we can only make if
something told us the number; when a runner gives us nothing parseable we
record `counts_available: False` instead of guessing from the exit code.
"""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from .runner import RunResult, run

SUMMARY_RE = re.compile(r"(\d+)\s+(passed|failed|error|errors|skipped)", re.I)

# "the runner never started", which is not the same as "the tests failed".
# Checked only when a run produced no per-case counts, so a failing test whose
# message happens to contain "not found" cannot be mistaken for a missing
# runner -- pytest reports counts whenever it actually ran.
RUNNER_MISSING = [
    re.compile(r"No module named\s+'?([\w.]+)'?", re.I),
    re.compile(r"([\w./\\-]+): (?:command )?not found", re.I),
    re.compile(r"'?([\w./\\-]+)'? is not recognized as an internal or external command", re.I),
    re.compile(r"can't open file\s+'?([^'\n]+)'?", re.I),
    re.compile(r"no such file or directory", re.I),
]


def runner_never_started(result: RunResult, outcome: "TestOutcome") -> str:
    """A message if the command itself could not run, else ''.

    Without this, `python -m pytest` where pytest is not installed exits 1 with
    "No module named pytest", which looks exactly like a failing suite -- and
    the report would blame the work for the environment.
    """
    if outcome.counts_available:
        return ""
    if result.returncode in (127, 9009):        # POSIX shell / cmd.exe
        return f"the command could not be found (exit {result.returncode})"
    text = "\n".join(part for part in (result.stderr, result.stdout) if part)
    for pattern in RUNNER_MISSING:
        match = pattern.search(text)
        if match:
            return f"the command could not start: {match.group(0).strip()}"
    return ""


@dataclass
class TestOutcome:
    returncode: int | None = None
    total: int | None = None
    passed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    failing_ids: list = field(default_factory=list)
    first_failure: str = ""
    counts_available: bool = False
    source: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _from_junit(path: str) -> TestOutcome:
    outcome = TestOutcome(source="junit xml")
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError, ValueError):
        return outcome
    total = passed = failed = skipped = 0
    for case in tree.iter("testcase"):
        total += 1
        bad = case.find("failure")
        error = case.find("error")
        if bad is not None or error is not None:
            failed += 1
            node = bad if bad is not None else error
            if len(outcome.failing_ids) < 50:
                name = f"{case.get('classname', '')}::{case.get('name', '')}".strip(":")
                outcome.failing_ids.append(name)
                if not outcome.first_failure:
                    message = (node.get("message") or node.text or "").strip()
                    outcome.first_failure = " ".join(message.split())[:400]
        elif case.find("skipped") is not None:
            skipped += 1
        else:
            passed += 1
    outcome.total, outcome.passed = total, passed
    outcome.failed, outcome.skipped = failed, skipped
    outcome.counts_available = total > 0
    return outcome


def _from_output(text: str) -> TestOutcome:
    counts = {name.lower(): int(number) for number, name in SUMMARY_RE.findall(text)}
    outcome = TestOutcome(source="summary line")
    if not counts:
        return outcome
    outcome.passed = counts.get("passed")
    outcome.failed = counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
    outcome.skipped = counts.get("skipped")
    if outcome.passed is not None:
        outcome.total = (outcome.passed or 0) + (outcome.failed or 0) + (outcome.skipped or 0)
        outcome.counts_available = True
    return outcome


def parse(result: RunResult, junit_path: str | None = None) -> TestOutcome:
    outcome = TestOutcome(returncode=result.returncode)
    if junit_path:
        outcome = _from_junit(junit_path)
        outcome.returncode = result.returncode
    if not outcome.counts_available:
        fallback = _from_output(result.stdout + "\n" + result.stderr)
        fallback.returncode = result.returncode
        outcome = fallback
    if result.timed_out:
        outcome.first_failure = outcome.first_failure or result.error
    elif result.returncode not in (0, None) and not outcome.first_failure:
        outcome.first_failure = " ".join(result.tail(300).split())
    return outcome


def execute(command, cwd=None, timeout: int = 120, junit: bool = True) -> tuple:
    """Run a test command, with a JUnit report when the runner supports one."""
    wants_junit = (isinstance(command, str) and junit and "pytest" in command
                   and "--junitxml" not in command)
    if wants_junit or (isinstance(command, list) and junit
                       and any("pytest" in str(part) for part in command)):
        handle, path = tempfile.mkstemp(suffix=".xml")
        os.close(handle)
        try:
            if isinstance(command, list):
                result = run([*command, "--junitxml", path], cwd=cwd, timeout=timeout)
            else:
                result = run(f'{command} --junitxml="{path}"', cwd=cwd, timeout=timeout)
            return result, parse(result, path)
        finally:
            with contextlib.suppress(OSError):
                os.remove(path)
    result = run(command, cwd=cwd, timeout=timeout)
    return result, parse(result)
