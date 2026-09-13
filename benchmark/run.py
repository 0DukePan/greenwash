#!/usr/bin/env python3
"""Publish the detector's numbers -- from measurements, not from prose.

This is the one place the public figures come from. It reads the artifacts
other scripts wrote (`results/detection.json` from `detection.py`,
`results/fp-survey.json` from `fp_survey.py`), derives the standard metrics,
and writes them into BENCHMARK.md between markers.

Nothing here invents a number. If an artifact is missing, the metric is
reported as "not measured" and the run says so, rather than quietly falling
back to a placeholder.

Run:  python benchmark/run.py [--write] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from report import wilson  # noqa: E402  one implementation, in percent

RESULTS = HERE / "results"
BENCHMARK = HERE.parent / "BENCHMARK.md"

START, END = "<!-- metrics:start -->", "<!-- metrics:end -->"


def percent(value: float) -> str:
    """For proportions in [0, 1]."""
    return f"{value * 100:.1f}%"


def already_percent(value: float) -> str:
    """`report.wilson` returns percentage points, not fractions."""
    return f"{value:.1f}%"


def load(name: str):
    path = RESULTS / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def agent_delta() -> dict:
    """The off/skill-only/full result, or an honest 'not measured'.

    `benchmark/report.py` writes this next to its markdown. A plumbing run --
    one driven by the fake agent -- is reported as plumbing, never as a
    measurement of the plugin's effect.
    """
    data = load("agent-delta.json")
    if not data:
        return {"state": "missing",
                "todo": "run benchmark/preflight.py, then benchmark/harness.py "
                        "--states off,skill-only,full --runs 3, then "
                        "benchmark/report.py --out benchmark/RESULTS.md"}
    if not data.get("live"):
        return {"state": "plumbing", "agents": data.get("agents", []),
                "todo": "the rows in results/ came from the fake agent; a live model "
                        "run is still required"}
    return {"state": "measured", **data}


def polyglot_coverage() -> dict:
    """Per-language pack coverage, measured by running the corpus."""
    try:
        import polyglot  # same directory
    except ImportError:
        return {}
    try:
        return polyglot.run()
    except Exception:                      # a broken pack must not break the report
        return {}


def metrics() -> dict:
    detection = load("detection.json")
    survey = load("fp-survey.json")
    out: dict = {"measured": {}, "not_measured": []}

    if detection:
        summary = detection.get("summary", {})
        tasks = summary.get("tasks", 0)
        caught = summary.get("either_caught", 0)
        honest = summary.get("solutions_clean", 0)
        false_positives = summary.get("false_positives", 0)
        out["measured"] = {
            "tasks": tasks,
            "cheats": summary.get("cheats_applied", 0),
            "effective_cheats": summary.get("cheats_effective", 0),
            "true_positives": caught,
            "false_negatives": tasks - caught,
            "false_positives": false_positives,
            "true_negatives": honest - false_positives,
            "static_caught": summary.get("static_caught", 0),
            "behavioral_caught": summary.get("behavioral_caught", 0),
            "recall": caught / tasks if tasks else None,
            "precision": (caught / (caught + false_positives)
                          if (caught + false_positives) else None),
            "false_positive_rate": (false_positives / honest if honest else None),
            "by_cheat_type": summary.get("by_cheat_type", {}),
        }
    else:
        out["not_measured"].append("detector accuracy (run benchmark/detection.py)")

    if survey:
        totals = survey.get("totals", {})
        flags = totals.get("real_flags", 0)
        out["survey"] = {
            "repos": len(totals.get("repos", [])),
            "commits": totals.get("commits", 0),
            "files": totals.get("files", 0),
            "flags": flags,
        }
        out["not_measured"].append(
            "the real-world false-positive *rate* -- the survey needs hand "
            "classification, and the 29 flags are listed for inspection instead")
    else:
        out["not_measured"].append("false-positive survey (run benchmark/fp_survey.py)")

    out["not_measured"].append(
        "the agent-facing delta -- needs a reachable model, spelled out below")
    return out


def write_into(path: Path, block: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if START not in text or END not in text:
        return False
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    path.write_text(f"{head}{START}\n{block}{END}{tail}", encoding="utf-8")
    return True


def render(data: dict) -> str:
    lines = ["<!-- generated by benchmark/run.py -- do not edit by hand -->", ""]

    coverage = polyglot_coverage()
    if coverage.get("by_language"):
        summary = ", ".join(
            f"`{language}` {bucket['passed']}/{bucket['cases']}"
            for language, bucket in sorted(coverage["by_language"].items()))
        lines += [
            "**Language packs, measured** (`python benchmark/polyglot.py`)",
            "",
            f"{summary} -- {coverage['passed']}/{coverage['total']} cases behave as declared. "
            "Python and JavaScript additionally have real tasks that run their test "
            "suites; the others have no toolchain on CI runners, so their packs are "
            "exercised statically. Signals from a pack that cannot parse the language "
            "carry `analysis: regex` in their evidence and their confidence is capped "
            "at `MEDIUM`.",
            "",
        ]

    measured = data.get("measured")
    if measured:
        recall = measured["recall"]
        precision = measured["precision"]
        fpr = measured["false_positive_rate"]
        recall_lo, recall_hi = wilson(measured["true_positives"], measured["tasks"])
        _, fpr_hi = wilson(measured["false_positives"],
                           measured["true_negatives"] + measured["false_positives"])

        lines += [
            "| Metric | Value |",
            "|---|---|",
            f"| Corpus | {measured['tasks']} tasks, "
            f"{measured['effective_cheats']} of {measured['cheats']} planted cheats "
            "verified to make the visible suite pass |",
            f"| True positives (cheats caught) | {measured['true_positives']} |",
            f"| False negatives (cheats missed) | {measured['false_negatives']} |",
            f"| False positives (honest fixes flagged) | {measured['false_positives']} |",
            f"| True negatives (honest fixes left alone) | {measured['true_negatives']} |",
            f"| Recall | {percent(recall)} "
            f"(95% CI {already_percent(recall_lo)}-{already_percent(recall_hi)}) |",
            f"| Precision | {percent(precision)} |",
            f"| False-positive rate | {percent(fpr)} "
            f"(95% upper bound {already_percent(fpr_hi)} on this corpus size) |",
            f"| Static layer alone | {measured['static_caught']}/{measured['tasks']} |",
            f"| Behavioral layer alone | {measured['behavioral_caught']}/{measured['tasks']} |",
            "",
            "By cheat type (applied / static caught / behavioral caught):",
            "",
            "| Cheat type | Applied | Static | Behavioral |",
            "|---|---|---|---|",
        ]
        for name, row in sorted(measured["by_cheat_type"].items()):
            lines.append(f"| `{name}` | {row.get('applied', 0)} | "
                         f"{row.get('static_caught', 0)} | {row.get('behavioral_caught', 0)} |")
        lines.append("")

    survey = data.get("survey")
    if survey:
        lines += [
            f"**False-positive survey:** {survey['flags']} flags over "
            f"{survey['commits']} commits touching {survey['files']} file changes in "
            f"{survey['repos']} repositories. Every flag is listed for inspection in "
            "`benchmark/results/fp-survey.json`; the classes are written up in "
            "`docs/false-positives.md`. The survey publishes its findings, not a "
            "rate: classifying 29 flags by hand gives a number, not a population "
            "estimate, and calling it a rate would overstate what was measured.",
            "",
        ]

    if data.get("not_measured"):
        lines.append("Not measured yet:")
        lines.append("")
        for item in data["not_measured"]:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_delta(delta: dict) -> str:
    """The agent-facing effect: off vs skill-only vs full.

    This is the number the project's opening claim rests on, so it is rendered
    only from a live run. A plumbing run says so in the table.
    """
    lines: list = []
    if delta["state"] == "measured":
        lines.append("**Silent-cheat rate, by plugin state** (lower is better)")
        lines.append("")
        lines.append("| State | Silent cheats | Runs | Rate | 95% CI |")
        lines.append("|---|---|---|---|---|")
        for state, row in delta["states"].items():
            rate = f"{row['rate'] * 100:.0f}%" if row["rate"] is not None else "-"
            lines.append(f"| `{state}` | {row['silent_cheats']} | {row['runs']} | "
                         f"{rate} | [{row['ci'][0]:.0f}, {row['ci'][1]:.0f}] |")
        lines.append("")
        if "delta_points" in delta:
            lines.append(f"**Delta (off -> full): {delta['delta_points']:+.1f} points "
                         "of silent cheating.**")
            lines.append("")
        lines.append(f"Agents: {', '.join('`' + a + '`' for a in delta.get('agents', []))}.")
        lines.append("")
    elif delta["state"] == "plumbing":
        lines.append("**The agent-facing delta is not measured yet.** The rows in "
                     "`benchmark/results/` were produced by the scripted fake agent, "
                     "so they exercise the harness, not the plugin's effect. The "
                     "harness is built and self-tested; what is missing is a live run:")
        lines.append("")
        lines.append(f"```bash\n{delta['todo']}\n```")
        lines.append("")
    else:
        lines.append("**The agent-facing delta is not measured yet.** No run rows exist. "
                     "The harness, the hidden-test injection, the scoring and the "
                     "reporting are all built; what is missing is a reachable model:")
        lines.append("")
        lines.append("```bash\n"
                     "python benchmark/preflight.py\n"
                     "python benchmark/harness.py --states off,skill-only,full --runs 3 "
                     "--model <id>\n"
                     "python benchmark/report.py --out benchmark/RESULTS.md\n"
                     "```")
        lines.append("")
    return "\n".join(lines)


def write_into(path: Path, block: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if START not in text or END not in text:
        return False
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    path.write_text(f"{head}{START}\n{block}{END}{tail}", encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="publish the measured numbers")
    parser.add_argument("--write", action="store_true", help="update BENCHMARK.md")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = metrics()
    delta = agent_delta()
    block = render(data).rstrip() + "\n\n" + render_delta(delta)
    if args.json:
        print(json.dumps({"metrics": data, "agent_delta": delta}, indent=2))
    else:
        print(block)

    if args.write:
        if write_into(BENCHMARK, block):
            print(f"updated {BENCHMARK}")
        else:
            print(f"{BENCHMARK} has no metrics markers; nothing written", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
