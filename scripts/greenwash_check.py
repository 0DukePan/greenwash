#!/usr/bin/env python3
"""greenwash -- catch "done" / "tests pass" claims that aren't backed by a real check.

Two layers:
  scan    static: flag a diff that looks like a faked pass (regex + Python AST)
  verify  dynamic: run the project's tests, and optionally a suite the agent
          was never shown

Usage:
  greenwash_check.py [scan] [--staged | --base REF] [--json]
  greenwash_check.py verify [--auto | --run-tests CMD] [--heldout PATH|CMD] [--json]
  greenwash_check.py all    [scan opts] [verify opts] [--json]

Exit codes:
  0   clean
  1   one or more flags raised
  2   tool error (not a git repo, git missing, ...)
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from greenwash import scan as scan_mod
from greenwash import verify as verify_mod
from greenwash.report import render_json, render_text


def _json_arg(p):
    p.add_argument("--json", action="store_true", help="machine-readable output")


def _scan_opts(p):
    p.add_argument("--staged", action="store_true", help="check staged changes only")
    p.add_argument("--base", default=None, help="diff against this ref instead of HEAD")


def _verify_opts(p):
    p.add_argument("--run-tests", default=None,
                   help="command that runs the project's tests")
    p.add_argument("--heldout", default=None,
                   help="path to (or command running) a suite the agent never saw")
    p.add_argument("--auto", action="store_true",
                   help="zero-config: discover the test command and diff the "
                        "suite against the committed baseline")


def main() -> None:
    argv = list(sys.argv[1:])
    if not (argv and argv[0] in ("-h", "--help")) and (not argv or argv[0].startswith("-")):
        argv = ["scan", *argv]

    parser = argparse.ArgumentParser(
        prog="greenwash",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    p_scan = sub.add_parser("scan", help="static diff scan")
    _json_arg(p_scan)
    _scan_opts(p_scan)

    p_verify = sub.add_parser("verify", help="run tests / held-out suite")
    _json_arg(p_verify)
    _verify_opts(p_verify)

    p_all = sub.add_parser("all", help="scan + verify")
    _json_arg(p_all)
    _scan_opts(p_all)
    _verify_opts(p_all)

    args = parser.parse_args(argv)

    flags: list = []
    verification = None
    if args.cmd in ("scan", "all"):
        flags += scan_mod.scan(staged=getattr(args, "staged", False),
                               base=getattr(args, "base", None))
    if args.cmd in ("verify", "all"):
        verification, vflags = verify_mod.verify(
            args.run_tests, args.heldout, auto=getattr(args, "auto", False))
        flags += vflags

    print(render_json(flags, verification) if args.json else render_text(flags, verification))
    sys.exit(1 if flags else 0)


if __name__ == "__main__":
    main()
