#!/usr/bin/env python3
"""The preliminary trial report: what the report-only beta trial measured.

Four inputs, all recorded artifacts, nothing fetched:

* the friction round artifact (benchmark/friction_round.py's report): the five
  friction measures with their explicit denominators, the judgment coverage,
  and the merged PR log it names -- the receipt this report reads the
  per-repository sizes from;
* the usability response rows for the round before and the round after the one
  recorded wording revision (benchmark/usability.py's rows);
* one static-overhead measurement file per repository:

    { "repository": "alpha",
      "measurement": "static scan (scan --json, no test execution), wall
                      milliseconds",
      "runs_ms": [402.0, 386.0, 394.0] }

* the checker version and configuration:

    { "version": "...", "configuration": { ... } }

The report states the participating repositories and their sizes (the merged
pull requests replayed for each), the PR counts behind every denominator, the
five friction measures, the usability share-correct and median time before and
after the one wording revision, the static overhead per repository, the checker
version and configuration, and the open questions. It states in one line that
Gate C is not decided and required mode is out of scope.

Its licensed-wording section renders from the claim ledger rows (claim, allowed
wording) and nothing else; `licensed_wording` refuses a sentence outside those
rows by name. The report is written locally and posts nothing.

Run:  python benchmark/trial_report.py --friction friction-round.json \\
        --responses responses.json --overhead overhead-alpha.json \\
        --checker checker.json [--out results/trial-report.md]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import claim_ledger  # noqa: E402
import friction_round  # noqa: E402
import usability  # noqa: E402

EXIT_OK = 0
EXIT_REFUSED = 2

#: The one line the report owes the reader: a partial trial decides nothing.
GATE_C_LINE = "Gate C is not decided; required mode is out of scope."

#: The questions the trial was opened to answer (the spec's Further Notes).
OPEN_QUESTIONS = (
    "How often does the checker interrupt pull requests that touch tests in "
    "consented repositories?",
    "How often does a human call the interruption unnecessary?",
    "Do developers read the four-part message correctly?",
    "What is the static overhead on real histories?",
)

MEASURES = ("interruption_rate", "unnecessary_interruption_rate",
            "time_to_resolve_seconds", "override_rate", "removal_optout_rate")


class Refusal(Exception):
    """The report refuses to state: an input is missing or invalid. Never a
    default, never a guess, never a number invented."""


def _read_json(path, what: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refusal(f"{what} at {path} cannot be read: {exc}") from exc


# -- inputs -----------------------------------------------------------------


def load_friction(path) -> dict:
    """The friction round artifact, carrying the keys the report states."""
    payload = _read_json(path, "the friction round artifact")
    if not isinstance(payload, dict):
        raise Refusal(f"the friction round artifact at {path} is not a JSON "
                      "object")
    for key in ("repositories", "merged_prs", "merged_pr_log",
                "judgment_coverage", "measures"):
        if key not in payload:
            raise Refusal(f"the friction round artifact at {path} does not "
                          f"carry {key!r}")
    measures = payload["measures"]
    for name in MEASURES:
        if name not in measures:
            raise Refusal(f"the friction round artifact at {path} does not "
                          f"carry the measure {name!r}")
    return payload


def load_responses(path) -> list:
    """The recorded usability response rows, both wording rounds."""
    payload = _read_json(path, "the usability responses")
    if not isinstance(payload, list) or not payload:
        raise Refusal(f"the usability responses at {path} are not a non-empty "
                      "list of response rows")
    return payload


def load_checker(path) -> dict:
    """The checker version and configuration the numbers are attributable to."""
    payload = _read_json(path, "the checker record")
    if not isinstance(payload, dict):
        raise Refusal(f"the checker record at {path} is not a JSON object")
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise Refusal(f"the checker record at {path} does not state a version")
    configuration = payload.get("configuration")
    if not isinstance(configuration, dict):
        raise Refusal(f"the checker record at {path} does not state a "
                      "configuration")
    return {"version": version, "configuration": configuration}


# -- derived numbers ---------------------------------------------------------


def _sizes(friction: dict) -> list:
    """Participating repositories and their sizes: the merged pull requests
    replayed for each, counted from the friction round's merged-log receipt."""
    merged = friction["merged_pr_log"]
    rows = _read_json(merged, "the friction round's merged PR log")
    if not isinstance(rows, list):
        raise Refusal(f"the merged PR log at {merged} is not a list of pull "
                      "request records")
    counts: dict = {}
    for row in rows:
        name = row.get("repository") if isinstance(row, dict) else None
        if not isinstance(name, str) or not name:
            raise Refusal(f"the merged PR log at {merged} holds a record "
                          "without a repository")
        counts[name] = counts.get(name, 0) + 1
    named = list(friction["repositories"])
    if sorted(counts) != sorted(named):
        raise Refusal(f"the merged PR log at {merged} names repositories "
                      f"{sorted(counts)} but the friction round artifact "
                      f"names {sorted(named)}")
    return [{"repository": name, "merged_prs": counts[name]} for name in named]


