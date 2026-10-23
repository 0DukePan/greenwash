#!/usr/bin/env python3
"""The launch command: one run, three outcomes, seven refusals.

One command runs the launch benchmark end to end and answers with exactly
three outcomes, distinguishable by exit code and by artifacts:

    LAUNCH   exit 0   the report and the decision record are written
    NARROW   exit 1   both are written, and the narrowed report is publishable
    REFUSED  exit 2   neither is written: the inputs cannot be trusted

The seven refusals are enforced **before any evaluation runs**, each naming
its cause: (1) a frozen artifact hash differs from the frozen manifest,
(2) the thresholds file differs from the pre-registration record, (3) the
launch configuration or detector differs from the pre-registration record,
(4) the frozen manifest has already been evaluated with a different detector
hash, (5) a gate input record is planted, synthetic, from the dev split, or
lacks source, repository identity, license, technique or split, (6) any
attempted network access, (7) a baseline pin is missing or unverifiable.
A refusal writes nothing: no report, no decision record, no ledger entry.

The contracts, each one load-bearing:

* **The criteria engine decides.** The command assembles the computed
  evaluation table, the determinism (L4), integrity (L5) and labels (L9)
  inputs, the pre-registration record, the claim-ledger rows and the two
  injected results (the rebuild-equality flag for L6 and the announcement
  check for L7), and `criteria_engine.evaluate_criteria` returns the one
  decision. The command never re-decides anything itself.
* **Determinism (L4) is measured, not assumed.** The launch detector runs
  five times over every frozen case (or a pre-registered stratified sample)
  and the per-case result bytes must be identical across the repeats.
* **The integrity input is assembled from pins.** The integrity suite
  hash-verifies the checker, the configuration and the pinned tests against
  their recorded digests; a file that differs is a successful modification,
  and a suite that cannot name all three kinds did not run (L5 fails closed).
* **The labels input is assembled from the double-labeled sample.** Two
  blind votes per case give raw agreement, kappa and PABAK mechanically.
* **Offline, enforced.** The run blocks network access at the socket; any
  connection attempt raises and the run is refused (6). Nothing in the
  pipeline needs a model or an external tool.
* **Byte stability.** The report and the decision record are generated,
  never typed: LF line endings only, sorted keys, fixed numeric formatting,
  no timestamp in the report, and the decision record's single `generated_at`
  field is the only value that varies between runs. The rebuild comparison
  excludes it **by field name** (`generated_at`), never by pattern, so a
  hand-edited report fails while a fresh timestamp does not.
* **L6 is the rebuild comparison.** The run rebuilds its artifacts from the
  pinned inputs a second time, offline, and requires byte-identical output
  (minus `generated_at`). CI runs `--check`, which rebuilds and compares
  against the committed artifacts and exits nonzero on any hand edit.
* **The README status line is generated, never typed.** `status_line(record)`
  turns the decision record into `UNMEASURED` (no record), `NARROWED` naming
  the failing criteria, or `LAUNCH-READY`; `readme_status_problems` is the
  comparison CI runs against the committed README, so a hand-edited line
  fails the build.

The seam (the command is this one surface and nothing else):

    outcome = launch(corpus_root, thresholds_file, launch_configuration,
                     detector_config, detectors, out_dir=..., ...)
    code = main(argv)

Run:  python benchmark/launch.py --corpus DIR --configuration B1 --out DIR
      [--thresholds FILE] [--announcement FILE] [--labels FILE]
      [--integrity FILE] [--check]

This module extends the merged kits rather than restating them: the
refusals and the burn ledger from `benchmark/preregistration.py`, the
decision from `benchmark/criteria_engine.py`, the computed table and the
interval arithmetic from `benchmark/evaluation.py`, the gate-input
admission from `greenwash.corpus`, and the byte-stability habits from
`benchmark/reproduce.py`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import claim_ledger  # noqa: E402
import criteria_engine  # noqa: E402
import evaluation  # noqa: E402
import preregistration  # noqa: E402
from greenwash import baselines, corpus  # noqa: E402
from greenwash.evidence import EvidenceError  # noqa: E402

EXIT_LAUNCH = 0
EXIT_NARROW = 1
EXIT_REFUSED = 2
EXIT_MISMATCH = 3      # --check: the committed artifacts are not the rebuild
EXIT_USAGE = 64        # usage errors live outside the decision range

REPORT_NAME = "launch-report.md"
RECORD_NAME = "decision-record.json"

# The single field the byte comparison excludes, by field name.
GENERATED_AT = "generated_at"

DETERMINISM_RUNS = 5

# The integrity suite's three kinds of artifact, all required.
INTEGRITY_KINDS = ("checker", "config", "pinned test")

CLAIMS_LINE = re.compile(r"^\s*claims:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
CLAIM_IN_VIOLATION = re.compile(r"claim '([^']+)'")

DEFAULT_OUT = ROOT / "benchmark" / "results" / "launch"


class NetworkAccessError(EvidenceError):
    """Refusal 6: the launch run is offline; a connection attempt fails it."""


# -- refusal 6: the run is offline, enforced at the socket -------------------

class _Offline:
    """Network access is blocked for the duration of the run.

    Every socket entry point raises `NetworkAccessError`, which the run
    reports as refusal 6 -- an attempted connection is not a slow detector,
    it is an input the launch benchmark refuses. The previous socket
    functions are restored on exit, so nothing leaks into the caller.
    """

    _TARGETS = ("socket", "create_connection", "getaddrinfo", "gethostbyname")

    def __enter__(self):
        self._saved = {name: getattr(socket, name) for name in self._TARGETS}

        def denied(*args, **kwargs):
            raise NetworkAccessError(
                "network access: attempted during the launch run; the launch "
                "benchmark runs offline and any connection attempt refuses "
                "the run")

        for name in self._TARGETS:
            setattr(socket, name, denied)
        return self

    def __exit__(self, *exc):
        for name, saved in self._saved.items():
            setattr(socket, name, saved)
        return False


# -- small deterministic serializations --------------------------------------

def _canonical(payload) -> bytes:
    """Compact sorted-key JSON: the bytes every hash is taken over."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")


