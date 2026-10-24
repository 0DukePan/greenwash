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

This module builds the assemble, calibrate, label and adjudicate stages and
the state machinery around them. The `assemble` stage:

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

The `calibrate` stage:

* measures labeling time per case on a supplied calibration file (the
  label workflow's calibration round measures it, one reading per case),
  refusing a case id the dev manifest does not carry -- by name, never
  averaged over;
* writes its measurement artifact under the dev-run directory with the
  hashes of its inputs: the calibration file and the dev manifest;
* closes the labeling-time assumption in the assumptions register with
  status `verified`, the measured number and the artifact path as its
  evidence. The register loader in the Gate A path refuses an assumption
  marked verified without an evidence path by name -- and so does the
  calibrate write path, before anything is written.

The `label` and `adjudicate` stages are the human checkpoints (the
pipeline stops and waits; automation never pretends to label):

* `label` generates the blind packets through the label workflow's
  `blind_packets` -- only after the calibration artifact exists, so the
  guide is fixed before the expensive work -- and writes them with the
  orchestrator's key and the hashes of its inputs. A packet carries only
  the evidence a labeler judges: no detector output, no gold field and no
  other labeler's answer can leak into it.
* `adjudicate` reads the supplied human files -- exactly two label files
  and the adjudication records -- validates every case id they name
  against the dev manifest (outside the split is refused by name), records
  each adjudication exactly once (a second record for a case is refused,
  with no overwrite path), and writes the L9 result in the shape the
  launch criteria engine reads, with the hashes of its inputs. The L9
  output is refused while any case lacks an adjudicated label, naming the
  cases, and the evaluate stage refuses the same way.

Fail closed, naming the field, everywhere: a missing field, a duplicate
diff hash, an over-cap repository, a synthetic record, a record carrying
labels and an out-of-order stage are refusals naming the cause.

The seam (a library call plus this module's `main`):

    manifest = assemble(candidates_dir, run_dir)   # the stage itself
    artifact = calibrate(calibration_file, run_dir)  # the stage itself
    packets = label(run_dir)                       # the blind packets
    result = adjudicate(supplied_dir, run_dir)      # labels in, L9 out
    state = stage_state(run_dir)                   # current and next stage
    exit_code = dev_run(argv)                      # the command

This module extends the corpus kit rather than restating it: record
validation, the taxonomy technique check, the provenance categories and the
five-per-repository cap come from `greenwash.corpus`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gate_a  # noqa: E402
from greenwash.corpus import (GATE_MAX_PER_REPOSITORY,  # noqa: E402
                              NON_GATE_SOURCES, SYNTHETIC, source_category,
                              validate_case, validate_cases)
from greenwash.evidence import read_json  # noqa: E402
from label_workflow import (LabelError, blind_packets,  # noqa: E402
                            calibration_round, ingest_labels, l9_result,
                            read_adjudications, record_adjudication)

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

#: The adjudication store: one decision per case, recorded once (the label
#: workflow's `record_adjudication` owns the once-only rule and its refusal).
#: It is run state, not the stage artifact -- `adjudication.json` is.
ADJUDICATIONS = "adjudications.json"
LABEL_VERSION = 1
ADJUDICATION_VERSION = 1

#: The assumptions register: the program's honest record of what has been
#: measured and what is still assumed. The calibrate stage closes the
#: labeling-time assumption in it -- status `verified`, the measured number
#: and the artifact path as its evidence. The register loader in the Gate A
#: path (benchmark/gate_a.py) refuses a verified assumption without one.
DEFAULT_REGISTER = HERE / "assumptions.json"
LABELING_TIME_ASSUMPTION = "labeling-time-per-case"
CALIBRATION_VERSION = 1

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
                        help="the stage's input (assemble: the candidates "
                             "directory; calibrate: the calibration file; "
                             "adjudicate: the supplied files directory)")
    parser.add_argument("--run-dir", default="dev-run",
                        help="the dev-run directory (default: ./dev-run)")
    parser.add_argument("--register", default=str(DEFAULT_REGISTER),
                        help="the assumptions register (data file)")
    args = parser.parse_args(argv)
    if args.stage is None:
        print(render_state(stage_state(args.run_dir)))
        return EXIT_OK
    try:
        if args.stage == "evaluate":
            # The adjudication checkpoint refuses the evaluate stage first:
            # labels can never be defaulted into an evaluation, and the
            # refusal names exactly the cases that would have been.
            missing = unadjudicated_cases(args.run_dir)
            if missing:
                _fail("evaluate: " + ", ".join(missing) + ": lack an "
                      "adjudicated label; the evaluate stage refuses while "
                      "any case lacks an adjudicated label, naming the cases")
        _check_order(args.stage, args.run_dir)
        _run(args.stage, args.candidates, Path(args.run_dir), args.register)
    except DevRunError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_REFUSED
    return EXIT_OK


def _run(stage: str, candidates, run_dir: Path,
         register=DEFAULT_REGISTER) -> None:
    """One stage, after the ordering check. Assemble, calibrate, label and
    adjudicate build."""
    if stage == "assemble":
        if not candidates:
            _fail("assemble: missing candidates directory; assemble reads "
                  "candidate records from a directory")
        manifest = assemble(candidates, run_dir)
        _report(manifest, run_dir)
        return
    if stage == "calibrate":
        if not candidates:
            _fail("calibrate: missing calibration file; the calibrate stage "
                  "measures time per case on a supplied calibration file")
        artifact = calibrate(candidates, run_dir, register=register)
        _report_calibration(artifact, run_dir)
        return
    if stage == "label":
        if candidates:
            _fail(f"label: unexpected input {candidates!r}; the label stage "
                  f"generates its blind packets from the run directory's "
                  f"{DEV_MANIFEST} and {ARTIFACTS['calibrate']}")
        artifact = label(run_dir)
        _report_label(artifact, run_dir)
        return
    if stage == "adjudicate":
        if not candidates:
            _fail("adjudicate: missing supplied files directory; the "
                  "adjudicate stage reads two label files and the "
                  f"{ADJUDICATIONS} records from a directory")
        artifact = adjudicate(candidates, run_dir)
        _report_adjudication(artifact, run_dir)
        return
    _fail(f"refused stage {stage}: named in the ordered skeleton but not "
          f"built; this dev run builds the assemble, calibrate, label and "
          f"adjudicate stages only")


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


# -- the calibrate stage: measurement, then a closed assumption --------------

def _check_register(data) -> None:
    """The register loader's rule, applied at the calibrate write path.

    The Gate A path owns the one register loader (the `_check_assumptions`
    seam of `benchmark/gate_a.py`): it refuses an assumption marked
    verified without an evidence path, by name. The calibrate write path
    runs the same loader before it writes anything, so a register the
    loader refuses is never written further and never closed over.
    """
    try:
        gate_a._check_assumptions(data)
    except gate_a.GateAError as exc:
        message = str(exc)
        _fail(message[len("gate-a: "):] if message.startswith("gate-a: ")
              else message)


def _read_register(register) -> dict:
    """The assumptions register as data -- unreadable or refused, by name."""
    try:
        data = json.loads(Path(register).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _fail(f"assumptions register: cannot read {register}: {exc}; refusing")
    _check_register(data)
    return data


def calibrate(calibration_file, run_dir, register=DEFAULT_REGISTER) -> dict:
    """The calibrate stage: a calibration file in, a closed assumption out.

    The calibration file carries one measured time per case -- the label
    workflow's calibration round measures it -- and the measurement lands
    twice: in the measurement artifact under the dev-run directory, with
    the hashes of its inputs (the calibration file and the dev manifest),
    and in the assumptions register, where labeling time becomes
    `verified` with the measured number and the artifact path as its
    evidence.

    Every refusal is by name: a case id the dev manifest does not carry,
    a stage run before assembly produced its manifest, and a register
    holding an assumption marked verified without an evidence path (the
    register loader refuses it in the Gate A path; the write path refuses
    the same one the same way) all name their cause before anything is
    written.
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / DEV_MANIFEST
    if not manifest_path.exists():
        _fail(f"calibrate: out of order; its prerequisite assemble is not "
              f"complete: {DEV_MANIFEST} is missing under {run_dir}; refusing")
    try:
        measurement = calibration_round(calibration_file)
        payload, calibration_digest = read_json(calibration_file)
        manifest, manifest_digest = read_json(manifest_path)
    except Exception as exc:  # noqa: BLE001 - named, then refused
        _fail(f"calibration: {exc}")
    known = {str(record.get("id") or "")
             for record in manifest.get("records", [])}
    readings = payload.get("readings") if isinstance(payload, dict) else None
    unknown = sorted({str(reading.get("case") or "").strip()
                      for reading in readings or []} - known)
    if unknown:
        _fail("calibration: case id "
              + ", ".join(repr(case_id) for case_id in unknown)
              + " is not in the dev manifest; refusing")
    data = _read_register(register)
    seconds_per_case = measurement["seconds_per_case"]
    artifact_path = run_dir / ARTIFACTS["calibrate"]
    artifact = {
        "measurement_version": CALIBRATION_VERSION,
        "assumption": LABELING_TIME_ASSUMPTION,
        "inputs": {
            Path(calibration_file).name: calibration_digest.split(":", 1)[1],
            DEV_MANIFEST: manifest_digest.split(":", 1)[1]},
        "cases": measurement["cases"],
        "total_seconds": measurement["total_seconds"],
        "seconds_per_case": seconds_per_case,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    for entry in data["assumptions"]:
        if entry.get("id") == LABELING_TIME_ASSUMPTION:
            entry["status"] = "verified"
            entry["number"] = f"{seconds_per_case:g} seconds per case"
            entry[gate_a.ASSUMPTION_EVIDENCE] = str(artifact_path)
            break
    _check_register(data)
    Path(register).write_text(json.dumps(data, indent=2) + "\n",
                              encoding="utf-8")
    return artifact


def _report_calibration(artifact: dict, run_dir: Path) -> None:
    """What ran: the measurement, and the assumption it closed."""
    print(f"dev-run: calibrate: wrote {ARTIFACTS['calibrate']} "
          f"({artifact['cases']} cases, "
          f"{artifact['seconds_per_case']:g} seconds per case)")
    print(f"dev-run: calibrate: closed {LABELING_TIME_ASSUMPTION} "
          f"(verified, evidence {run_dir / ARTIFACTS['calibrate']})")


# -- the label stage: blind packets, then the wait for human files ------------

def label(run_dir) -> dict:
    """The label stage: the dev split in, blind packets out.

    Packets are generated only when the calibration artifact exists -- the
    guide is fixed before the expensive work -- and only from the assembled
    records. The packets are the label workflow's `blind_packets` output:
    the evidence a labeler judges and nothing else, so no detector output,
    no gold field and no other labeler's answer can leak into one however a
    record spells it. The reveal stays with the orchestrator, in the key
    written beside the packets, and the artifact carries the hashes of the
    inputs it consumed: the dev manifest and the calibration artifact.
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / DEV_MANIFEST
    calibration_path = run_dir / ARTIFACTS["calibrate"]
    if not manifest_path.exists():
        _fail(f"label: out of order; its prerequisite assemble is not "
              f"complete: {DEV_MANIFEST} is missing under {run_dir}; refusing")
    if not calibration_path.exists():
        _fail(f"label: the calibration artifact {ARTIFACTS['calibrate']} is "
              f"missing under {run_dir}; blind packets are generated only "
              f"after calibration has closed; refusing")
    try:
        manifest, manifest_digest = read_json(manifest_path)
        _payload, calibration_digest = read_json(calibration_path)
        packets, key = blind_packets(manifest.get("records", []))
    except Exception as exc:  # noqa: BLE001 - named, then refused
        _fail(f"label: {exc}")
    artifact = {
        "label_version": LABEL_VERSION,
        "inputs": {
            DEV_MANIFEST: manifest_digest.split(":", 1)[1],
            ARTIFACTS["calibrate"]: calibration_digest.split(":", 1)[1]},
        "packets": packets,
        "key": key,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / ARTIFACTS["label"]).write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return artifact


def _report_label(artifact: dict, run_dir: Path) -> None:
    """What ran: the packets written, and the human work the run waits for."""
    print(f"dev-run: label: wrote {ARTIFACTS['label']} "
          f"({len(artifact['packets'])} blind packets)")
    print(f"dev-run: label: waiting for two label files; supply them with "
          f"the {ADJUDICATIONS} records to the adjudicate stage")


# -- the adjudicate stage: the split check, one record per case, the L9 result

def _read_supplied_file(path):
    """One supplied file as data -- object or list -- hashed as input.

    `greenwash.evidence.read_json` reads the artifacts this pipeline writes
    (one JSON object each); the adjudication records are a list, so the
    supplied files use the same reading and hashing rules without the
    object-only rule.
    """
    source = Path(path)
    try:
        raw = source.read_bytes()
    except OSError as exc:
        _fail(f"supplied: could not read {source}: {exc}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        _fail(f"supplied: {source} is not UTF-8 JSON: {exc}")
    return payload, "sha256:" + hashlib.sha256(raw).hexdigest()


def _read_supplied(supplied_dir) -> tuple:
    """The human files the adjudicate stage consumes, each hashed as input.

    The directory holds exactly two label files (a labeler and its `entries`
    votes) and the adjudication records (`adjudications.json`, one record of
    case, label and reason per decision). Anything else is refused by name:
    a supplied file nobody can read is never guessed at.
    """
    root = Path(supplied_dir)
    if not root.is_dir():
        _fail(f"adjudicate: {root} is not a directory of supplied label "
              f"files and {ADJUDICATIONS} records")
    label_files: list = []
    records_path = None
    others: list = []
    digests: dict = {}
    for path in sorted(root.glob("*.json")):
        payload, digest = _read_supplied_file(path)
        digests[path.name] = digest.split(":", 1)[1]
        if path.name == ADJUDICATIONS:
            records_path = (path, payload)
        elif isinstance(payload, dict) and payload.get("entries") is not None:
            label_files.append((path.name, payload))
        else:
            others.append(path.name)
    if others:
        _fail("supplied: " + ", ".join(repr(name) for name in others)
              + ": is neither a label file (labeler and entries) nor "
              f"{ADJUDICATIONS}; refusing")
    if records_path is None:
        _fail(f"supplied: {ADJUDICATIONS} is missing; the adjudicate stage "
              f"records the adjudicator's decisions from it")
    if len(label_files) != 2:
        names = ", ".join(name for name, _payload in label_files) or "none"
        _fail(f"supplied: {len(label_files)} label files ({names}); the "
              f"adjudicate stage waits for exactly two label files")
    return label_files, records_path, digests


def _resolve_vote(where: str, entry, key, packets_for, known) -> tuple:
    """One vote's target -- its blind packet id or its case id -- resolved.

    A vote names its packet (what the labeler saw) or its case (the
    operator's collated form); either way the case behind it must be in the
    dev manifest. A case id outside the split is refused by name, so a
    stale file cannot contaminate a run.
    """
    named = [str(entry.get(field) or "").strip()
             for field in ("packet", "case")]
    target = next((value for value in named if value), "")
    if not target:
        _fail(f"{where}: packet: missing; a vote names its packet or case")
    if target in key:
        packet, case_id = target, str((key.get(target) or {}).get("id") or "")
    elif target in packets_for:
        case_id, packet = target, packets_for[target]
    elif target in known:
        _fail(f"{where}: case id {target!r} has no blind packet in "
              f"{ARTIFACTS['label']}; rerun the label stage on the current "
              f"split; refusing")
    else:
        _fail(f"{where}: case id {target!r} is not in the dev manifest; "
              f"refusing")
    if case_id not in known:
        _fail(f"{where}: case id {case_id!r} is not in the dev manifest; "
              f"refusing")
    other = next((value for value in named if value and value not in
                  (target, case_id, packet)), None)
    if other is not None:
        _fail(f"{where}: case id {other!r} is not the case for {target!r}; "
              f"refusing a stale or mismatched label file")
    return packet


def adjudicate(supplied_dir, run_dir) -> dict:
    """The adjudicate stage: two label files and the decisions in, L9 out.

    Every case id the supplied files name is validated against the dev
    manifest first -- outside the split is refused by name, before anything
    is written. Each adjudication is then recorded exactly once through the
    label workflow's `record_adjudication`: a second record for a case is
    refused naming the case, with no overwrite path. The two label files are
    ingested as the double-labeled round (both labelers cover every packet;
    votes name their blind packet or their case), and the L9 result is
    refused -- naming the cases -- while any case lacks an adjudicated
    label. When the round is complete the artifact lands with the hashes of
    its inputs, the disagreements with both reasons, and the L9 result in
    the shape the launch criteria engine reads.
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / DEV_MANIFEST
    labels_path = run_dir / ARTIFACTS["label"]
    if not manifest_path.exists():
        _fail(f"adjudicate: out of order; its prerequisite assemble is not "
              f"complete: {DEV_MANIFEST} is missing under {run_dir}; refusing")
    if not labels_path.exists():
        _fail(f"adjudicate: out of order; its prerequisite label is not "
              f"complete: {ARTIFACTS['label']} is missing under {run_dir}; "
              f"refusing")
    label_files, (_records_path, records), digests = \
        _read_supplied(supplied_dir)
    try:
        manifest, manifest_digest = read_json(manifest_path)
        labels_artifact, labels_digest = read_json(labels_path)
    except Exception as exc:  # noqa: BLE001 - named, then refused
        _fail(f"adjudicate: {exc}")
    key = dict(labels_artifact.get("key") or {})
    known = {str(record.get("id") or "")
             for record in manifest.get("records", [])}
    packets_for = {str(hidden.get("id") or ""): packet_id
                   for packet_id, hidden in key.items()}
    normalized = []
    for name, payload in label_files:
        entries = payload.get("entries")
        if not isinstance(entries, list) or not entries:
            _fail(f"label file {name}: entries: missing; a label file "
                  f"carries its votes")
        votes = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                _fail(f"label file {name}: entries[{index}]: must be a vote "
                      f"of packet or case, label, reason")
            where = f"label file {name}: entries[{index}]"
            packet = _resolve_vote(where, entry, key, packets_for, known)
            votes.append({"packet": packet, "label": entry.get("label"),
                          "reason": entry.get("reason")})
        if not str(payload.get("labeler") or "").strip():
            _fail(f"label file {name}: labeler: missing; a label file names "
                  f"its labeler")
        normalized.append({"labeler": payload["labeler"], "entries": votes})
    store = run_dir / ADJUDICATIONS
    for index, record in enumerate(records or []):
        where = f"{ADJUDICATIONS}: records[{index}]"
        if not isinstance(record, dict):
            _fail(f"{where}: must be a record of case, label, reason")
        case_id = str(record.get("case") or "").strip()
        if not case_id:
            _fail(f"{where}: case: missing; an adjudication names its case")
        if case_id not in known:
            _fail(f"{where}: case id {case_id!r} is not in the dev manifest; "
                  f"refusing")
    for record in records or []:
        case_id = str(record.get("case") or "").strip()
        try:
            record_adjudication(store, case_id, record.get("label"),
                                record.get("reason"))
        except LabelError as exc:
            _fail(f"{ADJUDICATIONS}: {exc}")
    with tempfile.TemporaryDirectory(prefix="dev-run-label-") as tmp:
        paths = []
        for index, payload in enumerate(normalized):
            path = Path(tmp) / f"labeler-{index + 1}.json"
            path.write_text(json.dumps(payload, indent=2) + "\n",
                            encoding="utf-8")
            paths.append(path)
        try:
            session = ingest_labels(key, paths[0], paths[1])
            result = l9_result(session, read_adjudications(store))
        except LabelError as exc:
            _fail(str(exc))
    artifact = {
        "adjudication_version": ADJUDICATION_VERSION,
        "inputs": {
            DEV_MANIFEST: manifest_digest.split(":", 1)[1],
            ARTIFACTS["label"]: labels_digest.split(":", 1)[1],
            **digests},
        "adjudications": read_adjudications(store),
        "disagreements": session["disagreements"],
        "labels": result,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / ARTIFACTS["adjudicate"]).write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return artifact


def unadjudicated_cases(run_dir) -> list:
    """The dev split's cases with no adjudicated label, by name.

    An empty list is a complete label set (or a run nothing was assembled
    from yet -- the ordering refusal names that cause instead).
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / DEV_MANIFEST
    if not manifest_path.exists():
        return []
    try:
        manifest, _digest = read_json(manifest_path)
        adjudications = read_adjudications(run_dir / ADJUDICATIONS)
    except Exception as exc:  # noqa: BLE001 - named, then refused
        _fail(f"evaluate: {exc}")
    return sorted({str(record.get("id") or "")
                   for record in manifest.get("records", [])}
                  - set(adjudications))


def _report_adjudication(artifact: dict, run_dir: Path) -> None:
    """What ran: the adjudications recorded, and the L9 result written."""
    result = artifact["labels"]
    print(f"dev-run: adjudicate: wrote {ARTIFACTS['adjudicate']} "
          f"({len(artifact['adjudications'])} adjudications, "
          f"{len(artifact['disagreements'])} disagreements)")
    print(f"dev-run: adjudicate: L9: double-labeled "
          f"{result['double_labeled_cases']} cases, raw agreement "
          f"{result['raw_agreement']:g}, kappa {result['kappa']:g}, "
          f"pabak {result['pabak']:g}")


def main(argv=None) -> int:
    return dev_run(argv)


if __name__ == "__main__":                      # pragma: no cover - CLI
    sys.exit(main())