def _pr_counts(friction: dict) -> dict:
    measures = friction["measures"]
    coverage = friction["judgment_coverage"]
    return {
        "merged_prs": friction["merged_prs"],
        "touched_tests": measures["interruption_rate"]["n"],
        "flagged": measures["override_rate"]["n"],
        "reviewed_alerts": coverage["reviewed"],
        "unreviewed_alerts": coverage["unreviewed"],
        "with_both_timestamps": measures["time_to_resolve_seconds"]["n"],
        "consented_repositories": measures["removal_optout_rate"]["n"]}


def _usability(rows: list, kit: dict) -> dict:
    """Share correct and median seconds before and after the one wording
    revision. Every row is validated first, so a row outside rounds 1 and 2 is
    never silently dropped."""
    try:
        usability.score(rows, kit)
        before_rows = [row for row in rows if row["round"] == 1]
        after_rows = [row for row in rows if row["round"] == 2]
        if not before_rows:
            raise Refusal("the usability responses carry no rows for round 1 "
                          "(before the wording revision)")
        if not after_rows:
            raise Refusal("the usability responses carry no rows for round 2 "
                          "(after the wording revision)")
        before = usability.score(before_rows, kit)
        after = usability.check_target(after_rows, kit)
    except usability.KitError as exc:
        raise Refusal(f"the usability responses cannot be scored: {exc}") \
            from exc
    wording = kit["wording_round"]

    def numbers(result, with_target=False):
        out = {"responses": result["responses"], "correct": result["correct"],
               "share_correct": result["share_correct"],
               "median_seconds": result["median_seconds"]}
        if with_target:
            out.update(target=result["target"], met=result["met"])
        return out

    return {"wording_revision": wording["applied_after_round"],
            "wording_changes": len(wording["changes"]),
            "before": numbers(before),
            "after": numbers(after, with_target=True)}


def _overhead(paths, participating: list) -> list:
    """One static-overhead measurement per participating repository."""
    entries, seen = [], {}
    for path in paths or []:
        payload = _read_json(path, "the overhead measurement")
        if not isinstance(payload, dict):
            raise Refusal(f"the overhead measurement at {path} is not a JSON "
                          "object")
        name = payload.get("repository")
        if not isinstance(name, str) or not name:
            raise Refusal(f"the overhead measurement at {path} does not name "
                          "a repository")
        measurement = payload.get("measurement")
        if not isinstance(measurement, str) or not measurement:
            raise Refusal(f"the overhead measurement at {path} does not state "
                          "what was measured")
        runs = payload.get("runs_ms")
        if not isinstance(runs, list) or not runs:
            raise Refusal(f"the overhead measurement at {path} does not list "
                          "runs_ms")
        for run in runs:
            if isinstance(run, bool) or not isinstance(run, (int, float)) \
                    or run <= 0:
                raise Refusal(f"the overhead measurement at {path}: run "
                              f"{run!r} is not a positive number of "
                              "milliseconds")
        if name in seen:
            raise Refusal(f"repository {name!r}: two overhead measurement "
                          f"files ({seen[name]} and {path})")
        seen[name] = path
        entries.append({"repository": name, "measurement": measurement,
                        "runs": len(runs),
                        "median_ms": float(statistics.median(runs))})
    for name in sorted(n for n in seen if n not in participating):
        raise Refusal(f"repository {name!r}: named by an overhead measurement "
                      "file but absent from the trial")
    for name in participating:
        if name not in seen:
            raise Refusal(f"repository {name!r} has no overhead measurement "
                          "file")
    return sorted(entries, key=lambda entry: entry["repository"])


# -- the report --------------------------------------------------------------


def build(friction, responses, overhead, checker, kit=None) -> dict:
    """The report as data: every number read from a recorded artifact."""
    kit = kit if kit is not None else usability.load_kit()
    artifact = load_friction(friction)
    rows = load_responses(responses)
    entries = _overhead(overhead, list(artifact["repositories"]))
    return {
        "gate_c": GATE_C_LINE,
        "repositories": _sizes(artifact),
        "pr_counts": _pr_counts(artifact),
        "friction": artifact,
        "usability": _usability(rows, kit),
        "overhead": entries,
        "checker": load_checker(checker),
        "open_questions": list(OPEN_QUESTIONS)}


