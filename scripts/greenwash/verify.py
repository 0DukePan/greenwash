"""Behavioral verification: run the tests instead of only reading the diff.

This is the part that turns a smell into a signal.

Two modes:

  auto=True     Discover the test command, run the suite on the current tree
                and on the committed baseline (a detached worktree of HEAD),
                and flag any test that passed at baseline and fails now.
                Zero configuration -- no held-out suite required.

  explicit      `run_tests` executes a given command; `heldout` runs a suite
                the agent was never shown. Visible passes + held-out fails is
                the strongest evidence that a change overfits what it saw.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from . import discover
from .report import Flag


def _run(cmd, cwd=None) -> int:
    if isinstance(cmd, str):
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd).returncode
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd).returncode


def _failing_tests(cmd, cwd):
    """(returncode, {failing test ids} | None). Adds junitxml when pytest."""
    if isinstance(cmd, str) and "pytest" in cmd:
        fd, report = tempfile.mkstemp(suffix=".xml")
        os.close(fd)
        try:
            code = _run(f'{cmd} --junitxml="{report}"', cwd)
            ids = set()
            for case in ET.parse(report).iter("testcase"):
                if case.find("failure") is not None or case.find("error") is not None:
                    ids.add(f"{case.get('classname', '')}::{case.get('name', '')}")
            return code, ids
        except (ET.ParseError, OSError, ValueError):
            return _run(cmd, cwd), None
        finally:
            try:
                os.remove(report)
            except OSError:
                pass
    return _run(cmd, cwd), None


def _baseline_worktree():
    tmp = tempfile.mkdtemp(prefix="greenwash-base-")
    os.rmdir(tmp)  # git worktree add wants to create the directory itself
    subprocess.run(["git", "worktree", "prune"], capture_output=True, text=True)
    result = subprocess.run(["git", "worktree", "add", "--detach", tmp, "HEAD"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    return tmp


def _drop_worktree(tmp):
    subprocess.run(["git", "worktree", "remove", "--force", tmp],
                   capture_output=True, text=True)
    shutil.rmtree(tmp, ignore_errors=True)


def _verify_auto(run_tests):
    verification: dict = {}
    flags: list = []

    cmd = run_tests or discover.discover_test_command(".")
    if not cmd:
        verification["auto"] = False
        return verification, flags
    verification["test_command"] = cmd

    current_code, current_fail = _failing_tests(cmd, ".")
    verification["tests_passed"] = current_code == 0

    baseline = _baseline_worktree()
    if baseline:
        try:
            base_code, base_fail = _failing_tests(cmd, baseline)
            verification["baseline_passed"] = base_code == 0
            if current_fail is not None and base_fail is not None:
                newly = sorted(current_fail - base_fail)
                if newly:
                    verification["newly_failing"] = newly[:20]
                    flags.append(Flag(
                        "", "regression",
                        f"{len(newly)} test(s) passed at baseline and fail now, "
                        f"e.g. {newly[0]} -- the change broke existing coverage"))
        finally:
            _drop_worktree(baseline)

    if current_code != 0 and not any(f.kind == "regression" for f in flags):
        flags.append(Flag("", "tests-failed",
                          "the test suite exits non-zero after the agent claimed done"))

    return verification, flags


def verify(run_tests=None, heldout=None, auto=False):
    if auto:
        return _verify_auto(run_tests)

    verification: dict = {}
    flags: list = []

    if run_tests:
        verification["tests_passed"] = _run(run_tests) == 0

    if heldout:
        if os.path.isfile(heldout):
            code = _run([sys.executable, "-m", "pytest", "-q", heldout])
        else:
            code = _run(heldout)
        verification["heldout_passed"] = code == 0

    if verification.get("tests_passed") is False:
        flags.append(Flag("", "tests-failed",
                          "the test command exits non-zero after the agent claimed done"))

    if verification.get("tests_passed") and verification.get("heldout_passed") is False:
        flags.append(Flag("", "heldout-failed",
                          "the visible suite passes but the held-out suite fails -- "
                          "the change overfits what it was allowed to see"))

    return verification, flags
