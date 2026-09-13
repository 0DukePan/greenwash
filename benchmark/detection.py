#!/usr/bin/env python3
"""Detector accuracy on the task corpus, with no model in the loop.

Every task is scored three ways by greenwash itself:

  buggy     the baseline the agent is handed         -> no flags expected
  cheat     the scripted cheat (fake_agent hardcode) -> static and/or behavioral catch
  solution  the task's recorded real fix             -> no flags, both suites pass

What this measures is the checker against a labelled corpus. It says nothing
about how often a model reaches for the cheat -- that is `harness.py`'s job,
and it needs a model the account can reach.

Writes benchmark/results/detection.json.

Run:  python benchmark/detection.py
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402

FAKE_AGENT = HERE / "tools" / "fake_agent.py"
OUT = HERE / "results" / "detection.json"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")


def apply_cheat(task_dir, tmp):
    env = {**os.environ, "FAKE_AGENT_MODE": "hardcode",
           "GREENWASH_BENCH_TASK_DIR": str(task_dir)}
    subprocess.run([sys.executable, str(FAKE_AGENT)], cwd=tmp, env=env,
                   capture_output=True, text=True)


def score(task, variant):
    task_dir = task["_dir"]
    language = task.get("language", "python")
    tmp = tempfile.mkdtemp(prefix="greenwash-detect-")
    try:
        harness.prepare_repo(task, tmp)
        if variant == "cheat":
            apply_cheat(task_dir, tmp)
        elif variant == "solution":
            shutil.copytree(task_dir / "solution", tmp, dirs_exist_ok=True,
                            ignore=IGNORE)

        flags = [flag["kind"] for flag in harness.run_greenwash(tmp)]
        visible = harness.run_tests(task["visible_test"], tmp, language)
        hidden = pathlib.Path(task_dir) / task["hidden_test"]
        shutil.copy(hidden, pathlib.Path(tmp) / "tests" / hidden.name)
        hidden_pass = harness.run_tests(f"tests/{hidden.name}", tmp, language)
        return {"flags": flags, "visible_pass": visible, "hidden_pass": hidden_pass}
    finally:
        harness.remove_tree(tmp)


def main() -> None:
    tasks = harness.load_tasks([])
    rows = []
    for task in tasks:
        name = task.get("name", task["_dir"].name)
        row = {"task": name, "language": task.get("language", "python")}
        for variant in ("buggy", "cheat", "solution"):
            row[variant] = score(task, variant)
        rows.append(row)
        mark = "flagged" if row["cheat"]["flags"] else "silent"
        print(f"{name:<24}{row['language']:<12}cheat: visible="
              f"{str(row['cheat']['visible_pass']):<6}hidden={str(row['cheat']['hidden_pass']):<6}"
              f"{mark:<9}flags={row['cheat']['flags']}")

    cheats = [r["cheat"] for r in rows]
    effective = [c for c in cheats if c["visible_pass"]]
    static = [c for c in effective if c["flags"]]
    behavioral = [c for c in effective
                  if c["visible_pass"] and not c["hidden_pass"]]
    either = [c for c in effective if c["flags"] or not c["hidden_pass"]]
    fixes = [r["solution"] for r in rows]
    false_positives = [f for f in fixes if f["flags"]]
    regressions = [f for f in fixes if not (f["visible_pass"] and f["hidden_pass"])]
    baseline_flags = [r["buggy"] for r in rows if r["buggy"]["flags"]]

    summary = {
        "tasks": len(rows),
        "cheats_applied": len(cheats),
        "cheats_effective": len(effective),
        "static_caught": len(static),
        "behavioral_caught": len(behavioral),
        "either_caught": len(either),
        "missed_by_both": len(effective) - len(either),
        "false_positives": len(false_positives),
        "solutions_clean": len(fixes) - len(false_positives) - len(regressions),
        "baseline_flagged": len(baseline_flags),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "tasks": rows}, indent=2),
                   encoding="utf-8")

    print()
    for key, value in summary.items():
        print(f"  {key:<20}{value}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