def licensed_wording(sentences=None) -> str:
    """The licensed-wording section, rendered from the claim ledger rows
    (claim, allowed wording).

    With no argument every row is rendered. Given sentences, each must be a
    row's allowed wording exactly; a sentence outside those rows is refused by
    name before anything is rendered.
    """
    rows = claim_ledger.rows()
    if sentences is not None:
        allowed = {row.allowed: row for row in rows}
        chosen = []
        for sentence in sentences:
            row = allowed.get(sentence)
            if row is None:
                raise Refusal(f"sentence {sentence!r} is outside the claim "
                              "ledger rows and cannot be licensed")
            chosen.append(row)
        rows = chosen
    lines = ["| Claim | Allowed wording |", "|---|---|"]
    lines.extend(f"| {row.claim} | {row.allowed} |" for row in rows)
    return "\n".join(lines)


def render(report: dict) -> str:
    """The preliminary trial report: every number beside its denominator or
    sample size, the Gate C line, and the licensed-wording section rendered
    from the claim ledger rows."""
    measures = report["friction"]["measures"]
    counts = report["pr_counts"]
    usability_rows = report["usability"]
    before, after = usability_rows["before"], usability_rows["after"]

    lines = [
        "# Preliminary trial report", "",
        report["gate_c"], "",
        "## Participating repositories and sizes", ""]
    lines.extend(f"{entry['repository']}: {entry['merged_prs']} merged pull "
                 f"requests replayed." for entry in report["repositories"])
    lines += [
        "", "## PR counts and denominators", "",
        f"merged pull requests replayed: {counts['merged_prs']}",
        f"pull requests that touched tests: {counts['touched_tests']} -- "
        f"denominator: {measures['interruption_rate']['denominator']}",
        f"flagged pull requests: {counts['flagged']} -- denominator: "
        f"{measures['override_rate']['denominator']}",
        f"alerts with a recorded human judgment: {counts['reviewed_alerts']} "
        f"-- denominator: "
        f"{measures['unnecessary_interruption_rate']['denominator']}",
        f"unreviewed alerts: {counts['unreviewed_alerts']} (never counted as "
        f"unnecessary)",
        f"flagged pull requests with both timestamps: "
        f"{counts['with_both_timestamps']} -- denominator: "
        f"{measures['time_to_resolve_seconds']['denominator']}",
        f"consented repositories appearing in the PR log: "
        f"{counts['consented_repositories']} -- denominator: "
        f"{measures['removal_optout_rate']['denominator']}",
        "", "## Friction measures", "",
        "```",
        friction_round.render(report["friction"]).rstrip("\n"),
        "```",
        "", "## Usability round", "",
        f"The kit records one wording revision, applied after round "
        f"{usability_rows['wording_revision']} "
        f"({usability_rows['wording_changes']} messages changed).",
        f"before the revision (round 1): {before['correct']} of "
        f"{before['responses']} responses correct -- share correct "
        f"{before['share_correct']}, median time {before['median_seconds']} s "
        f"({before['responses']} responses).",
        f"after the revision (round 2): {after['correct']} of "
        f"{after['responses']} responses correct -- share correct "
        f"{after['share_correct']}, median time {after['median_seconds']} s "
        f"({after['responses']} responses).",
        f"the {after['target']:.0%} target is checked on the round after the "
        f"revision only: "
        f"{'met' if after['met'] else 'not met'} at "
        f"{after['share_correct']}.",
        "", "## Static overhead per repository", ""]
    lines.extend(f"{entry['repository']}: median {entry['median_ms']} ms over "
                 f"{entry['runs']} run"
                 f"{'' if entry['runs'] == 1 else 's'} "
                 f"({entry['measurement']})."
                 for entry in report["overhead"])
    lines += [
        "", "## Checker version and configuration", "",
        f"- version: {report['checker']['version']}",
        f"- configuration: "
        f"{json.dumps(report['checker']['configuration'], sort_keys=True)}",
        "", "## Open questions", ""]
    lines.extend(f"- {question}" for question in report["open_questions"])
    lines += ["", "## Licensed wording", "",
              "Rendered from the claim ledger rows (claim, allowed wording); "
              "a sentence outside those rows is refused.", "",
              licensed_wording(), ""]
    return "\n".join(lines)


# -- the command ------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="trial_report.py", description=__doc__)
    parser.add_argument("--friction", required=True,
                        help="the friction round artifact")
    parser.add_argument("--responses", required=True,
                        help="the usability response rows (rounds 1 and 2)")
    parser.add_argument("--overhead", action="append", required=True,
                        help="a static-overhead measurement file (one per "
                             "repository)")
    parser.add_argument("--checker", required=True,
                        help="the checker version and configuration record")
    parser.add_argument("--out", default=str(HERE / "results" /
                                             "trial-report.md"),
                        help="where to write the report")
    args = parser.parse_args(argv)
    try:
        report = build(args.friction, args.responses, args.overhead,
                       args.checker)
    except Refusal as exc:
        print(f"trial_report: refused to build: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(report) + "\n", encoding="utf-8")
    print(f"written -> {path}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
