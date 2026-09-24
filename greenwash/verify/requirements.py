"""Requirements: what a claim says it did, and the evidence bound to each part.

A claim is prose, and prose cannot be checked. A requirement can -- when it names
the thing that would prove it. `--require "Login succeeds => tests/test_auth.py::test_login"`
binds one sentence to one test id; a requirement with no binding is recorded as
unverifiable, never as a pass.

No model is involved. The agent -- or the person writing the config -- says what
the claim entails and names the evidence; greenwash runs it and reports which
parts held up. The untrusted party supplies the checklist, and the evidence stays
the arbiter, which is the only arrangement that works without a model in the loop.
"""

from __future__ import annotations

from ..domain import Outcome, Requirement
from . import results, signals

SEPARATOR = "=>"
COMMAND_PREFIX = "cmd:"
DEFAULT_LIMIT = 10


def parse(specs) -> list:
    """Turn `--require` / config strings into Requirement records.

    `text => target` binds one sentence to its evidence; `cmd:` marks the target
    as a command rather than a test id. Anything without a binding is prose.
    """
    parsed = []
    for spec in specs or []:
        text, _, target = str(spec).partition(SEPARATOR)
        text, target = text.strip(), target.strip()
        if not text:
            continue
        if not target:
            parsed.append(Requirement(text=text, kind="prose"))
        elif target.startswith(COMMAND_PREFIX):
            parsed.append(Requirement(text=text, kind="command",
                                      target=target[len(COMMAND_PREFIX):].strip()))
        else:
            parsed.append(Requirement(text=text, kind="test", target=target))
    return parsed


def _command_for(requirement: Requirement, test_command) -> str:
    """The command that would prove one requirement, or '' when there is none.

    A test id is only meaningful to a runner that takes one on the command line,
    so a project whose runner does not is told the requirement could not be run
    rather than being told it passed.
    """
    if requirement.kind == "command":
        return requirement.target
    if requirement.kind != "test" or not test_command:
        return ""
    if "pytest" not in test_command:
        return ""
    return f'{test_command} "{requirement.target}"'


def run_requirements(specs, test_command=None, cwd=None, timeout: int = 120,
                     limit: int = DEFAULT_LIMIT) -> tuple:
    """(requirements, signals) -- each requirement run against its own evidence."""
    requirements = parse(specs)
    if not requirements:
        return [], []

    raised: list = []
    started = 0
    for requirement in requirements:
        if requirement.kind == "prose":
            requirement.status = Outcome.UNAVAILABLE.value
            requirement.detail = {"reason": "no evidence was bound to this requirement"}
            continue

        command = _command_for(requirement, test_command)
        if not command:
            requirement.status = Outcome.UNAVAILABLE.value
            requirement.detail = {
                "reason": "no test command to run it with" if requirement.kind == "test"
                          else "this requirement has no command to run"}
            continue

        if started >= limit:
            requirement.status = Outcome.UNAVAILABLE.value
            requirement.detail = {"reason": f"only the first {limit} requirements are run",
                                  "command": command}
            continue
        started += 1

        run_result, outcome = results.execute(command, cwd=cwd, timeout=timeout)
        requirement.detail = {
            "command": command,
            "exit_code": run_result.returncode,
            "cases": outcome.total,
            "failing": outcome.failing_ids[:5],
        }

        if run_result.timed_out:
            requirement.status = Outcome.UNAVAILABLE.value
            requirement.detail["reason"] = run_result.error
            continue
        if (startup := results.runner_never_started(run_result, outcome)):
            requirement.status = Outcome.UNAVAILABLE.value
            requirement.detail["reason"] = startup
            continue

        requirement.status = Outcome.PASS.value if outcome.ok else Outcome.FAIL.value
        if requirement.status == Outcome.FAIL.value:
            example = outcome.failing_ids[0] if outcome.failing_ids else ""
            raised.append(signals.REQUIREMENT_FAILED.signal(
                "", None,
                f'the requirement "{requirement.text}" does not hold'
                + (f" ({example})" if example else f" ({requirement.target})"),
                command=command))
    return requirements, raised


__all__ = ["parse", "run_requirements", "SEPARATOR", "DEFAULT_LIMIT"]