def preregistration_sha256(record) -> str:
    """The pre-registration hash: sha256 over the record's canonical JSON."""
    return hashlib.sha256(_canonical(record)).hexdigest()


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _record_bytes(payload: dict) -> bytes:
    """The decision record's bytes: LF-only, sorted keys, one trailing LF."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    return text.encode("utf-8")


def _report_bytes(text: str) -> bytes:
    """The report's bytes: LF-only whatever the platform's line ending."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return (normalized.rstrip("\n") + "\n").encode("utf-8")


def without_generated_at(payload: dict) -> dict:
    """The decision record minus its single timestamp, dropped **by field
    name** so the comparison can never be steered by a pattern."""
    return {key: value for key, value in payload.items()
            if key != GENERATED_AT}


# -- the README launch status line, generated from the decision record --------

STATUS_PREFIX = "Launch status:"
STATUS_LINE = re.compile(rf"^{re.escape(STATUS_PREFIX)} .+$", re.MULTILINE)


def status_line(record) -> str:
    """The README's launch status line, generated from the decision record.

    `UNMEASURED` with no record, `NARROWED` naming the failing criteria after
    a NARROW run, and `LAUNCH-READY` when a record exists and every criterion
    held. The README carries this line verbatim; it is generated here and
    never typed.
    """
    if not isinstance(record, dict):
        return f"{STATUS_PREFIX} UNMEASURED"
    failing = [str(cid) for cid in (record.get("failing_criteria") or [])]
    if failing or record.get("decision") == criteria_engine.NARROW:
        return (f"{STATUS_PREFIX} NARROWED (failing criteria: "
                f"{', '.join(failing) or 'none'})")
    return f"{STATUS_PREFIX} LAUNCH-READY"


def read_decision_record(out_dir=None):
    """The committed decision record, or None before the first measurement."""
    path = Path(DEFAULT_OUT if out_dir is None else out_dir) / RECORD_NAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def readme_status_problems(readme_text, record) -> list:
    """Every way the README's status line differs from the generated one.

    Empty when the committed line is the generated line. CI runs this over
    the committed README and the committed decision record, so a hand-edited
    line -- or a record that moved on without the line following it -- fails
    the build.
    """
    expected = status_line(record)
    found = STATUS_LINE.findall(readme_text or "")
    if found == [expected]:
        return []
    if not found:
        return [f"README: no launch status line; the generated one is: "
                f"{expected!r}"]
    if len(found) > 1:
        return [f"README: {len(found)} launch status lines where one belongs; "
                f"the generated one is: {expected!r}"]
    return [f"README: launch status line {found[0]!r} is not the generated "
            f"{expected!r}"]


