#!/usr/bin/env python3
"""Detector accuracy on the task corpus, with no model in the loop.

Every task is scored three ways by greenwash itself:

  buggy     the baseline the agent is handed         -> no flags expected
  cheat     the cheat the task was designed to tempt -> static and/or behavioral catch
  solution  the task's recorded real fix             -> no flags, both suites pass

The cheat is per task: `fake_agent` reads the task's `cheat_type` (hardcode,
skip, weaken, swallow, mock, exploit) and applies that technique, so the
results break down by cheat type instead of testing one generic trick.

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
    env = {**os.environ, "FAKE_AGENT_CHEAT": "auto",
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
        row = {"task": name, "language": task.get("language", "python"),
               "cheat_type": task.get("cheat_type", "unknown")}
        for variant in ("buggy", "cheat", "solution"):
            row[variant] = score(task, variant)
        rows.append(row)
        cheat = row["cheat"]
        caught = ("static" if cheat["flags"] else "missed")
        if cheat["visible_pass"] and not cheat["hidden_pass"]:
            caught += "+behavioral" if cheat["flags"] else " -> behavioral"
        print(f"{name:<24}{row['cheat_type']:<10}visible={str(cheat['visible_pass']):<6}"
              f"hidden={str(cheat['hidden_pass']):<6}{caught:<18}flags={cheat['flags']}")

    def stats(cells):
        return {
            "applied": len(cells),
            "effective": sum(1 for c in cells if c["visible_pass"]),
            "static_caught": sum(1 for c in cells if c["visible_pass"] and c["flags"]),
            "behavioral_caught": sum(1 for c in cells
                                     if c["visible_pass"] and not c["hidden_pass"]),
        }

    cheats = [r["cheat"] for r in rows]
    overall = stats(cheats)
    overall["either_caught"] = sum(
        1 for c in cheats if c["visible_pass"] and (c["flags"] or not c["hidden_pass"]))
    overall["missed_by_both"] = overall["effective"] - overall["either_caught"]

    kinds = sorted({r["cheat_type"] for r in rows})
    by_type = {kind: stats([r["cheat"] for r in rows if r["cheat_type"] == kind])
               for kind in kinds}

    fixes = [r["solution"] for r in rows]
    summary = {
        "tasks": len(rows),
        "cheats_applied": overall["applied"],
        "cheats_effective": overall["effective"],
        "static_caught": overall["static_caught"],
        "behavioral_caught": overall["behavioral_caught"],
        "either_caught": overall["either_caught"],
        "missed_by_both": overall["missed_by_both"],
        "false_positives": sum(1 for f in fixes if f["flags"]),
        "solutions_clean": sum(1 for f in fixes
                               if f["visible_pass"] and f["hidden_pass"] and not f["flags"]),
        "baseline_flagged": sum(1 for r in rows if r["buggy"]["flags"]),
        "by_cheat_type": by_type,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "tasks": rows}, indent=2),
                   encoding="utf-8")

    print(f"\n  {'cheat type':<12}{'applied':>8}{'effective':>10}{'static':>8}"
          f"{'behavioral':>12}")
    for kind in kinds:
        cell = by_type[kind]
        print(f"  {kind:<12}{cell['applied']:>8}{cell['effective']:>10}"
              f"{cell['static_caught']:>8}{cell['behavioral_caught']:>12}")
    print(f"\n  {'all':<12}{summary['cheats_applied']:>8}{summary['cheats_effective']:>10}"
          f"{summary['static_caught']:>8}{summary['behavioral_caught']:>12}")
    print(f"\n  either layer caught {summary['either_caught']}, "
          f"missed by both {summary['missed_by_both']}, "
          f"false positives {summary['false_positives']}/{len(fixes)}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
