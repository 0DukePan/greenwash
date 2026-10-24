#!/usr/bin/env python3
"""The dev-run command: ordered checkpoints over a development corpus.

One command, ordered checkpoints (docs/specs/dev-corpus-run.md,
Implementation Decisions): the stages `assemble`, `calibrate`, `label`,
`adjudicate`, `twins`, `baselines`, `evaluate` and `gate-a` run in that
order, each stage checks the artifacts of its predecessors, refuses out of
order by name, and writes its own artifact under the dev-run directory. A
bare invocation prints the current state and the next required stage, so
the sequence is never held in anyone's head; re-running the command resumes
the run.

This module builds the first stage and the state machinery around it. The
`assemble` stage:

* reads candidate records from a directory -- miner and importer records
  interchangeably, one JSON case file each (case record v2);
* deduplicates by diff hash across routes: one change cannot inflate two
  classes, so a duplicate is a refusal naming the hash and its carriers,
  never a silent drop;
* enforces the corpus kit's five-per-repository cap per class (rejection,
  never silent capping), naming the repository;
* requires a collection route and a taxonomy technique per record, and
  refuses any record carrying labels or adjudication -- an assembled record
  is unadjudicated until the label workflow says otherwise;
* excludes planted and synthetic material by the corpus kit's own
  provenance categories -- plumbing that may be reported, never dev-split
  cases;
* warns -- never silently accepts -- when a class is under the dev minimum
  of sixty;
* writes a versioned dev manifest with the input hashes, the record set and
  the counts by route and class. The dev split is mutable by design: a
  rerun on changed inputs replaces the manifest and records the new hashes.

Fail closed, naming the field, everywhere: a missing field, a duplicate
diff hash, an over-cap repository, a synthetic record, a record carrying
labels and an out-of-order stage are refusals naming the cause.

The seam (a library call plus this module's `main`):

    manifest = assemble(candidates_dir, run_dir)   # the stage itself
    state = stage_state(run_dir)                   # current and next stage
    exit_code = dev_run(argv)                      # the command

This module extends the corpus kit rather than restating it: record
validation, the taxonomy technique check, the provenance categories and the
five-per-repository cap come from `greenwash.corpus`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from greenwash.corpus import (GATE_MAX_PER_REPOSITORY, NON_GATE_SOURCES,
                              SYNTHETIC, source_category, validate_case,
                              validate_cases)
from greenwash.evidence import read_json

#: The ordered checkpoints. A stage runs only after its predecessors.
STAGES = ("assemble", "calibrate", "label", "adjudicate", "twins",
          "baselines", "evaluate", "gate-a")

#: The artifact each stage writes under the dev-run directory. Only the
#: assemble artifact is written by this ticket; the rest are the skeleton's
#: ordered names, so the state machinery already knows the whole sequence.
ARTIFACTS = {
    "assemble": "dev-manifest.json",
    "calibrate": "calibration.json",
    "label": "labels.json",
    "adjudicate": "adjudication.json",
    "twins": "twins.json",
    "baselines": "baselines.json",
    "evaluate": "dev-table.json",
    "gate-a": "gate-a.json",
}

DEV_MANIFEST = "dev-manifest.json"
MANIFEST_VERSION = 1

#: The dev minimum per class (the halved recommendation: sixty per class).
#: A class under it is warned about, never silently accepted.
DEV_MINIMUM = 60

EXIT_OK = 0
EXIT_REFUSED = 2


class DevRunError(ValueError):
    """A stage refused to run.

    Refused by name, never defaulted: a dev run built on a record or an
    order nobody checked is worse than no dev run.
    """


def _fail(message: str) -> None:
    raise DevRunError(f"dev-run: {message}")


# -- the checkpoint state: where the run is, and what is next ----------------

def stage_state(run_dir) -> dict:
    """The dev run's state: completed stages, the current one, the next.

    A stage is complete when its artifact exists under the dev-run
    directory. `current` is the last completed stage (None before any runs)
    and `next` is the first incomplete one -- the stage the next invocation
    must run.
    """
    run_dir = Path(run_dir)
    completed = tuple(stage for stage in STAGES
                      if (run_dir / ARTIFACTS[stage]).exists())
    remaining = [stage for stage in STAGES if stage not in completed]
    return {
        "completed": completed,
        "current": completed[-1] if completed else None,
        "next": remaining[0] if remaining else None,
    }


def render_state(state: dict) -> str:
    """The state as two lines: the current stage and the next required one."""
    current = state["current"] or "none"
    nxt = state["next"] or "none; every stage is complete"
    return (f"dev-run: current stage: {current}\n"
            f"dev-run: next required stage: {nxt}")


def _check_order(stage: str, run_dir) -> None:
    """The ordering rule: a stage runs only after its predecessors.

    Out of order is a refusal naming the stage and its prerequisite. The
    assemble stage is exempt: it re-runs on changed inputs and replaces its
    own artifact.
    """
    if stage not in STAGES:
        _fail(f"refused stage {stage!r}; not one of: {', '.join(STAGES)}")
    index = STAGES.index(stage)
    if stage == "assemble":
        return
    completed = set(stage_state(run_dir)["completed"])
    missing = [name for name in STAGES[:index] if name not in completed]
    if missing:
        prerequisite = STAGES[index - 1]
        detail = ("" if prerequisite == missing[0]
                  else f" (first incomplete stage: {missing[0]})")
        _fail(f"refused stage {stage}: out of order; its prerequisite "
              f"{prerequisite} is not complete{detail}")


# -- the command -------------------------------------------------------------

def dev_run(argv=None) -> int:
    """The dev-run command: run one stage, or print the state.

    Exit 0 is a result (a state line, or a stage that ran); exit 2 is a
    refusal naming the cause.
    """
    parser = argparse.ArgumentParser(prog="dev_run.py", description=__doc__)
    parser.add_argument("stage", nargs="?",
                        help="the checkpoint to run (see the ordered stages)")
    parser.add_argument("candidates", nargs="?",
                        help="the directory of candidate records (assemble)")
    parser.add_argument("--run-dir", default="dev-run",
                        help="the dev-run directory (default: ./dev-run)")
    args = parser.parse_args(argv)
    if args.stage is None:
        print(render_state(stage_state(args.run_dir)))
        return EXIT_OK
    try:
        _check_order(args.stage, args.run_dir)
        _run(args.stage, args.candidates, Path(args.run_dir))
    except DevRunError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_REFUSED
    return EXIT_OK


def _run(stage: str, candidates, run_dir: Path) -> None:
    """One stage, after the ordering check. Only assemble is built so far."""
    if stage == "assemble":
        if not candidates:
            _fail("assemble: missing candidates directory; assemble reads "
                  "candidate records from a directory")
        manifest = assemble(candidates, run_dir)
        _report(manifest, run_dir)
        return
    _fail(f"refused stage {stage}: named in the ordered skeleton but not "
          f"built; this dev run builds the assemble stage only")


def _report(manifest: dict, run_dir: Path) -> None:
    """What ran: counts by route and class, and every warning."""
    routes = ", ".join(f"{name}={count}"
                       for name, count in manifest["counts_by_route"].items())
    classes = ", ".join(f"{name}={count}"
                        for name, count in manifest["counts_by_class"].items())
    total = len(manifest["records"])
    print(f"dev-run: assemble: wrote {DEV_MANIFEST} ({total} records)")
    print(f"dev-run: counts by route: {routes}")
    print(f"dev-run: counts by class: {classes}")
    for warning in manifest["warnings"]:
        print(f"dev-run: WARNING: {warning}", file=sys.stderr)


# -- the assemble stage ------------------------------------------------------

def read_candidates(candidates_dir) -> list:
    """Every candidate record file in the directory, hashed as input.

    One JSON case file per record, the layout the miners and importers
    write. Each entry is `(file name, record, sha256 of the file bytes)` --
    the manifest's input hashes.
    """
    root = Path(candidates_dir)
    if not root.is_dir():
        _fail(f"candidates: {root} is not a directory of candidate records")
    paths = sorted(path for path in root.glob("*.json"))
    if not paths:
        _fail(f"candidates: no candidate records in {root}")
    entries = []
    for path in paths:
        try:
            record, digest = read_json(path)
        except Exception as exc:  # noqa: BLE001 - named, then refused
            _fail(f"candidates: {exc}")
        entries.append((path.name, record, digest.split(":", 1)[1]))
    return entries


def _assembly_issues(record) -> list:
    """What the assemble stage refuses beyond the corpus kit's validation.

    A route and a taxonomy technique are required (the technique check is
    `validate_case`'s own), an assembled record is unadjudicated -- a record
    carrying labels or an adjudicated label is refused -- and planted or
    synthetic material is excluded by the corpus kit's provenance
    categories: plumbing that may be reported, never dev-split cases.
    """
    issues: list = []
    if not str(record.get("route") or "").strip():
        issues.append("route: missing; an assembled record carries its "
                      "collection route (R1 to R5)")
    if not str(record.get("diff_hash") or "").strip():
        issues.append("diff_hash: missing; an assembled record carries the "
                      "diff hash it deduplicates by")
    if record.get("labels"):
        issues.append("labels: an assembled record is unadjudicated; a "
                      "record carrying labels or an adjudicated label is "
                      "refused")
    category = source_category(record)
    if category in NON_GATE_SOURCES:
        issues.append(f"source: a {category} record; planted and synthetic "
                      "material is plumbing, never a dev-split case")
    if record.get("origin") == SYNTHETIC:
        issues.append("origin: a synthetic injected tamper; synthetic "
                      "material is plumbing, never a dev-split case")
    return issues


def _diff_hash_issues(entries) -> list:
    """Deduplication by diff hash, across routes: rejection, never a drop."""
    carriers: dict = {}
    for name, record, _digest in entries:
        carriers.setdefault(str(record.get("diff_hash") or ""), []).append(name)
    return [f"diff_hash: {digest} is carried by {', '.join(names)}; one "
            "change cannot inflate two classes -- duplicates are refused, "
            "never silently dropped"
            for digest, names in sorted(carriers.items())
            if len(names) > 1]


def _cap_issues(records) -> list:
    """The five-per-repository cap per class: rejection, never silent capping."""
    counts: dict = {}
    for record in records:
        key = (str(record.get("label") or ""), str(record.get("repository") or ""))
        counts[key] = counts.get(key, 0) + 1
    over = sorted((label, repository, n)
                  for (label, repository), n in counts.items()
                  if n > GATE_MAX_PER_REPOSITORY)
    return [f"repository: {repository} contributes {n} cases to class "
            f"{label!r}, above the {GATE_MAX_PER_REPOSITORY}-case "
            "per-repository cap; the class is rejected, never silently capped"
            for label, repository, n in over]


def _class_warnings(records) -> list:
    """A class under the dev minimum: warned about, never silently accepted."""
    counts: dict = {}
    for record in records:
        label = str(record.get("label") or "")
        counts[label] = counts.get(label, 0) + 1
    return [f"class {label}: {count} records, under the dev minimum of "
            f"{DEV_MINIMUM}; the dev split is warned about, never silently "
            "accepted"
            for label, count in sorted(counts.items())
            if count < DEV_MINIMUM]


def assemble(candidates_dir, run_dir) -> dict:
    """The assemble stage: candidate records in, a dev manifest out.

    Every refusal names the offending record and field. The manifest is
    versioned and mutable by design: a rerun on changed inputs replaces it
    and records the new input hashes. It never marks anything frozen.
    """
    entries = read_candidates(candidates_dir)
    for name, record, _digest in entries:
        issues = validate_case(record) + _assembly_issues(record)
        if issues:
            _fail(f"{name}: " + "; ".join(issues))
    issues = _diff_hash_issues(entries)
    if issues:
        _fail("; ".join(issues))
    records = [record for _name, record, _digest in entries]
    issues = validate_cases(records) + _cap_issues(records)
    if issues:
        _fail("; ".join(issues))
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "split": "dev",
        "inputs": {name: digest for name, _record, digest in entries},
        "records": sorted(records, key=lambda record: str(record.get("id"))),
        "counts_by_route": _counts(records, "route"),
        "counts_by_class": _counts(records, "label"),
        "warnings": _class_warnings(records),
    }
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / DEV_MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return manifest


def _counts(records, field) -> dict:
    counts: dict = {}
    for record in records:
        key = str(record.get(field) or "")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def main(argv=None) -> int:
    return dev_run(argv)


if __name__ == "__main__":                      # pragma: no cover - CLI
    sys.exit(main())
