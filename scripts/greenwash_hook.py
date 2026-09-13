#!/usr/bin/env python3
"""greenwash Stop hook.

Claude Code calls this every time the agent tries to end its turn. It produces
a trust report for whatever changed since HEAD and prints it.

Two modes, and the default is the one the project promises:

  report (default)   exit 0. The report is printed for the transcript; the
                     agent's stop is allowed. Nothing blocks, ever.
  enforce (opt-in)   exit 2 + the report on stderr, which blocks the stop and
                     hands the agent the findings. Enabled with
                     `"mode": "enforce"` in .greenwash/config.json, or
                     GREENWASH_ENFORCE=1.

Plain exit-code signalling is deliberate: the exit-2 + stderr contract is
stable regardless of which JSON schema a given Claude Code version expects for
Stop. Same for exit 0 -- an informational report must not depend on a field
name in a payload we do not control.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(HERE)


def _report_command(root: str, claim: str) -> list:
    """The new CLI, called with the plugin's package importable."""
    command = [sys.executable, "-m", "greenwash", "--json", "--no-color"]
    if os.environ.get("GREENWASH_AUTO") == "1" or os.environ.get("GREENWASH_TEST_CMD"):
        command.append("--auto")
    if os.environ.get("GREENWASH_TEST_CMD"):
        command += ["--run-tests", os.environ["GREENWASH_TEST_CMD"]]
    if os.environ.get("GREENWASH_HELDOUT"):
        command += ["--heldout", os.environ["GREENWASH_HELDOUT"]]
    if claim:
        command += ["--claim", claim]
    if os.environ.get("GREENWASH_ENFORCE") == "1":
        command.append("--enforce")
    return command


def _describe(report: dict) -> str:
    """A message an agent can act on, built from the report."""
    signals = report.get("signals") or []
    verification = report.get("verification") or {}
    confidence = report.get("confidence") or {}
    lines = [f"greenwash: {report.get('verdict', 'INCONCLUSIVE')} "
             f"({str(confidence.get('level', '')).lower()} confidence)"]

    ran = verification.get("outcome")
    if ran and ran != "not_requested":
        passed, total = verification.get("tests_passed"), verification.get("tests_run")
        counts = f"{passed}/{total}" if total else ran
        lines.append(f"  visible tests: {counts}")
    if verification.get("heldout") and verification["heldout"] != "not_requested":
        lines.append(f"  held-out checks: {verification['heldout']}")
    if verification.get("baseline") == "fail":
        lines.append(f"  regression: {len(verification.get('newly_failing') or [])} "
                     "test(s) passed at the baseline and fail now")

    if signals:
        lines.append("")
        lines.append("Suspicious patterns to explain:")
        for signal in signals[:8]:
            where = f" {signal.get('files', [''])[0]}" if signal.get("files") else ""
            lines.append(f"  [{signal.get('rule_id', '?')}]{where} {signal.get('explanation', '')}")
    for item in (verification.get("evidence") or [])[:3]:
        lines.append("")
        if item.get("expected"):
            lines.append(f"  Expected: {item['expected']}")
        if item.get("observed"):
            lines.append(f"  Observed: {item['observed']}")
        if item.get("source"):
            lines.append(f"  Source:   {item['source']}")

    lines.append("")
    lines.append("If a pattern is not actually a problem (an intentionally skipped "
                 "unrelated test, a legitimate constant), say so explicitly and why. "
                 "Otherwise fix it before calling this done.")
    return "\n".join(lines)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # Set true when a previous Stop hook already forced a retry this turn:
    # never block twice, and never loop on a flag the agent cannot resolve.
    if payload.get("stop_hook_active"):
        sys.exit(0)

    claim = ""
    for key in ("claim", "summary", "task"):
        if isinstance(payload.get(key), str):
            claim = payload[key][:400]
            break

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [PLUGIN_ROOT, *([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])])
    try:
        result = subprocess.run(_report_command(PLUGIN_ROOT, claim), capture_output=True,
                                text=True, env=env, timeout=240)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"greenwash: could not run ({exc})", file=sys.stderr)
        sys.exit(0)          # a broken checker must never block a developer

    try:
        report = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        if result.returncode == 3:
            print("greenwash: could not produce a report (not a git repository?)",
                  file=sys.stderr)
        sys.exit(0)

    message = _describe(report)
    enforcing = os.environ.get("GREENWASH_ENFORCE") == "1" or report.get("run", {}).get(
        "mode") == "enforce"

    if enforcing:
        print(message, file=sys.stderr)
        sys.exit(2)
    print(message)
    sys.exit(0)


if __name__ == "__main__":
    main()
