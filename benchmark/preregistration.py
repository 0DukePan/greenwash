#!/usr/bin/env python3
"""Pre-registration, the thresholds file, and the burn ledger.

One record commits the evaluation before it happens: the pre-registration
record is stored **inside the existing frozen manifest** and pins the
thresholds-file hash, the launch configuration id, the detector hash and
version, the pinned baseline versions (including the competitor), the taxonomy
version, the tool commit and the frozen manifest hash. The nine launch
criteria live in one versioned thresholds data file. Every evaluation appends
one hash-chained entry to an append-only ledger keyed on the manifest, detector
and thresholds hashes, and retires every repository the frozen split used.

The contracts, each one load-bearing:

* **Pre-registered once.** A frozen manifest carries at most one pre-registration
  record; `corpus.write_preregistration` refuses a second write, so the
  commitment cannot be quietly replaced after the numbers are in.
* **Refusals before evaluation.** Drifted frozen artifacts (refusal 1), a
  drifted thresholds file (refusal 2), a drifted launch configuration or
  detector (refusal 3) and a missing or unverifiable baseline pin are refused
  by name before any evaluation runs, and a refusal writes nothing: no ledger
  entry, no registry change.
* **The burn ledger cannot be rewritten.** Each entry chains to the previous
  one by hash (`verify_ledger` recomputes every link). The first evaluation of
  a manifest appends one entry; an identical rerun appends nothing and returns
  the recorded entry, so it is detectable as identical and reproduces the same
  decision and bytes; a rerun with a changed detector or thresholds hash is
  refusal 4 -- a fresh split is required, not a second try.
* **Evaluated repositories are retired.** `record_evaluation` adds every
  repository in the frozen manifest to the retired registry, and the corpus
  kit (`corpus.write_manifest`) rejects any new frozen split that reuses one.
* **Byte stability.** Ledger lines are compact sorted-key JSON with LF endings
  only, and the hashes are computed over canonical serializations, so two runs
  on two machines produce identical bytes.

The seam, all callable without a CLI (the launch command is a separate ticket):

    record = preregister(root, thresholds, "B1", detector_config)
    verify_preregistration(root, thresholds, "B1", detector_config)
    result = record_evaluation(root, thresholds, "B1", detector_config, "NARROW")

This module extends the corpus kit rather than restating it: the frozen
manifest and the retired registry come from `greenwash.corpus`, the pinned
baseline versions from `greenwash.baselines`, the taxonomy version from
`greenwash.taxonomy`.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash import baselines, corpus, gitutil, taxonomy  # noqa: E402
from greenwash.evidence import EvidenceError  # noqa: E402

# Where the two ledger-side artifacts live, relative to the project root.
# Callers may pass their own paths everywhere; tests always do.
THRESHOLDS = "benchmark/thresholds.json"
LEDGER = "benchmark/evaluation-ledger.jsonl"

# The hash chain's first link: entry 1 prevs this.
GENESIS = "0" * 64

# The launch criteria the thresholds file must name, in fixed order.
CRITERIA = tuple(f"L{number}" for number in range(1, 10))

BASELINE_NAMES = {"B0": "the path rule", "B1": "the held-out tests",
                  "B2": "the judge", "B3": "the competitor"}

# The ledger entry fields the chain covers (everything but the entry's own hash).
ENTRY_FIELDS = ("entry", "manifest_sha256", "detector_sha256",
                "thresholds_sha256", "decision", "prev")

# Re-exported seam: the retired registry the corpus kit enforces.
read_retired_repositories = corpus.read_retired_repositories


def ledger_file(path=None) -> Path:
    """The ledger file: `path`, or the project's own by default."""
    return Path(path) if path is not None else ROOT / LEDGER


# -- the thresholds file: one versioned data file naming L1-L9 ----------------

