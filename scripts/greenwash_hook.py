#!/usr/bin/env python3
"""greenwash Stop hook.

Claude Code calls this every time the agent tries to end its turn. It runs
`greenwash_check.py scan` against everything changed since HEAD and, if the
diff looks like a silently faked pass, blocks the stop and hands the report
back to the agent.

If GREENWASH_AUTO=1, it runs the zero-config behavioral layer too: discover the
project's tests and diff the result against the committed baseline. Or set
GREENWASH_TEST_CMD and/or GREENWASH_HELDOUT to be explicit.

Claude Code's contract (https://code.claude.com/docs/en/hooks):
  exit 0          -> allow the stop
  exit 2 + stderr -> block the stop; stderr is shown to the agent

Plain exit-code signaling is used deliberately: the exit-2 + stderr contract
is stable regardless of which JSON schema a given Claude Code version expects
for Stop.
"""

import json
import os
import subprocess
import sys


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # Set true if a previous Stop hook already forced a retry this turn. Don't
    # block a second time -- avoid an infinite loop when the agent can't or
    # won't resolve the flag (Claude Code also caps consecutive blocks at 8).
    if payload.get("stop_hook_active"):
        sys.exit(0)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cli = os.path.join(script_dir, "greenwash_check.py")

    cmd = [sys.executable, cli, "scan", "--json"]
    test_cmd = os.environ.get("GREENWASH_TEST_CMD")
    heldout = os.environ.get("GREENWASH_HELDOUT")
    auto = os.environ.get("GREENWASH_AUTO") == "1"

    if heldout:
        cmd = [sys.executable, cli, "all", "--json"]
        if test_cmd:
            cmd += ["--run-tests", test_cmd]
        cmd += ["--heldout", heldout]
    elif auto:
        cmd = [sys.executable, cli, "all", "--json", "--auto"]
        if test_cmd:
            cmd += ["--run-tests", test_cmd]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        sys.exit(0)

    try:
        report = json.loads(result.stdout)
        flags = report.get("flags", [])
        verification = report.get("verification") or {}
        lines = [
            f"greenwash: {len(flags)} flag(s) in what changed this turn -- "
            f"resolve or explain these before saying it's done:",
        ]
        if verification:
            summary = ", ".join(f"{k}={'pass' if ok else 'fail'}" for k, ok in verification.items())
            lines.insert(0, f"greenwash: verification -- {summary}")
        for flag in flags:
            where = f" {flag['file']}:" if flag.get("file") else ""
            lines.append(f"  [{flag['kind']}]{where} {flag['detail']}")
        lines.append(
            "If any of these are not actually cheats (e.g. an intentionally "
            "skipped unrelated test), say so explicitly and why, rather than "
            "silently proceeding."
        )
        message = "\n".join(lines)
    except (json.JSONDecodeError, KeyError, AttributeError):
        message = result.stdout.strip() or "greenwash: check failed to parse its own output."

    print(message, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
