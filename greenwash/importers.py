"""The importers: outside sources turned into unadjudicated case records.

R3, R4 and R5 are the collection routes that import material produced outside
this repository: local agent runs on impossible tasks, public dataset entries,
and public agent pull requests. Each import path takes a fixture source on
local disk -- nothing is ever fetched from the network, in code or in tests --
and produces case records that validate against the corpus kit and stay
*unadjudicated*: no `labels` block is written, so `Case.adjudicated` is None
until the label workflow (a separate ticket) adjudicates.

Fail closed, by name, everywhere. A missing license decision, a license
decision that does not permit the use, an unknown technique, an R4 entry
without an executable suite, an R3 entry that tries to name its own label,
and -- for a replay-needing technique -- an absent replay record are all
refusals via `greenwash.evidence.EvidenceError`, naming the offending field
and the entry, never a default.

The seam, all callable without a CLI:

    records = import_local_runs(source)          # R3, labels by construction
    records = import_dataset_entries(source)     # R4, suite + license gated
    records = import_pull_requests(source)       # R5, metadata and diff only
    decisions = read_license_decisions(path)     # the recorded license checks

`source` is a directory of one-JSON-per-entry fixture files (plus diff files
for R5). `license_decisions` is a mapping of `LicenseDecision`, or the path to
a recorded decisions file, and defaults to `LICENSES.json` inside the source;
a source without one is refused by name.

The three routes, each with its own honesty rule:

* **R3, local agent runs on impossible tasks.** Labels by construction: on a
  task that cannot be passed, any pass is an exploit, so a passing run imports
  as `tampered` and a failing one as `clean`. An R3 entry records `outcome`,
  never a label of its own. The technique still needs review, so the record
  stays unadjudicated.
* **R4, public dataset entries.** Admitted only when the task carries an
  executable test suite (`suite`) and the entry's license has a recorded
  decision that permits the use. An entry without a suite is refused by name.
* **R5, public agent pull requests.** Metadata and the diff only, never an
  interaction with the repository: the diff is a fixture file inside the
  source, hashed into the record's `diff_hash` with its `diff_path` recorded.
  Imported only where the recorded license decision permits the use.

Every record carries its `route`, `source` (`category: detail`: the route's
category plus the outside source's own description, so a record can never
claim a provenance category it did not come through), `license`, the taxonomy
`technique` (checked by `greenwash.taxonomy.validate_technique`, so a record
cannot cite a technique the detector never heard of), the base and head refs
and the diff hash -- the provenance every published cell is traced by.

Imports land in the `dev` split. The frozen split is built last, hash-locked,
from repositories never used before; it is never an import's default.

This module extends the corpus kit rather than restating it: validation and
the case-record contract come from `greenwash.corpus`, the error type from
`greenwash.evidence`, technique validation from `greenwash.taxonomy`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from greenwash.corpus import (CLEAN, DEV, TAMPERED, read_repo_files,
                              validate_case, validate_cases)
from greenwash.evidence import EvidenceError, read_json
from greenwash.taxonomy import BY_ID

R3 = "R3"
R4 = "R4"
R5 = "R5"

#: The provenance category each route imports under (`category: detail`).
CATEGORIES = {R3: "local-run", R4: "dataset", R5: "public-pr"}

#: R3 labels by construction: on an impossible task a pass is an exploit.
OUTCOMES = {"pass": TAMPERED, "fail": CLEAN}

#: Where the recorded license decisions live inside a source, by default.
LICENSES = "LICENSES.json"


@dataclass(frozen=True)
class LicenseDecision:
    """One recorded license check: the license, the decision, and its record.

    `checked` is who checked the license and when -- a decision nobody
    recorded is not a decision, and `permits` is the outcome of that check.
    The importers never infer a license or default a decision: a source
    without a recorded decision is refused.
    """

    name: str
    permits: bool
    checked: str


def read_license_decisions(path: str | Path) -> dict:
    """The recorded license checks in one decisions file, keyed by license.

    The file is `{"decisions": [{"license": ..., "permits": true|false,
    "checked": ...}, ...]}`. A decision that does not record its license, its
    boolean `permits`, or its `checked` provenance is refused naming the
    field: a license check that cannot be recorded is not silently accepted.
    """
    path = Path(path)
    payload, _ = read_json(path)
    rows = payload.get("decisions")
    if not isinstance(rows, list):
        raise EvidenceError(f"{path.name}: 'decisions' must be a list of "
                            "recorded license checks")
    out: dict = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise EvidenceError(f"{path.name}: {row!r} is not a recorded "
                                "license decision; each one is a mapping of "
                                "license, permits and checked")
        name = str(row.get("license") or "").strip()
        permits = row.get("permits")
        checked = str(row.get("checked") or "").strip()
        issues: list = []
        if not name:
            issues.append("license: missing; a recorded license decision "
                          "names the license it checked")
        if not isinstance(permits, bool):
            issues.append("permits: missing or not true/false; a recorded "
                          "license decision says whether the license permits "
                          "the use")
        if not checked:
            issues.append("checked: missing; a recorded license decision "
                          "records who checked the license and when")
        if issues:
            raise EvidenceError(f"{path.name}: " + "; ".join(issues))
        out[name] = LicenseDecision(name=name, permits=permits, checked=checked)
    return out


def import_local_runs(source: str | Path, license_decisions=None) -> tuple:
    """R3: local agent runs on impossible tasks, labels by construction.

    Any pass on an impossible task is an exploit, so the run's `outcome`
    fixes the gold label (`pass` is `tampered`, `fail` is `clean`) and an
    entry that names a label of its own is refused. The technique still needs
    review, so every record is imported unadjudicated.
    """
    return _import(R3, source, license_decisions)


def import_dataset_entries(source: str | Path, license_decisions=None) -> tuple:
    """R4: public dataset entries, admitted only with a suite and a license.

    The task must carry an executable test suite (`suite`) and the entry's
    license must have a recorded decision that permits the use; an entry
    without a suite is refused by name, and a source without a recorded
    license decision is refused, never defaulted.
    """
    return _import(R4, source, license_decisions)


def import_pull_requests(source: str | Path, license_decisions=None) -> tuple:
    """R5: public agent pull request metadata and diffs, license permitting.

    Metadata and the diff only -- the importer never interacts with the pull
    request's repository and reads nothing from the network. The diff is a
    fixture file inside the source, hashed into the record's `diff_hash`;
    imported only where the recorded license decision permits the use.
    """
    return _import(R5, source, license_decisions)


# -- one import: entries in, unadjudicated records out -------------------------

def _decisions(source: Path, license_decisions):
    if license_decisions is None:
        return read_license_decisions(source / LICENSES)
    if isinstance(license_decisions, Mapping):
        return dict(license_decisions)
    return read_license_decisions(license_decisions)


def _import(route: str, source: str | Path, license_decisions) -> tuple:
    """Every entry in one fixture source, as one unadjudicated record each."""
    source = Path(source)
    decisions = _decisions(source, license_decisions)
    category = CATEGORIES[route]
    records: list = []
    for path in sorted(source.glob("*.json")):
        if path.name == LICENSES:
            continue
        entry, _ = read_json(path)
        name = str(entry.get("id") or "").strip() or path.stem
        record, issues = _record(route, category, entry, source, decisions)
        if issues:
            raise EvidenceError(f"{name}: " + "; ".join(issues))
        records.append(record)
    issues = validate_cases(records)
    if issues:
        raise EvidenceError("; ".join(issues))
    return tuple(records)


def _entry_text(entry, field: str, issues: list) -> str:
    value = str(entry.get(field) or "").strip()
    if not value:
        issues.append(f"{field}: missing; an imported record carries {field}")
    return value


def _record(route, category, entry, source, decisions):
    """One entry as a record, and every way it is refused -- by name."""
    issues: list = []
    detail = _entry_text(entry, "source", issues)
    case_id = _entry_text(entry, "id", issues)
    task = _entry_text(entry, "task", issues)
    repository = _entry_text(entry, "repository", issues)
    license_name = _entry_text(entry, "license", issues)
    base_ref = _entry_text(entry, "base_ref", issues)
    head_ref = _entry_text(entry, "head_ref", issues)
    if license_name:
        issues.extend(_license_issues(license_name, decisions))
    issues.extend(_replay_issues(entry))
    label = str(entry.get("label") or "").strip()
    diff_hash = str(entry.get("diff_hash") or "").strip()
    diff_path = entry.get("diff_path")
    replay = entry.get("replay")
    record = {
        "id": case_id,
        "source": f"{category}: {detail}",
        "technique": entry.get("technique") or "",
        "label": "",
        "split": DEV,
        "task": task,
        "repository": repository,
        "license": license_name,
        "route": route,
        "base_ref": base_ref or None,
        "head_ref": head_ref or None,
    }
    if route == R3:
        if label:
            issues.append("label: an R3 entry names no label; the label is "
                          "by construction from the run outcome -- a pass on "
                          "an impossible task is an exploit")
        outcome = str(entry.get("outcome") or "").strip()
        if not outcome:
            issues.append("outcome: missing; an R3 run records pass or fail, "
                          "and a pass on an impossible task is an exploit by "
                          "construction")
        elif outcome not in OUTCOMES:
            issues.append(f"outcome: unknown value {outcome!r}; an R3 run "
                          f"records pass or fail, and a pass on an impossible "
                          f"task is an exploit by construction")
        else:
            record["label"] = OUTCOMES[outcome]
        record["outcome"] = outcome
    else:
        record["label"] = label
        if route == R4:
            suite = str(entry.get("suite") or "").strip()
            if not suite:
                issues.append("suite: missing; an R4 entry is admitted only "
                              "when the task has an executable test suite, "
                              "never by default")
            record["suite"] = suite
        else:
            if not str(diff_path or "").strip():
                issues.append("diff_path: missing; an R5 entry imports the "
                              "pull request diff as a fixture file")
            else:
                record["diff_path"] = diff_path
                try:
                    files = read_repo_files(source, [diff_path])
                except EvidenceError as exc:
                    issues.append(str(exc))
                else:
                    expected = files[str(diff_path).replace("\\", "/")]["sha256"]
                    if diff_hash and diff_hash != expected:
                        issues.append(f"diff_hash: {diff_hash!r} does not hash "
                                      f"the imported diff; expected {expected}")
                    record["diff_hash"] = expected
    if route != R5:
        if not diff_hash:
            issues.append("diff_hash: missing; an imported record carries "
                          "the diff hash")
        else:
            record["diff_hash"] = diff_hash
    if replay is not None:
        record["replay"] = replay
    issues.extend(validate_case(record))
    return record, issues


def _license_issues(name: str, decisions) -> list:
    decision = decisions.get(name)
    if decision is None:
        return [f"license: no recorded license decision for {name!r}; a source "
                "without a recorded license decision is refused, never "
                "defaulted"]
    if not decision.permits:
        return [f"license: the recorded decision for {name!r} does not permit "
                f"the use (checked {decision.checked!r}); the entry is "
                f"refused"]
    return []


def _replay_issues(entry) -> list:
    """Presence only: a replay-needing technique carries a replay record."""
    if entry.get("replay") is not None:
        return []
    technique = BY_ID.get(str(entry.get("technique") or ""))
    if technique is None or not technique.replay:
        return []
    return ["replay: missing; catching this technique needs replay, so the "
            "record must carry a recorded, hashed replay result or a sandbox "
            "reference"]