def load_thresholds(path) -> dict:
    """The thresholds file as data: a version, and L1-L9 each with a value.

    The file is the decision rule's single home, so a threshold change is a
    one-line diff -- and any change after pre-registration is refusal 2.
    """
    source = Path(path)
    try:
        payload = json.loads(source.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise EvidenceError(f"thresholds file {source}: could not be read as "
                            f"JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceError(f"thresholds file {source}: must be one JSON object")
    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        raise EvidenceError(f"thresholds file {source}: version is missing; "
                            "the file must name its version")
    criteria = payload.get("criteria")
    if not isinstance(criteria, dict):
        raise EvidenceError(f"thresholds file {source}: criteria are missing; "
                            "the file must name L1-L9")
    for name in CRITERIA:
        if name not in criteria:
            raise EvidenceError(f"thresholds file {source}: criterion {name} "
                                "is missing; the file must name L1-L9")
    for name in sorted(set(criteria) - set(CRITERIA)):
        raise EvidenceError(f"thresholds file {source}: criterion {name} is "
                            "not one of L1-L9")
    for name in CRITERIA:
        entry = criteria[name]
        if (not isinstance(entry, dict) or "value" not in entry
                or not str(entry.get("criterion", "")).strip()):
            raise EvidenceError(f"thresholds file {source}: criterion {name} "
                                "must carry its name and its value")
    return payload


def thresholds_sha256(path) -> str:
    """The thresholds-file hash exactly as the record pins it: the file bytes."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise EvidenceError(f"thresholds file {path}: could not be read: "
                            f"{exc}") from exc
    return hashlib.sha256(raw).hexdigest()


# -- the detector configuration ----------------------------------------------

def detector_sha256(config) -> str:
    """The detector hash: sha256 over the canonical configuration JSON.

    Canonical means compact separators and sorted keys, so the hash depends on
    the configuration's content and never on how it was pretty-printed.
    """
    if not isinstance(config, dict):
        raise EvidenceError("detector configuration: must be a JSON object")
    for field in ("id", "version"):
        if not str(config.get(field, "")).strip():
            raise EvidenceError(f"detector configuration: {field} is missing; "
                                f"the configuration must name {field}")
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# -- building and storing the pre-registration record -------------------------

def preregistration_record(corpus_root, thresholds_file, launch_configuration,
                           detector, tool_commit=None) -> dict:
    """The record the spec lists, every hash computed from its artifact.

    The thresholds file must load as L1-L9 data before its hash can be pinned:
    garbage cannot be pre-registered. The tool commit is the git HEAD unless a
    caller pins one.
    """
    load_thresholds(thresholds_file)
    launch = str(launch_configuration or "").strip()
    if not launch:
        raise EvidenceError("preregistration: launch configuration is "
                            "missing; exactly one configuration decides")
    commit = str(tool_commit or gitutil.head_commit() or "").strip()
    if not commit:
        raise EvidenceError("preregistration: tool commit could not be "
                            "established; pass tool_commit")
    return {
        "schema": 1,
        "thresholds_file": str(thresholds_file),
        "thresholds_sha256": thresholds_sha256(thresholds_file),
        "launch_configuration": launch,
        "detector_sha256": detector_sha256(detector),
        "detector_version": str(detector["version"]),
        "baseline_pins": dict(baselines.pinned_versions()),
        "taxonomy_version": taxonomy.TAXONOMY_VERSION,
        "tool_commit": commit,
        "manifest_sha256": corpus.manifest_sha256(corpus_root),
    }


def preregister(corpus_root, thresholds_file, launch_configuration, detector,
                tool_commit=None) -> dict:
    """Pre-register the frozen manifest, once, with every hash the spec lists."""
    record = preregistration_record(corpus_root, thresholds_file,
                                    launch_configuration, detector,
                                    tool_commit=tool_commit)
    return corpus.write_preregistration(corpus_root, record)


# -- the enforcement primitives: refusals 1-3 and the baseline-pin refusal ----

def verify_frozen_artifacts(corpus_root, record) -> str:
    """Refusal 1: every frozen artifact must hash-match the frozen manifest.

    The corpus kit does the hashing (`load_corpus` names the file and both
    hashes on any mismatch); the record's manifest hash is checked too, so a
    split that changed after pre-registration is refused, not re-scored.
    """
    corpus.load_corpus(corpus_root)
    found = corpus.manifest_sha256(corpus_root)
    pinned = str(record.get("manifest_sha256", ""))
    if found != pinned:
        raise EvidenceError(f"preregistration: frozen manifest hash mismatch: "
                            f"pre-registered {pinned}, found {found}")
    return found


def verify_thresholds(record, thresholds_file) -> str:
    """Refusal 2: the thresholds file must still hash to the registered one."""
    found = thresholds_sha256(thresholds_file)
    pinned = str(record.get("thresholds_sha256", ""))
    if found != pinned:
        raise EvidenceError(f"preregistration: thresholds file {thresholds_file} "
                            f"hash mismatch: pre-registered {pinned}, found "
                            f"{found}")
    return found


def verify_launch_configuration(record, launch_configuration, detector) -> None:
    """Refusal 3: the deciding cell and the detector must be the registered ones."""
    launch = str(launch_configuration or "").strip()
    registered = str(record.get("launch_configuration", ""))
    if launch != registered:
        raise EvidenceError(f"preregistration: launch configuration {launch!r} "
                            f"differs from the pre-registered {registered!r}")
    found = detector_sha256(detector)
    pinned = str(record.get("detector_sha256", ""))
    if found != pinned:
        raise EvidenceError(f"preregistration: detector hash mismatch: "
                            f"pre-registered {pinned}, found {found}")
    version = str(detector.get("version", ""))
    registered = str(record.get("detector_version", ""))
    if version != registered:
        raise EvidenceError(f"preregistration: detector version {version!r} "
                            f"differs from the pre-registered {registered!r}")


def verify_baseline_pins(record) -> dict:
    """The missing-baseline-pin refusal: every baseline pinned and verifiable.

    A pin is verifiable when it is the version the tool itself reports; the
    competitor is named first-class, because comparing against whatever
    happens to be installed is not a pinned baseline.
    """
    pins = record.get("baseline_pins")
    expected = baselines.pinned_versions()
    for baseline in sorted(expected):
        name = BASELINE_NAMES.get(baseline, baseline)
        pinned = pins.get(baseline) if isinstance(pins, dict) else None
        if not str(pinned or "").strip():
            raise EvidenceError(f"preregistration: baseline pin for {baseline} "
                                f"({name}) is missing; every baseline version, "
                                f"including the competitor's, must be pinned")
        if pinned != expected[baseline]:
            raise EvidenceError(f"preregistration: baseline pin for {baseline} "
                                f"({name}) is unverifiable: pinned {pinned!r}, "
                                f"the tool pins {expected[baseline]!r}")
    return dict(pins)


def verify_preregistration(corpus_root, thresholds_file, launch_configuration,
                           detector) -> dict:
    """Refusals 1-3 and the baseline-pin refusal, composed and ordered.

    Run this before any evaluation: it names what drifted and writes nothing.
    """
    record = corpus.read_preregistration(corpus_root)
    if not record:
        raise EvidenceError(f"{corpus.MANIFEST}: not pre-registered; a frozen "
                            "split is pre-registered before its first "
                            "evaluation")
    verify_frozen_artifacts(corpus_root, record)
    verify_thresholds(record, thresholds_file)
    verify_launch_configuration(record, launch_configuration, detector)
    verify_baseline_pins(record)
    return record


# -- the evaluation ledger: append-only, hash-chained -------------------------

@dataclass(frozen=True)
class Recording:
    """One ledger outcome: the entry the ledger holds, and whether it is new.

    An identical rerun returns the recorded entry with `appended` False, so
    the rerun is detectable as identical and reproduces the same decision and
    the same bytes.
    """

    entry: dict
    appended: bool

    def as_bytes(self) -> bytes:
        return entry_bytes(self.entry)


def entry_bytes(entry) -> bytes:
    """One ledger line: compact sorted-key JSON, LF-terminated, CR-free."""
    return (json.dumps(entry, sort_keys=True, separators=(",", ":"))
            + "\n").encode("utf-8")


def _entry_sha256(entry) -> str:
    body = {field: entry[field] for field in ENTRY_FIELDS}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_ledger(path) -> list:
    """The ledger as written: [] before the first evaluation."""
    path = Path(path)
    if not path.exists():
        return []
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise EvidenceError(f"evaluation ledger {path}: could not be read: "
                            f"{exc}") from exc
    entries = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        try:
            entry = json.loads(line)
        except ValueError as exc:
            raise EvidenceError(f"evaluation ledger: entry {number} is not "
                                f"JSON") from exc
        if not isinstance(entry, dict):
            raise EvidenceError(f"evaluation ledger: entry {number} is not "
                                "one JSON object")
        entries.append(entry)
    return entries


def verify_ledger(path) -> list:
    """The hash chain, recomputed link by link; a break names its entry.

    The ledger is tamper-evident through git history, not tamper-proof: this
    proves the file was not edited in place, and the chain is what an
    identical rerun is compared against.
    """
    path = Path(path)
    if path.exists():
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise EvidenceError(f"evaluation ledger {path}: could not be "
                                f"read: {exc}") from exc
        if b"\r" in raw:
            raise EvidenceError(f"evaluation ledger {path}: contains CR; the "
                                "ledger is LF-only and byte-stable")
    entries = read_ledger(path)
    prev = GENESIS
    for number, entry in enumerate(entries, start=1):
        for field in (*ENTRY_FIELDS, "sha256"):
            if field not in entry:
                raise EvidenceError(f"evaluation ledger: entry {number} is "
                                    f"missing {field}")
        if entry["entry"] != number:
            raise EvidenceError(f"evaluation ledger: entry {number} is "
                                f"numbered {entry['entry']}; entries are "
                                "appended in order")
        if entry["prev"] != prev:
            raise EvidenceError(f"evaluation ledger: entry {number} breaks "
                                f"the hash chain: prev is {entry['prev']}, "
                                f"expected {prev}")
        if entry["sha256"] != _entry_sha256(entry):
            raise EvidenceError(f"evaluation ledger: entry {number} hash "
                                f"mismatch: recorded {entry['sha256']}, "
                                f"recomputed {_entry_sha256(entry)}")
        prev = entry["sha256"]
    return entries


def record_evaluation(corpus_root, thresholds_file, launch_configuration,
                      detector, decision, ledger_path=None,
                      retired_path=None) -> Recording:
    """Record one evaluation in the burn ledger and retire its repositories.

    The ledger is keyed on the manifest, detector and thresholds hashes. The
    first evaluation of a manifest appends one entry. An identical rerun
    appends nothing and returns the recorded entry, refusing to record a
    decision that does not reproduce the recorded one. A rerun with a changed
    detector or thresholds hash is refusal 4: the manifest has already been
    evaluated, and a fresh split -- not a second try -- is what may be
    evaluated next. Refusals append nothing and retire nothing.
    """
    verdict = str(decision or "").strip()
    if not verdict:
        raise EvidenceError("evaluation ledger: an evaluation is recorded "
                            "with its decision")
    manifest_sha = corpus.manifest_sha256(corpus_root)
    thresholds_sha = thresholds_sha256(thresholds_file)
    detector_sha = detector_sha256(detector)
    path = ledger_file(ledger_path)
    entries = verify_ledger(path)
    prior = [entry for entry in entries
             if entry["manifest_sha256"] == manifest_sha]
    if prior:
        last = prior[-1]
        if last["detector_sha256"] != detector_sha:
            raise EvidenceError(
                f"evaluation ledger: manifest {manifest_sha} was already "
                f"evaluated with detector {last['detector_sha256']}, not "
                f"{detector_sha}; a fresh split is required")
        if last["thresholds_sha256"] != thresholds_sha:
            raise EvidenceError(
                f"evaluation ledger: manifest {manifest_sha} was already "
                f"evaluated with thresholds {last['thresholds_sha256']}, not "
                f"{thresholds_sha}; a fresh split is required")
        verify_preregistration(corpus_root, thresholds_file,
                               launch_configuration, detector)
        if last["decision"] != verdict:
            raise EvidenceError(
                f"evaluation ledger: an identical rerun must reproduce the "
                f"recorded decision {last['decision']!r}, not {verdict!r}")
        return Recording(entry=last, appended=False)
    verify_preregistration(corpus_root, thresholds_file, launch_configuration,
                           detector)
    entry = {"entry": len(entries) + 1,
             "manifest_sha256": manifest_sha,
             "detector_sha256": detector_sha,
             "thresholds_sha256": thresholds_sha,
             "decision": verdict,
             "prev": entries[-1]["sha256"] if entries else GENESIS,
             "sha256": ""}
    entry["sha256"] = _entry_sha256(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(entry_bytes(entry))
    repositories = {case.repository for case in corpus.load_corpus(corpus_root)
                    if case.split == corpus.FROZEN}
    corpus.retire_repositories(repositories, path=retired_path)
    return Recording(entry=entry, appended=True)


if __name__ == "__main__":  # pragma: no cover - library seam, no CLI
    raise SystemExit("preregistration.py is a library seam; the launch "
                     "command is a separate ticket")
