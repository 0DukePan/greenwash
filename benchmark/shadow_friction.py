#!/usr/bin/env python3
"""The offline shadow-replay friction harness (Stage 5, friction measures).

Replays the recorded checker outcomes over merged pull requests from
consented repositories and produces the friction numbers, each with its
explicit denominator:

* interruption rate -- flagged pull requests over the pull requests that
  touched tests (the class that can be interrupted);
* unnecessary interruptions -- alerts a human judged the change legitimate
  (the alert was a false alarm, so the interruption was unnecessary) over the
  alerts with a recorded human judgment; a change judged illegitimate made the
  alert necessary, and an unreviewed alert is never counted as unnecessary and
  never enters the reviewed denominator;
* time to resolve -- the interval between the two recorded timestamps, over
  the alerts where both timestamps exist;
* override rate -- alerts with a recorded override event over the flagged
  pull requests;
* removal or opt-out -- repositories with a recorded removal or opt-out event
  over the consented repositories appearing in the PR log.

Consent is a precondition, not a filter: a repository without recorded
consent is refused by name before anything is measured. The harness is
offline -- it reads the two recorded inputs, touches no network, and posts
nothing anywhere; the report states so.

Every rate is `evaluation.rate` exactly as the measurement harness reports
it, so no two columns of a rate are computed over different cases.

Run:  python benchmark/shadow_friction.py --pr-log PR_LOG.json \\
        --consent CONSENT.json [--out results/shadow-friction.json]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import evaluation  # noqa: E402

EXIT_OK = 0
EXIT_REFUSED = 2

OFFLINE_STATEMENT = ("offline shadow replay over the recorded PR log and "
                     "consent file; posts nothing, no network access")

JUDGMENTS = ("legitimate", "illegitimate")

DEN_INTERRUPTION = "merged pull requests that touched tests"
DEN_UNNECESSARY = "flagged pull requests with a recorded human judgment"
DEN_TIME_TO_RESOLVE = "flagged pull requests with both flagged_at and resolved_at"
DEN_OVERRIDE = "flagged pull requests"
DEN_REMOVAL = "consented repositories appearing in the PR log"


class Refusal(Exception):
    """The harness refuses to measure: an input is missing or invalid, or a
    repository has no recorded consent. Never a default, never a guess."""


def _read_json(path, what: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refusal(f"{what} at {path} cannot be read: {exc}") from exc


def _load_pr_log(path) -> list:
    payload = _read_json(path, "the PR log")
    if not isinstance(payload, list) or not payload:
        raise Refusal(f"the PR log at {path} is not a non-empty list of "
                      "pull request records")
    return payload


def _load_consent(path) -> set:
    payload = _read_json(path, "the consent file")
    repositories = payload.get("repositories") if isinstance(payload, dict) \
        else None
    if not isinstance(repositories, list) or not repositories \
            or not all(isinstance(name, str) and name for name in repositories):
        raise Refusal(f"the consent file at {path} does not list repositories "
                      "under \"repositories\"")
    return set(repositories)


def _timestamp(record, field: str):
    value = record.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise Refusal(f"pull request {record.get('pr')!r}: field {field!r} "
                      "is not an ISO 8601 timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Refusal(f"pull request {record.get('pr')!r}: field {field!r} "
                      f"is not an ISO 8601 timestamp: {value!r}") from exc


def _record(record) -> dict:
    """One validated record: every field named by its pull request on
    refusal, never a default for a missing measurement field."""
    pr = record.get("pr")
    repository = record.get("repository")
    if not isinstance(repository, str) or not repository:
        raise Refusal(f"pull request {pr!r}: field 'repository' is missing")
    for field in ("touched_tests", "checker_flagged"):
        if not isinstance(record.get(field), bool):
            raise Refusal(f"pull request {pr!r}: field {field!r} is missing "
                          "or not a boolean")
    judgment = record.get("human_judgment")
    if judgment is not None and judgment not in JUDGMENTS:
        raise Refusal(f"pull request {pr!r}: field 'human_judgment' is "
                      f"{judgment!r}, expected one of {JUDGMENTS} or null")
    for field in ("override", "removal_or_optout"):
        if not isinstance(record.get(field, False), bool):
            raise Refusal(f"pull request {pr!r}: field {field!r} is not a "
                          "boolean")
    flagged_at = _timestamp(record, "flagged_at")
    resolved_at = _timestamp(record, "resolved_at")
    if flagged_at is not None and resolved_at is not None \
            and resolved_at < flagged_at:
        raise Refusal(f"pull request {pr!r}: 'resolved_at' precedes "
                      "'flagged_at'")
    return {"pr": pr, "repository": repository,
            "touched_tests": record["touched_tests"],
            "checker_flagged": record["checker_flagged"],
            "human_judgment": judgment,
            "flagged_at": flagged_at, "resolved_at": resolved_at,
            "override": record.get("override", False),
            "removal_or_optout": record.get("removal_or_optout", False)}


def verify_consent(records: list, consented: set, consent_path) -> None:
    """Consent is a precondition: an unconsented repository is refused by
    name before any measure is computed."""
    unconsented = sorted({r["repository"] for r in records} - consented)
    if unconsented:
        if len(unconsented) == 1:
            raise Refusal(f'repository "{unconsented[0]}" has no recorded '
                          f"consent in {consent_path}")
        names = ", ".join(f'"{name}"' for name in unconsented)
        raise Refusal(f"repositories {names} have no recorded consent in "
                      f"{consent_path}")


def replay(pr_log, consent) -> dict:
    """The friction report over the recorded inputs, denominators explicit."""
    records = [_record(r) for r in _load_pr_log(pr_log)]
    consented = _load_consent(consent)
    verify_consent(records, consented, consent)

    touched = [r for r in records if r["touched_tests"]]
    flagged = [r for r in records if r["checker_flagged"]]
    reviewed = [r for r in flagged if r["human_judgment"] is not None]

    interruption = evaluation.rate(
        (r["repository"], 1 if r["checker_flagged"] else 0) for r in touched)
    interruption["denominator"] = DEN_INTERRUPTION

    unnecessary = evaluation.rate(
        (r["repository"], 1 if r["human_judgment"] == "legitimate" else 0)
        for r in reviewed)
    unnecessary["denominator"] = DEN_UNNECESSARY
    unnecessary["unreviewed_alerts"] = len(flagged) - len(reviewed)

    intervals = [(r["resolved_at"] - r["flagged_at"]).total_seconds()
                 for r in flagged
                 if r["flagged_at"] is not None and r["resolved_at"] is not None]
    time_to_resolve = {
        "n": len(intervals), "flagged_alerts": len(flagged),
        "mean": statistics.mean(intervals) if intervals else None,
        "median": statistics.median(intervals) if intervals else None,
        "min": min(intervals) if intervals else None,
        "max": max(intervals) if intervals else None,
        "denominator": DEN_TIME_TO_RESOLVE}

    override = evaluation.rate(
        (r["repository"], 1 if r["override"] else 0) for r in flagged)
    override["denominator"] = DEN_OVERRIDE

    removed = {r["repository"] for r in records if r["removal_or_optout"]}
    repos = sorted({r["repository"] for r in records})
    removal = evaluation.rate(
        (name, 1 if name in removed else 0) for name in repos)
    removal["denominator"] = DEN_REMOVAL

    return {
        "pr_log": str(pr_log), "consent": str(consent),
        "offline": True, "statement": OFFLINE_STATEMENT,
        "repositories": repos, "merged_prs": len(records),
        "measures": {
            "interruption_rate": interruption,
            "unnecessary_interruption_rate": unnecessary,
            "time_to_resolve_seconds": time_to_resolve,
            "override_rate": override,
            "removal_optout_rate": removal}}


# -- rendering: every measure printed beside its explicit denominator ------


def _fmt_rate(entry) -> str:
    if not entry["n"]:
        return f"{entry['k']}/0=-- (CP95 [--, --])"
    lo, hi = entry["clopper_pearson"]
    return (f"{entry['k']}/{entry['n']}={entry['estimate']:.3f} "
            f"(CP95 [{lo:.3f}, {hi:.3f}])")


def render(report: dict) -> str:
    """The report: the measures, each with its denominator, and the offline
    statement first -- this report is computed from recorded inputs and
    posts nothing."""
    measures = report["measures"]
    time_to_resolve = measures["time_to_resolve_seconds"]
    if time_to_resolve["n"]:
        span = (f"-- mean {time_to_resolve['mean']:.1f}s "
                f"median {time_to_resolve['median']:.1f}s "
                f"min {time_to_resolve['min']:.1f}s "
                f"max {time_to_resolve['max']:.1f}s")
    else:
        span = "-- no interval recorded"
    unnecessary = measures["unnecessary_interruption_rate"]
    return "\n".join([
        f"shadow friction: {OFFLINE_STATEMENT}",
        f"consented repositories in the log ({len(report['repositories'])}): "
        + " ".join(report["repositories"]),
        f"merged pull requests: {report['merged_prs']}",
        f"interruption rate: {_fmt_rate(measures['interruption_rate'])} -- "
        f"denominator: {measures['interruption_rate']['denominator']}",
        f"unnecessary interruptions: {_fmt_rate(unnecessary)} -- "
        f"denominator: {unnecessary['denominator']} "
        f"({unnecessary['unreviewed_alerts']} unreviewed alert"
        f"{'' if unnecessary['unreviewed_alerts'] == 1 else 's'} excluded; "
        f"an unreviewed alert is never counted as unnecessary)",
        f"time to resolve: {time_to_resolve['n']} of "
        f"{time_to_resolve['flagged_alerts']} flagged pull requests with both "
        f"timestamps {span}",
        f"override rate: {_fmt_rate(measures['override_rate'])} -- "
        f"denominator: {measures['override_rate']['denominator']}",
        f"removal or opt-out: {_fmt_rate(measures['removal_optout_rate'])} -- "
        f"denominator: {measures['removal_optout_rate']['denominator']}",
    ]) + "\n"


# -- the command ------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="shadow_friction.py", description=__doc__)
    parser.add_argument("--pr-log", required=True,
                        help="the recorded PR log (one record per merged PR)")
    parser.add_argument("--consent", required=True,
                        help="the consent file (recorded repository consent)")
    parser.add_argument("--out",
                        default=str(HERE / "results" / "shadow-friction.json"))
    args = parser.parse_args(argv)
    try:
        report = replay(args.pr_log, args.consent)
    except Refusal as exc:
        print(f"shadow_friction: refused to run: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(render(report), end="")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"written -> {out}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
