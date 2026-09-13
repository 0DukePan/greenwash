#!/usr/bin/env python3
"""greenwash -- the compatibility entry point.

This is the path every existing integration calls: the GitHub Action, the
pre-commit hook, the CI job, the benchmark harness's fake agent, the demo, and
the Stop hook. Its command line, its stdout and its exit codes are a contract,
so they stay exactly as they were:

  greenwash_check.py [scan] [--staged | --base REF] [--json]
  greenwash_check.py verify [--auto | --run-tests CMD] [--heldout PATH|CMD] [--json]
  greenwash_check.py all    [scan opts] [verify opts] [--json]

Exit codes:
  0   clean
  1   one or more flags raised
  2   tool error (not a git repo, git missing, ...)

For the trust report -- verdicts, confidence, evidence, JSON schema v1 -- use
the `greenwash` command instead. This one speaks the old dialect so that a
pinned Action does not break when the report layer changes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from greenwash import gitutil  # noqa: E402
from greenwash.domain import Outcome  # noqa: E402
from greenwash.scan import scan_diff  # noqa: E402
from greenwash.verify import verify as run_verification  # noqa: E402


@dataclass
class Flag:
    file: str
    kind: str
    detail: str


def _flags(signals) -> list:
    return [Flag(signal.path, signal.rule_id, signal.explanation) for signal in signals]


def _verification_dict(result) -> dict:
    """The old `{name: bool}` summary, rebuilt from the new result."""
    out: dict = {}
    if result.outcome in (Outcome.PASS.value, Outcome.FAIL.value):
        out["tests_passed"] = result.outcome == Outcome.PASS.value
    if result.baseline in (Outcome.PASS.value, Outcome.FAIL.value):
        out["baseline_passed"] = result.baseline == Outcome.PASS.value
    if result.heldout in (Outcome.PASS.value, Outcome.FAIL.value):
        out["heldout_passed"] = result.heldout == Outcome.PASS.value
    return out


def render_json(flags, verification=None) -> str:
    out = {"clean": not flags, "flags": [asdict(flag) for flag in flags]}
    if verification is not None:
        out["verification"] = verification
    return json.dumps(out, indent=2)


def render_text(flags, verification=None) -> str:
    lines = []
    if verification is not None:
        summary = ", ".join(f"{name}={'pass' if ok else 'fail'}"
                            for name, ok in verification.items())
        if summary:
            lines.append(f"greenwash: verification -- {summary}")
    if not flags:
        lines.append("greenwash: clean -- nothing here fakes a passing suite.")
        return "\n".join(lines)
    lines.append(f"greenwash: {len(flags)} flag(s) -- explain these before calling it done.")
    lines.append("")
    for flag in flags:
        lines.append(f"  [{flag.kind}] {flag.file}")
        lines.append(f"      {flag.detail}")
    return "\n".join(lines)


def do_scan(args) -> tuple:
    try:
        diff = gitutil.diff(staged=args.staged, base=args.base)
    except gitutil.GitError as exc:
        sys.exit(f"greenwash: {exc}")
    return _flags(scan_diff(diff))


def do_verify(args) -> tuple:
    outcome = run_verification(run_tests=args.run_tests, heldout=args.heldout, auto=args.auto)
    return _verification_dict(outcome.result), _flags(outcome.signals)


def main() -> None:
    argv = list(sys.argv[1:])
    if not (argv and argv[0] in ("-h", "--help")) and (not argv or argv[0].startswith("-")):
        argv = ["scan", *argv]

    parser = argparse.ArgumentParser(
        prog="greenwash_check.py",
        description="Static + behavioral checks on what an agent claimed to have done.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")

    def common(target):
        target.add_argument("--json", action="store_true", help="machine-readable output")

    def scan_opts(target):
        target.add_argument("--staged", action="store_true", help="check staged changes only")
        target.add_argument("--base", default=None, help="diff against this ref")

    def verify_opts(target):
        target.add_argument("--run-tests", default=None, help="command that runs the project's tests")
        target.add_argument("--heldout", default=None,
                            help="path to (or command running) a suite the agent never saw")
        target.add_argument("--auto", action="store_true",
                            help="discover the test command and diff against the committed baseline")

    for name in ("scan", "verify", "all"):
        target = sub.add_parser(name)
        common(target)
        if name in ("scan", "all"):
            scan_opts(target)
        if name in ("verify", "all"):
            verify_opts(target)

    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not hasattr(args, "staged"):
        args.staged, args.base = False, None
    if not hasattr(args, "run_tests"):
        args.run_tests, args.heldout, args.auto = None, None, False

    flags: list = []
    verification = None
    if args.cmd in ("scan", "all"):
        flags += do_scan(args)
    if args.cmd in ("verify", "all"):
        verification, verify_flags = do_verify(args)
        flags += verify_flags

    print(render_json(flags, verification) if args.json else render_text(flags, verification))
    sys.exit(1 if flags else 0)


if __name__ == "__main__":
    main()
