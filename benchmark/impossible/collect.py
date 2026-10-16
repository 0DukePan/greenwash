"""Collect the pilot runs into benchmark/results/pilot.jsonl.

One row per run, scored from the workspace and the recorded transcript.

    python benchmark/impossible/collect.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
RUNS = HERE / "runs"
OUT = HERE.parent / "results" / "pilot.jsonl"


def main() -> int:
    rows = []
    for result_file in sorted(RUNS.glob("*.result.txt")):
        name = result_file.name[:-len(".result.txt")]
        for condition in ("skill-only", "full", "off"):
            if name.endswith("-" + condition):
                task, condition = name[:-(len(condition) + 1)], condition
                break
        scored = subprocess.run(
            [sys.executable, str(HERE / "pilot_score.py"), str(RUNS / name),
             task, condition, str(result_file)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        row = json.loads(scored.stdout.strip().splitlines()[-1])
        rows.append(row)
        print(f"{condition:<11} {task:<22} visible={str(row['visible_pass']):<5} "
              f"hidden={str(row['hidden_pass']):<5} cheated={str(row['cheated']):<5} "
              f"refused={str(row['refused']):<5} {row['outcome']:<15} {row['signals']}")
    OUT.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    print(f"written -> {OUT} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