# -- the three inputs the command assembles for the criteria engine ----------

def _result_bytes(result) -> bytes:
    """One detector verdict as bytes: what L4 compares across repeats."""
    return _canonical({"prediction": result.prediction,
                       "version": result.version,
                       "detail": result.detail})


def determinism_result(detector, records, runs: int = DETERMINISM_RUNS) -> dict:
    """L4's input: `runs` repeats per frozen case, byte differences counted.

    Every case in `records` (every frozen case, or the pre-registered
    stratified sample) is run `runs` times; each repeat's result bytes must
    equal the first. `byte_differences` counts the repeats that differ, so
    zero means the run reproduced every verdict byte for byte.
    """
    cases, techniques, differences = [], set(), 0
    for record in records:
        first = _result_bytes(detector.run(record))
        cases.append(record.case.id)
        techniques.add(record.case.technique)
        for _ in range(runs - 1):
            if _result_bytes(detector.run(record)) != first:
                differences += 1
    return {"byte_differences": differences, "runs": runs,
            "cases": cases, "techniques": sorted(techniques)}


def integrity_result(pin_record) -> dict:
    """L5's input: the integrity suite over checker, config and pinned tests.

    The suite hash-verifies each pinned artifact against its recorded
    digest: a file that differs (or is gone) is a successful modification,
    because the modification landed. A pin record that cannot name all
    three kinds is a suite that did not run, and L5 fails closed on it.
    """
    if pin_record is None:
        return {"suite_ran": False, "successful_modifications": 0,
                "checked": [], "modified": [],
                "note": "no integrity pin record; the suite did not run"}
    try:
        payload = json.loads(Path(pin_record).read_text(encoding="utf-8"))
        pinned = payload["pinned"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise EvidenceError(f"integrity pin record {pin_record}: could not "
                            f"be read: {exc}") from exc
    root = Path(pin_record).parent
    suite_ran = isinstance(pinned, dict) and all(
        kind in pinned for kind in INTEGRITY_KINDS)
    checked, modified = [], []
    for kind in sorted(pinned or {}):
        entry = pinned[kind]
        rel = str(entry.get("path", "")) if isinstance(entry, dict) else ""
        expected = str(entry.get("sha256", "")) if isinstance(entry, dict) else ""
        found = None
        try:
            found = _sha256_bytes((root / rel).read_bytes())
        except OSError:
            found = None
        checked.append(f"{kind}: {rel}")
        if found != expected:
            modified.append(f"{kind}: {rel}")
    return {"suite_ran": bool(suite_ran),
            "successful_modifications": len(modified),
            "checked": checked, "modified": modified}


def labels_result(payload) -> dict:
    """L9's input: raw agreement, kappa and PABAK over the double-labeled
    sample, computed from the two blind votes per case."""
    if payload is None:
        return None
    try:
        annotations = payload["annotations"]
        votes = [entry["labelers"] for entry in annotations.values()
                 if isinstance(entry, dict)
                 and isinstance(entry.get("labelers"), list)
                 and len(entry["labelers"]) == 2]
    except (TypeError, KeyError) as exc:
        raise EvidenceError(f"double-labeled sample: not a record of two "
                            f"blind votes per case: {exc}") from exc
    n = len(votes)
    if not n:
        return {"double_labeled_cases": 0, "pabak": None, "kappa": None,
                "raw_agreement": None}
    agree = sum(1 for first, second in votes if first == second)
    po = agree / n
    labels = sorted({vote for pair in votes for vote in pair})
    pe = sum((sum(1 for first, _ in votes if first == label) / n)
             * (sum(1 for _, second in votes if second == label) / n)
             for label in labels)
    kappa = 1.0 if pe == 1.0 else (po - pe) / (1.0 - pe)
    return {"double_labeled_cases": n, "pabak": 2 * po - 1,
            "kappa": kappa, "raw_agreement": po}


def announcement_result(text: str) -> dict:
    """L7's input: the announcement checked against the claim ledger rows.

    The ledger's registered triggers and forbidden phrasings decide whether
    the draft states more than its row's allowed wording; a claim the draft
    names (its `claims:` line) must map to a ledger row.
    """
    violations = claim_ledger.check_pages({"announcement": text})
    registered = {row.claim for row in claim_ledger.rows()}
    named = set()
    for match in CLAIMS_LINE.finditer(text):
        named.update(part.strip() for part in match.group(1).split(",")
                     if part.strip())
    named.update(match.group(1) for match in
                 (CLAIM_IN_VIOLATION.search(violation)
                  for violation in violations) if match)
    named.update(claim for claim in registered if claim in text)
    return {"claims_outside_ledger": len(violations),
            "claims": sorted(named), "violations": violations}


# -- refusals 4 and 5, the two the merged kits leave to the command ----------

def verify_not_reused(corpus_root, thresholds_file, detector_config,
                      ledger_path) -> None:
    """Refusal 4: a manifest already evaluated with another detector or
    thresholds hash needs a fresh split, never a second try."""
    entries = preregistration.verify_ledger(preregistration.ledger_file(
        ledger_path))
    manifest_sha = corpus.manifest_sha256(corpus_root)
    detector_sha = preregistration.detector_sha256(detector_config)
    thresholds_sha = preregistration.thresholds_sha256(thresholds_file)
    for entry in entries:
        if entry["manifest_sha256"] != manifest_sha:
            continue
        if entry["detector_sha256"] != detector_sha:
            raise EvidenceError(
                f"evaluation ledger: manifest {manifest_sha} was already "
                f"evaluated with detector {entry['detector_sha256']}, not "
                f"{detector_sha}; a fresh split is required")
        if entry["thresholds_sha256"] != thresholds_sha:
            raise EvidenceError(
                f"evaluation ledger: manifest {manifest_sha} was already "
                f"evaluated with thresholds {entry['thresholds_sha256']}, not "
                f"{thresholds_sha}; a fresh split is required")


def verify_gate_inputs(records) -> tuple:
    """Refusal 5: gate inputs are real, adjudicated, frozen cases and
    nothing else -- `corpus.gate_input_issues` names the offending field."""
    gated = [record for record in records
             if record.case.gated and record.case.split == corpus.FROZEN]
    problems = []
    for record in gated:
        issues = corpus.gate_input_issues(record.case)
        if issues:
            problems.append(f"{record.case.id}: " + "; ".join(issues))
    if problems:
        raise EvidenceError("gate inputs: " + "; ".join(problems))
    return tuple(gated)


# -- the pipeline: computed table + assembled inputs + one decision ----------

@dataclass(frozen=True)
class _Built:
    decision: dict
    report: bytes
    record: bytes


@dataclass(frozen=True)
class _Derived:
    """Everything a decision is computed from, derived once from the pins."""

    table: dict
    record: dict
    ledger_rows: tuple
    hashes: dict
    announcement: dict | None


def _gate_class_stats(pooled: dict, key: str) -> dict:
    entry = pooled.get(key)
    if not isinstance(entry, dict):
        return {}
    return {"n_cases": entry.get("n"), "n_repos": entry.get("n_repos"),
            "rho_hat": entry.get("rho_hat"), "rho_used": entry.get("rho_used"),
            "deff": entry.get("deff"), "n_eff": entry.get("n_eff"),
            "k": entry.get("k")}


def _fmt_class(label: str, stats: dict) -> str:
    return (f"{label}: n_cases {stats.get('n_cases', 0)}, "
            f"n_repos {stats.get('n_repos', 0)}, "
            f"rho_hat {stats.get('rho_hat', 0.0):.3f}, "
            f"rho_used {stats.get('rho_used', 0.0):.3f}, "
            f"DEFF {stats.get('deff', 1.0):.3f}, "
            f"n_eff {stats.get('n_eff', 0.0):.2f}")


def _fmt_value(value) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return json.dumps(value, sort_keys=True, default=str)


def render_report(decision: dict, stats: dict, hashes: dict,
                  ledger_rows) -> str:
    """The human report: generated from the decision and its inputs only.

    No timestamp, no measured wall time, no path from the machine that ran
    it: the bytes are a function of the pinned inputs and nothing else.
    """
    lines = ["# Launch benchmark report", "",
             "Generated by `python benchmark/launch.py` beside the machine-"
             "readable decision record. Every number is computed from the",
             "pinned inputs; this file carries no timestamp, so a rebuild is "
             "byte-identical across runs, locales, time zones and line-"
             "ending settings.",
             "",
             f"Decision: {decision['decision']}",
             f"Deciding criterion: "
             f"{decision['deciding_criterion'] or 'none'}",
             f"Failing criteria: "
             f"{', '.join(decision['failing_criteria']) or 'none'}",
             "",
             "## Criteria (fixed order L1-L9)", ""]
    for row in decision["criteria"]:
        verdict = "PASS" if row["pass"] else "FAIL"
        reason = f" ({row['reason']})" if row["reason"] else ""
        lines.append(f"- {row['id']} {row['criterion']}: {verdict}{reason} -- "
                     f"value {_fmt_value(row['value'])}, "
                     f"threshold {row['relation']} "
                     f"{_fmt_value(row['threshold'])}, "
                     f"interval {_fmt_value(row['interval'])}, "
                     f"n_eff {_fmt_value(row['n_eff'])}")
        if row["detail"]:
            lines.append(f"    {row['detail']}")
    lines += ["", "## Gate classes (repository clustering beside every rate)",
              ""]
    for label in ("positives", "twins", "natural_clean"):
        lines.append(_fmt_class(label, stats.get(label, {})))
    lines += ["", "## Designed-for sample (generated from the interval "
              "arithmetic; P(both a recall and a false-alarm gate clear))",
              "",
              "| effective n per class | max errors for a 90% bound "
              "| 99%/1% | 97%/3% | 95%/5% |",
              "|---|---|---|---|---|"]
    for row in decision["designed_for"]:
        odds = row["launch_odds"]
        lines.append(
            f"| {row['effective_n']} | {row['max_errors']} | "
            + " | ".join(f"{odds[label] * 100:.1f}%"
                         for label, _ in evaluation.LAUNCH_ERROR_RATES) + " |")
    lines += ["", "## Pinned artifacts (sha256)", "",
              "| artifact | sha256 |", "|---|---|"]
    for name in sorted(hashes):
        lines.append(f"| {name} | {hashes[name]} |")
    lines += ["", "## Claim wording (rendered from the claim ledger)", "",
              "| claim | status | strongest wording allowed today "
              "| may not say |", "|---|---|---|---|"]
    for row in ledger_rows:
        lines.append(f"| {row.claim} | {row.status} | {row.allowed} | "
                     f"{'; '.join(row.forbidden) or '--'} |")
    if decision["decision"] != criteria_engine.LAUNCH:
        lines += ["", "## Narrowed scope (publishable)", "",
                  "What the measurement supports. Every line is rendered "
                  "from the computed table or the claim ledger; none of it "
                  "is typed:", ""]
        for label in ("positives", "twins", "natural_clean"):
            lines.append(f"- coverage {label}: "
                         + _fmt_class(label, stats.get(label, {})))
        for cid, label in (("L2", "measured twin false-alarm rate"),
                           ("L3", "measured abstention rate")):
            row = next(r for r in decision["criteria"] if r["id"] == cid)
            lines.append(f"- {label}: value {_fmt_value(row['value'])}, "
                         f"interval {_fmt_value(row['interval'])}, "
                         f"n_eff {_fmt_value(row['n_eff'])}")
        lines.append("- the ledger's strongest wording allowed today:")
        for row in ledger_rows:
            lines.append(f"    - {row.claim}: {row.allowed}")
    return "\n".join(lines) + "\n"


def build_artifacts(decision, table, record, hashes) -> _Built:
    """The report and the decision record, generated from data only."""
    cell = table["detectors"].get(record["launch_configuration"]) or {}
    pooled = cell.get("pooled") or {}
    stats = {label: _gate_class_stats(pooled, key)
             for label, key in (("positives", "strict_recall"),
                                ("twins", "twin_false_alarm"),
                                ("natural_clean", "natural_clean_false_alarm"))}
    report_text = render_report(decision, stats, hashes,
                                claim_ledger.rows())
    report = _report_bytes(report_text)
    payload = {
        "schema": 1,
        "decision": decision["decision"],
        "deciding_criterion": decision["deciding_criterion"],
        "failing_criteria": decision["failing_criteria"],
        "criteria": decision["criteria"],
        "launch_configuration": decision["launch_configuration"],
        "designed_for": decision["designed_for"],
        "configuration": hashes["configuration"],
        "hashes": {name: digest for name, digest in hashes.items()
                   if name != "configuration"},
        "preregistration_sha256": hashes["preregistration"],
    }
    payload["hashes"]["report"] = _sha256_bytes(report)
    payload[GENERATED_AT] = datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z")
    return _Built(decision=decision, report=report,
                  record=_record_bytes(payload))


def _derive(corpus_root, thresholds_file, launch_configuration,
            detector_config, detectors, *, announcement, labels, integrity,
            repeats, determinism_runs, record) -> _Derived:
    """One full derivation from the pinned inputs: the computed table with
    the determinism, integrity and labels inputs assembled beside it."""
    records = baselines.load_case_records(corpus_root)
    gated = verify_gate_inputs(records)
    table = evaluation.evaluate(corpus_root, detectors, repeats=repeats)
    launch_detector = next((detector for detector in detectors
                            if getattr(detector, "id", None)
                            == launch_configuration), None)
    table["determinism"] = (
        determinism_result(launch_detector, gated, runs=determinism_runs)
        if launch_detector is not None else None)
    table["integrity"] = integrity_result(integrity)
    table["labels"] = labels_result(
        json.loads(Path(labels).read_text(encoding="utf-8"))
        if labels is not None else None)
    announcement_payload = (
        announcement_result(Path(announcement).read_text(encoding="utf-8"))
        if announcement is not None else None)
    hashes = {
        "corpus_manifest": corpus.manifest_sha256(corpus_root),
        "thresholds_file": preregistration.thresholds_sha256(thresholds_file),
        "detector": preregistration.detector_sha256(detector_config),
        "preregistration": preregistration_sha256(record),
        "configuration": {
            "detector_id": detector_config["id"],
            "detector_sha256": preregistration.detector_sha256(detector_config),
            "detector_version": str(detector_config["version"]),
            "launch_configuration": launch_configuration,
            "baseline_pins": dict(record["baseline_pins"]),
            "taxonomy_version": record["taxonomy_version"],
            "tool_commit": record["tool_commit"]},
    }
    return _Derived(table=table, record=record,
                    ledger_rows=claim_ledger.rows(), hashes=hashes,
                    announcement=announcement_payload)


def _decide_and_build(derived: _Derived, rebuild_equal: bool) -> _Built:
    decision = criteria_engine.evaluate_criteria(
        derived.table, derived.record, derived.ledger_rows, rebuild_equal,
        derived.announcement)
    return build_artifacts(decision, derived.table, derived.record,
                           derived.hashes)


def _rebuilt_identically(first: _Built, second: _Built) -> bool:
    """The rebuild comparison: bytes, with `generated_at` excluded by field
    name on the decision record (the report carries no timestamp at all)."""
    return (first.report == second.report
            and without_generated_at(json.loads(first.record))
            == without_generated_at(json.loads(second.record)))


# -- the seam ----------------------------------------------------------------

@dataclass(frozen=True)
class LaunchOutcome:
    """One run's answer: the exit code, the artifacts and the decision."""

    exit_code: int
    report: bytes | None = None
    record: bytes | None = None
    decision: dict | None = None
    refusal: str | None = None


def launch(corpus_root, thresholds_file, launch_configuration, detector_config,
           detectors, *, out_dir, ledger_path=None, retired_path=None,
           announcement=None, labels=None, integrity=None,
           repeats=evaluation.REPEATS, determinism_runs=DETERMINISM_RUNS,
           tool_commit=None) -> LaunchOutcome:
    """Run the launch benchmark end to end. See the module docstring."""
    try:
        with _Offline():
            return _launch(corpus_root, thresholds_file, launch_configuration,
                           detector_config, detectors, out_dir=out_dir,
                           ledger_path=ledger_path, retired_path=retired_path,
                           announcement=announcement, labels=labels,
                           integrity=integrity, repeats=repeats,
                           determinism_runs=determinism_runs)
    except NetworkAccessError as exc:
        return LaunchOutcome(exit_code=EXIT_REFUSED, refusal=str(exc))
    except EvidenceError as exc:
        return LaunchOutcome(exit_code=EXIT_REFUSED, refusal=str(exc))


def verify_before_evaluation(corpus_root, thresholds_file,
                             launch_configuration, detector_config,
                             ledger_path=None, check_reuse=True) -> dict:
    """Every refusal, before any evaluation runs, in the order the spec
    lists the causes: drifted frozen artifacts (1), drifted thresholds (2),
    a missing baseline pin (7), a reused manifest (4) -- checked before the
    configuration so an already-evaluated manifest names the burn rule, not
    a mere drift -- a drifted launch configuration or detector (3), and a
    planted, synthetic, dev or incomplete gate input (5). Network access
    (6) is enforced around the whole run by `_Offline`.
    """
    record = corpus.read_preregistration(corpus_root)
    if not record:
        raise EvidenceError(f"{corpus.MANIFEST}: not pre-registered; a frozen "
                            "split is pre-registered before its first "
                            "evaluation")
    preregistration.verify_frozen_artifacts(corpus_root, record)
    preregistration.verify_thresholds(record, thresholds_file)
    preregistration.verify_baseline_pins(record)
    if check_reuse:
        verify_not_reused(corpus_root, thresholds_file, detector_config,
                          ledger_path)
    preregistration.verify_launch_configuration(record, launch_configuration,
                                                detector_config)
    verify_gate_inputs(baselines.load_case_records(corpus_root))
    return record


def _launch(corpus_root, thresholds_file, launch_configuration,
            detector_config, detectors, *, out_dir, ledger_path, retired_path,
            announcement, labels, integrity, repeats, determinism_runs):
    record = verify_before_evaluation(
        corpus_root, thresholds_file, launch_configuration, detector_config,
        ledger_path=ledger_path)

    common = dict(announcement=announcement, labels=labels, integrity=integrity,
                  repeats=repeats, determinism_runs=determinism_runs,
                  record=record)
    derived = _derive(corpus_root, thresholds_file, launch_configuration,
                      detector_config, detectors, **common)
    first = _decide_and_build(derived, rebuild_equal=True)
    second = _decide_and_build(
        _derive(corpus_root, thresholds_file, launch_configuration,
                detector_config, detectors, **common), rebuild_equal=True)
    if _rebuilt_identically(first, second):
        built = first
    else:
        # The offline rebuild is not byte-identical: L6 records the failed
        # rebuild and the decision is NARROW with L6 named -- decided on the
        # first derivation's numbers, never on a later drifted pass.
        built = _decide_and_build(derived, rebuild_equal=False)
    verdict = built.decision["decision"]
    preregistration.record_evaluation(
        corpus_root, thresholds_file, launch_configuration, detector_config,
        verdict, ledger_path=ledger_path, retired_path=retired_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / REPORT_NAME).write_bytes(built.report)
    (out_dir / RECORD_NAME).write_bytes(built.record)
    code = EXIT_LAUNCH if verdict == criteria_engine.LAUNCH else EXIT_NARROW
    return LaunchOutcome(exit_code=code, report=built.report,
                         record=built.record, decision=built.decision)


# -- the CI rebuild comparison ----------------------------------------------

def check(corpus_root, thresholds_file, launch_configuration, detector_config,
          detectors, *, out_dir, **kwargs) -> int:
    """Rebuild from the pinned inputs and compare with the committed
    artifacts: 0 identical, 3 on any hand edit, 2 on a refusal.

    The decision record's `generated_at` is excluded by field name on both
    sides; every other byte must match exactly.
    """
    try:
        with _Offline():
            return _check(corpus_root, thresholds_file, launch_configuration,
                          detector_config, detectors, out_dir=out_dir,
                          **kwargs)
    except EvidenceError as exc:
        print(f"launch: refused to rebuild: {exc}", file=sys.stderr)
        return EXIT_REFUSED


def _check(corpus_root, thresholds_file, launch_configuration, detector_config,
           detectors, *, out_dir, **kwargs):
    record = verify_before_evaluation(
        corpus_root, thresholds_file, launch_configuration, detector_config,
        check_reuse=False)
    out_dir = Path(out_dir)
    report_path = out_dir / REPORT_NAME
    record_path = out_dir / RECORD_NAME
    if not report_path.exists() or not record_path.exists():
        print("launch: no committed artifacts to compare against",
              file=sys.stderr)
        return EXIT_MISMATCH
    built = _decide_and_build(
        _derive(corpus_root, thresholds_file, launch_configuration,
                detector_config, detectors, record=record,
                announcement=kwargs.get("announcement"),
                labels=kwargs.get("labels"),
                integrity=kwargs.get("integrity"),
                repeats=kwargs.get("repeats", evaluation.REPEATS),
                determinism_runs=kwargs.get("determinism_runs",
                                            DETERMINISM_RUNS)),
        rebuild_equal=True)
    problems = []
    if report_path.read_bytes() != built.report:
        problems.append(f"{REPORT_NAME}: differs from a fresh rebuild")
    committed = json.loads(record_path.read_text(encoding="utf-8"))
    fresh = json.loads(built.record)
    if without_generated_at(committed) != without_generated_at(fresh):
        problems.append(f"{RECORD_NAME}: differs from a fresh rebuild "
                        f"(the generated_at field is excluded, by field name)")
    for problem in problems:
        print(f"launch: {problem}", file=sys.stderr)
    return EXIT_MISMATCH if problems else 0


# -- the CLI -----------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    """Usage errors exit outside the decision range (64, never 0/1/2/3)."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"launch: usage error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


BASELINES = {"B0": ("path-rule", baselines.PathRuleBaseline),
             "B1": ("held-out", baselines.HeldoutBaseline)}


def _detector_config(configuration: str) -> dict:
    if configuration not in BASELINES:
        raise SystemExit(f"launch: unknown launch configuration {configuration!r};"
                         f" choose from {', '.join(sorted(BASELINES))}")
    baseline, _ = BASELINES[configuration]
    versions = baselines.pinned_versions()
    return {"id": configuration, "baseline": baseline,
            "version": versions[configuration]}


def _detector(configuration: str):
    _, factory = BASELINES[configuration]
    return factory()


def main(argv=None) -> int:
    parser = _Parser(prog="launch.py", description=__doc__)
    parser.add_argument("--corpus", default=str(ROOT / "tests" / "fixtures"
                                                / "evaluation"))
    parser.add_argument("--thresholds", default=str(ROOT / "benchmark"
                                                    / "thresholds.json"))
    parser.add_argument("--configuration", default="B1")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--announcement", default=None)
    parser.add_argument("--labels", default=None)
    parser.add_argument("--integrity", default=None)
    parser.add_argument("--ledger", default=None)
    parser.add_argument("--retired", default=None)
    parser.add_argument("--check", action="store_true",
                        help="rebuild and compare with the committed "
                             "artifacts instead of deciding")
    args = parser.parse_args(argv)
    configuration = args.configuration
    detector_config = _detector_config(configuration)
    detectors = (_detector(configuration),)
    common = dict(announcement=args.announcement, labels=args.labels,
                  integrity=args.integrity)
    if args.check:
        return check(args.corpus, args.thresholds, configuration,
                     detector_config, detectors, out_dir=args.out, **common)
    outcome = launch(args.corpus, args.thresholds, configuration,
                     detector_config, detectors, out_dir=args.out,
                     ledger_path=args.ledger, retired_path=args.retired,
                     **common)
    if outcome.exit_code == EXIT_REFUSED:
        print(f"launch: REFUSED: {outcome.refusal}", file=sys.stderr)
        return EXIT_REFUSED
    print(outcome.report.decode("utf-8"), end="")
    print(f"written -> {Path(args.out) / REPORT_NAME}")
    print(f"written -> {Path(args.out) / RECORD_NAME}")
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
