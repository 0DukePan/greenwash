#!/usr/bin/env python3
"""The trial's friction round: the reviewed-alerts judgments merged with the
collector's PR log, measured by the existing friction harness.

Two inputs beyond the harness's own: the PR log (benchmark/collector.py's
output) and the reviewed-alerts judgment file -- one entry per reviewed alert,
mapping a PR id to `legitimate` or `illegitimate`, with a reviewer and a date.
The term is about the change, never the alert text: a legitimate change means
the alert was a false alarm and the interruption unnecessary; an illegitimate
change made the alert necessary. An unreviewed alert is absent from the file
and never counted as unnecessary -- absence of review is not a false alarm.

The judgment file is the only source of legitimacy: every log record is merged
with its judgment (if reviewed) and handed to benchmark/shadow_friction.py,
which computes the five measures with their explicit denominators. This round
adds the judgment coverage -- reviewed vs unreviewed alerts -- writes both
artifacts, and posts nothing.

Judgment file schema (JSON, one entry per reviewed alert):

  [ { "pr": "owner/name#41",        -- required, present in the PR log
      "judgment": "legitimate",     -- required: legitimate | illegitimate
      "reviewer": "name",           -- required
      "date": "2024-03-05" } ]      -- required, ISO 8601

An unknown judgment value, a PR id absent from the log, an incomplete entry, a
duplicate judgment, or a malformed field refuses by name before anything is
written. Run:

  python benchmark/friction_round.py --pr-log PR_LOG.json \\
    --judgments JUDGMENTS.json --consent CONSENT.json \\
    [--out results/friction-round.json] [--merged-log results/pr-log-reviewed.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import shadow_friction  # noqa: E402

EXIT_OK = 0
EXIT_REFUSED = 2

JUDGMENTS = shadow_friction.JUDGMENTS
REQUIRED = ("pr", "judgment", "reviewer", "date")


class Refusal(Exception):
    """The round refuses to measure: the judgment file or the PR log is
    missing or invalid. Never a default, never a guess."""


def _read_json(path, what: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refusal(f"{what} at {path} cannot be read: {exc}") from exc


def _entry(entry, row: int) -> tuple:
    """One validated judgment entry: (pr, entry). Every refusal names the
    entry and its pull request; an incomplete entry is never completed with a
    default."""
    if not isinstance(entry, dict):
        raise Refusal(f"judgment entry {row} is not a JSON object")
    pr = entry.get("pr")
    label = f"pull request {pr!r}" if isinstance(pr, str) and pr \
        else f"judgment entry {row}"
    for field in REQUIRED:
        value = entry.get(field)
        if value is None or (isinstance(value, str) and not value):
            raise Refusal(f"{label}: field {field!r} is missing")
        if not isinstance(value, str):
            raise Refusal(f"{label}: field {field!r} is not a string")
    if entry["judgment"] not in JUDGMENTS:
        raise Refusal(f"{label}: judgment {entry['judgment']!r} is not one of "
                      f"{JUDGMENTS}")
    try:
        datetime.fromisoformat(entry["date"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refusal(f"{label}: field 'date' is not an ISO 8601 timestamp: "
                      f"{entry['date']!r}") from exc
    return pr, entry


def load_judgments(path, pr_ids) -> dict:
    """The reviewed-alerts file, validated against the PR log: PR id to
    {judgment, reviewer, date}. An alert absent from the file is unreviewed."""
    payload = _read_json(path, "the judgment file")
    if not isinstance(payload, list):
        raise Refusal(f"the judgment file at {path} is not a list of "
                      "reviewed-alert judgments")
    known = set(pr_ids)
    loaded = {}
    for row, raw in enumerate(payload, start=1):
        pr, entry = _entry(raw, row)
        if pr not in known:
            raise Refusal(f"pull request {pr!r}: judgment names a pull request "
                          "absent from the log")
        if pr in loaded:
            raise Refusal(f"pull request {pr!r}: duplicate judgment")
        loaded[pr] = {"judgment": entry["judgment"], "reviewer": entry["reviewer"],
                      "date": entry["date"]}
    return loaded


# -- the round: merge the judgments into the log, run the harness -----------


def _load_pr_log(path) -> list:
    payload = _read_json(path, "the PR log")
    if not isinstance(payload, list) or not payload:
        raise Refusal(f"the PR log at {path} is not a non-empty list of "
                      "pull request records")
    return payload


def run_round(pr_log, judgments, consent, out=None, merged_log=None) -> dict:
    """The trial's friction round: the judgments merged with the collector's
    PR log, measured by the existing harness, with the judgment coverage --
    reviewed vs unreviewed alerts -- beside the five measures. The merged log
    is always written (the harness measures it, so the merge is a receipt),
    the report when its path is given; both paths default beside the results.
    """
    records = _load_pr_log(pr_log)
    judged = load_judgments(judgments, [r.get("pr") for r in records])
    merged = []
    for record in records:
        row = dict(record)
        entry = judged.get(row.get("pr"))
        if entry is not None:
            row["human_judgment"] = entry["judgment"]
        merged.append(row)

    merged_log = Path(merged_log) if merged_log is not None \
        else HERE / "results" / "pr-log-reviewed.json"
    merged_log.parent.mkdir(parents=True, exist_ok=True)
    merged_log.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    try:
        report = shadow_friction.replay(merged_log, consent)
    except shadow_friction.Refusal as exc:
        raise Refusal(str(exc)) from exc

    unnecessary = report["measures"]["unnecessary_interruption_rate"]
    reviewed, unreviewed = unnecessary["n"], unnecessary["unreviewed_alerts"]
    report["collected_pr_log"] = str(pr_log)
    report["judgments"] = str(judgments)
    report["merged_pr_log"] = str(merged_log)
    report["judgment_coverage"] = {
        "alerts": reviewed + unreviewed, "reviewed": reviewed,
        "unreviewed": unreviewed,
        "denominator": shadow_friction.DEN_OVERRIDE}
    if out is not None:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


# -- rendering: the harness's measures, then the judgment coverage ---------


def render(report: dict) -> str:
    """The five measures each beside its explicit denominator (the harness's
    own report), then the judgment coverage: reviewed vs unreviewed alerts,
    and the rule that an unreviewed alert is never counted as unnecessary."""
    coverage = report["judgment_coverage"]
    line = (f"judgment coverage: {coverage['reviewed']} of "
            f"{coverage['alerts']} alerts reviewed -- {coverage['unreviewed']} "
            f"unreviewed alert{'' if coverage['unreviewed'] == 1 else 's'} "
            f"(denominator: {coverage['denominator']}; an unreviewed alert is "
            f"never counted as unnecessary)")
    return shadow_friction.render(report) + line + "\n"


# -- the command ------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="friction_round.py", description=__doc__)
    parser.add_argument("--pr-log", required=True,
                        help="the collector's recorded PR log")
    parser.add_argument("--judgments", required=True,
                        help="the reviewed-alerts judgment file")
    parser.add_argument("--consent", required=True,
                        help="the consent file (recorded repository consent)")
    parser.add_argument("--out", default=str(HERE / "results" /
                                             "friction-round.json"),
                        help="where to write the round's report")
    parser.add_argument("--merged-log",
                        default=str(HERE / "results" / "pr-log-reviewed.json"),
                        help="where to write the merged PR log")
    args = parser.parse_args(argv)
    try:
        report = run_round(args.pr_log, args.judgments, args.consent,
                           out=args.out, merged_log=args.merged_log)
    except Refusal as exc:
        print(f"friction_round: refused to run: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(render(report), end="")
    print(f"written -> {args.out}")
    print(f"written -> {args.merged_log}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
