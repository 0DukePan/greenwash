#!/usr/bin/env python3
"""Every offline measurement, one command, no model and no network.

    python benchmark/verify.py            # all three, about a minute
    python benchmark/verify.py --quick    # polyglot + tampering only, seconds

A stranger's first question about a tool like this is "does it work on
something I can check myself?" This runs the three measurements that need no
API key and no repository clone:

  1. the task corpus (`detection.py`)   -- a planted cheat per task, in six languages
  2. the attack/twin pairs (`tampering.py`) -- each cheat beside its legitimate lookalike
  3. the language packs (`polyglot.py`) -- a positive and a negative per language

Each is a real subprocess against real test runners; none of them needs a
model. The command exits non-zero on the first measurement that regresses, so
it can be the acceptance test for a change.

What it does not do: it does not measure whether a *model* cheats, which needs
`harness.py` and a reachable model, and it does not replace reading the limits
in `docs/what-did-not-work.md`.

Writes benchmark/results/verify.json.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = HERE / "results"
SUMMARY = RESULTS / "verify.json"


def run(name, script, args=(), timeout=1800):
    started = time.monotonic()
    proc = subprocess.run([sys.executable, str(HERE / script), *args],
                          cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    elapsed = round(time.monotonic() - started, 1)
    tail = "\n".join((proc.stdout or "").strip().splitlines()[-4:])
    status = "pass" if proc.returncode == 0 else "FAIL"
    print(f"\n=== {name}: {status} ({elapsed}s) ===")
    if tail:
        print(tail)
    if proc.returncode != 0 and proc.stderr.strip():
        print(proc.stderr.strip()[-1500:], file=sys.stderr)
    return {"name": name, "script": script, "status": status,
            "seconds": elapsed, "returncode": proc.returncode,
            "detail": tail}


def main() -> int:
    parser = argparse.ArgumentParser(description="the offline benchmarks")
    parser.add_argument("--quick", action="store_true",
                        help="skip the task corpus (the slow one)")
    parser.add_argument("--out", type=pathlib.Path, default=SUMMARY)
    args = parser.parse_args()

    print("greenwash offline verification -- no model, no network, no clone")
    print(f"python {sys.version.split()[0]} on {sys.platform}")

    measurements = []
    if not args.quick:
        # Write beside the committed artifact, not over it: `detection.json`
        # is the reference run the README quotes, and a reader's machine has a
        # different set of toolchains. Letting a local run overwrite it turns
        # a true published number into a false one on CI.
        measurements.append(run(
            "task corpus", "detection.py",
            ("--out", str(RESULTS / "detection-local.json"))))
    measurements.append(run(
        "attack/twin pairs", "tampering.py",
        ("--out", str(RESULTS / "tampering-local.json"))))
    measurements.append(run("language packs", "polyglot.py"))

    failed = [m for m in measurements if m["status"] != "pass"]
    payload = {"measurements": measurements,
               "failed": [m["name"] for m in failed]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print()
    if failed:
        print(f"FAILED: {', '.join(m['name'] for m in failed)}", file=sys.stderr)
        return 1
    print(f"all {len(measurements)} measurements pass -- wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
