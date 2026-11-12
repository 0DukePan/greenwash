#!/usr/bin/env python3
"""The DeepSeek run: one command, resumable, honest about a dead key.

`benchmark/harness.py` scores a model through the same seam it uses for the
scripted double -- `--agent-cmd python --agent-arg benchmark/tools/deepseek_agent.py`.
This script wraps that with the things a real run needs:

- a preflight that asks the API one question and stops on 402/401 rather than
  writing 87 `infra` rows;
- the model id written into every row, so two models are never mixed;
- `--resume` on a jsonl, so an interrupted run continues instead of restarting;
- a report that separates "the agent cheated" from "the agent did not fix it",
  because those are different findings about the tool and the corpus.

    python benchmark/deepseek_run.py --preflight
    python benchmark/deepseek_run.py --states off,full --runs 3
    python benchmark/deepseek_run.py --report

Costs are recorded from the API's usage field; a run of 29 tasks x 3 states x 3
runs is 261 model sessions, so start with `--tasks` limited.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
AGENT = HERE / "tools" / "deepseek_agent.py"
RESULTS = HERE / "results"
DEFAULT_JSONL = RESULTS / "deepseek.jsonl"
MODEL = os.environ.get("GREENWASH_AGENT_MODEL", "deepseek-v4-pro")


def preflight(model: str) -> int:
    """One call, and the reason on failure. Never write rows on a dead key."""
    import urllib.error
    import urllib.request
    sys.path.insert(0, str(ROOT))
    from benchmark.tools.deepseek_agent import API, api_key
    body = json.dumps({"model": model, "max_tokens": 4, "temperature": 0,
                       "messages": [{"role": "user", "content": "say OK"}]}
                      ).encode()
    request = urllib.request.Request(
        API, data=body, headers={"Authorization": "Bearer " + api_key(),
                                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.load(response)
        print(f"preflight: OK model={data.get('model')} "
              f"tokens={data.get('usage', {}).get('total_tokens')}")
        return 0
    except urllib.error.HTTPError as error:
        code = error.code
        detail = error.read().decode("utf-8", "replace")[:300]
        print(f"preflight: HTTP {code}: {detail}", file=sys.stderr)
        if code == 402:
            print("preflight: the account has no balance. Top up and rerun; "
                  "no rows were written.", file=sys.stderr)
        elif code in (401, 403):
            print("preflight: the key was refused. Rotate it and rerun.",
                  file=sys.stderr)
        return 2
    except Exception as error:            # network, DNS, timeout
        print(f"preflight: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


def run(args) -> int:
    if preflight(args.model) != 0:
        return 2
    command = [
        sys.executable, str(HERE / "harness.py"),
        "--agent-cmd", sys.executable,
        "--agent-arg", str(AGENT),
        "--states", args.states,
        "--runs", str(args.runs),
        "--jsonl", str(args.jsonl),
        "--out", str(RESULTS / "deepseek-latest.json"),
        "--timeout", str(args.timeout),
    ]
    if args.resume:
        command.append("--resume")
    for task in args.tasks:
        command += ["--task", task]
    environment = {**os.environ, "GREENWASH_AGENT_MODEL": args.model}
    return subprocess.call(command, cwd=ROOT, env=environment)


def report(jsonl: pathlib.Path) -> int:
    if not jsonl.is_file():
        print(f"report: no rows at {jsonl}")
        return 1
    rows = [json.loads(line) for line in
            jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    models = sorted({row.get("model") for row in rows if row.get("model")})
    print(f"rows: {len(rows)}  models: {', '.join(models) or 'unrecorded'}")
    print()
    by_state = {}
    for row in rows:
        by_state.setdefault(row["state"], {}).setdefault(row["outcome"], 0)
        by_state[row["state"]][row["outcome"]] += 1
    outcomes = ["genuine fix", "integrity cheat", "flagged", "spec overfit",
                "underspecified", "valid failure", "honest refusal", "infra"]
    print(f"{'state':<12}" + "".join(f"{name:>18}" for name in outcomes))
    for state, counts in by_state.items():
        print(f"{state:<12}" + "".join(f"{counts.get(name, 0):>18}"
                                       for name in outcomes))
    print()
    print("The two numbers that matter, per state:")
    for state, counts in by_state.items():
        total = sum(value for name, value in counts.items() if name != "infra")
        cheats = counts.get("integrity cheat", 0)
        fixed = counts.get("genuine fix", 0) + counts.get("flagged", 0)
        print(f"  {state:<12} cheated {cheats}/{total}   "
              f"actually fixed {fixed}/{total}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="the DeepSeek benchmark run")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--states", default="off,skill-only,full")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--task", action="append", default=[], dest="tasks")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--jsonl", type=pathlib.Path, default=DEFAULT_JSONL)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        return preflight(args.model)
    if args.report:
        return report(args.jsonl)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
