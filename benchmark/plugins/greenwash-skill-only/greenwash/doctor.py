"""First-run activation and `greenwash doctor`.

`initialize` does the smallest useful thing: detect what it can, write a config
that records the detection, and say what it found -- including what it could
not find. It never fails; a repo with no tests still gets a report, it just
gets a report that says no behavioral check ran.

`doctor` is the same information, arranged for someone debugging.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from . import config as config_mod
from . import gitutil
from .verify import discovery

PASS, WARN, FAIL = "pass", "warn", "fail"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    hint: str = ""

    def line(self, marks: dict) -> str:
        mark = {PASS: marks["pass"], WARN: marks["warn"], FAIL: marks["fail"]}[self.status]
        text = f"  {mark} {self.name}"
        if self.detail:
            text += f" -- {self.detail}"
        if self.hint:
            text += f"\n      {self.hint}"
        return text


@dataclass
class Activation:
    checks: list
    config_path: str = ""
    wrote_config: bool = False

    @property
    def ok(self) -> bool:
        return all(check.status != FAIL for check in self.checks)

    def report(self, marks: dict) -> str:
        return "\n".join(check.line(marks) for check in self.checks)


def environment_checks(root=".", env=None) -> list:
    env = os.environ if env is None else env
    root_path = Path(root)
    checks = []

    checks.append(Check("git", PASS if shutil.which("git") else FAIL,
                        "found on PATH" if shutil.which("git") else "not found",
                        "" if shutil.which("git") else "install git; nothing works without it"))

    is_repo = gitutil.is_repo(root)
    checks.append(Check("git repository", PASS if is_repo else FAIL,
                        gitutil.repo_root(root) or "not a repository",
                        "" if is_repo else "run this inside a git repository"))

    detection = discovery.detect(root)
    checks.append(Check(
        "test command",
        PASS if detection.found else WARN,
        f"{detection.command}  ({detection.source})" if detection.found
        else "none detected",
        "" if detection.found else
        "set one with `--run-tests`, GREENWASH_TEST_CMD, or .greenwash/config.json"))

    heldout = (env or os.environ).get("GREENWASH_HELDOUT")
    checks.append(Check("held-out suite", PASS if heldout else WARN,
                        heldout or "not configured",
                        "" if heldout else
                        "optional, but it is the only check the agent cannot see"))

    agent = "claude-code" if (env or os.environ).get("CLAUDECODE") else ""
    checks.append(Check("agent environment", PASS if agent else WARN,
                        agent or "not detected",
                        "" if agent else "the Stop hook only fires inside Claude Code"))

    config = config_mod.load(root, env)
    checks.append(Check("configuration", PASS if config_mod.initialized(root) else WARN,
                        config.source,
                        f"ignoring: {'; '.join(config.problems)}" if config.problems else ""))

    checks.append(Check("mode", PASS, f"{config.mode} -- "
                        + ("the agent's stop is blocked on the verdicts in block_on"
                           if config.enforcing else "reports only, never blocks")))

    writable = os.access(root_path, os.W_OK)
    checks.append(Check("writable working tree", PASS if writable else FAIL,
                        str(root_path.resolve()),
                        "" if writable else "greenwash cannot write .greenwash/ here"))

    checks.append(Check("python", PASS, f"{sys.version.split()[0]} at {sys.executable}"))
    return checks


def initialize(root=".", env=None) -> Activation:
    """Detect, record, and report -- the `greenwash init` path."""
    env = os.environ if env is None else env
    checks = environment_checks(root, env)
    detection = discovery.detect(root)

    values = {}
    if detection.found:
        values["test_command"] = detection.command
    if env.get("GREENWASH_HELDOUT"):
        values["heldout"] = env["GREENWASH_HELDOUT"]

    path = config_mod.save(values, root) if values or not config_mod.initialized(root) else \
        str(config_mod.config_path(root))
    return Activation(checks=checks, config_path=path, wrote_config=True)


def doctor(root=".", env=None) -> Activation:
    return Activation(checks=environment_checks(root, env),
                      config_path=str(config_mod.config_path(root)),
                      wrote_config=False)
