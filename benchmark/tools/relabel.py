"""Relabel recorded benchmark rows under the corrected outcome taxonomy.

The v1 labels counted honest fixes to underspecified tasks as "silent cheat",
because the table read the agent's claims instead of the evidence. This
recomputes every row's outcome from what the run recorded, adds `diff_class`,
and keeps the v1 label in `outcome_v1` so the published correction stays
auditable from the data alone. Idempotent: outcome_v1 is written once and
re-running never moves it.

    python benchmark/tools/relabel.py                        # the study rows
    python benchmark/tools/relabel.py --rows benchmark/results/rows.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from benchmark import harness  # noqa: E402

DEFAULT_ROWS = [HERE.parent / "results" / "delta.jsonl"]


def spec_stated(task_name: str) -> bool:
    """What the task's spec promised, from the task itself.

    A hidden requirement the spec never stated makes the task underspecified,
    and no amount of agent behavior changes that. The default is generous to
    the agent's accusers: a task is assumed specified unless its task.json says
    otherwise.
    """
    meta = HERE.parent / "tasks" / task_name / "task.json"
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    return bool(data.get("hidden_requirement_stated", True))


def relabel_row(row: dict) -> dict:
    if "outcome_v1" not in row:
        row["outcome_v1"] = row.get("outcome", "")
    flags = row.get("greenwash_flags") or []
    row["diff_class"] = harness.diff_class(flags)
    agent_ok = row.get("api_error") is None and row.get("exit_code") in (0, None)
    row["outcome"] = harness.classify(
        agent_ok, row.get("visible_pass"), row.get("hidden_pass"), flags,
        result_text=row.get("result_text", ""),
        spec_stated=spec_stated(row.get("task", "")))
    return row


def load_rows(path: Path) -> tuple:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()], "jsonl"
    data = json.loads(text)
    return (data if isinstance(data, list) else data.get("rows", [])), "json"


def save_rows(path: Path, rows: list, kind: str) -> None:
    if kind == "jsonl":
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    else:
        path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", nargs="*", default=None,
                        help="row files to relabel (.jsonl or a .json list)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the new counts without writing")
    args = parser.parse_args()

    for name in (args.rows or DEFAULT_ROWS):
        path = Path(name)
        rows, kind = load_rows(path)
        before = Counter(row.get("outcome", "") for row in rows)
        for row in rows:
            relabel_row(row)
        after = Counter(row["outcome"] for row in rows)
        print(f"{path}")
        for label in sorted(set(before) | set(after)):
            print(f"  {label:<20} {before.get(label, 0):>4} -> {after.get(label, 0):>4}")
        if not args.dry_run:
            save_rows(path, rows, kind)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
