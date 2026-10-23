"""The corpus kit: case records, task-level splits, and the frozen manifest.

A corpus case is a record, not a verdict. Each one carries its source, the
technique it exercises, its gold label, its split, its task and repository
identity, and its license -- enough for an evaluation to be audited after the
fact and for every published cell to be traced back to the cases that made it.

The contracts, each one load-bearing:

* **Splits by task identity.** A task lives in exactly one split. A task with
  cases in both `dev` and `frozen` is rejected with the offending field named,
  so no task used during development can ever be scored in the frozen set.
* **The frozen manifest.** `FROZEN.json` hash-records the frozen split's case
  files (the pattern the impossible-task corpus froze with) and is verified on
  load: a tampered case file fails with the file and the failed hash named,
  and a frozen case the manifest does not hash-record refuses to load.
* **Pre-registration lives inside the manifest.** The pre-registration record
  is stored under the reserved `preregistration` key of the same file, written
  once by `write_preregistration` (a second write is refused), and read by
  `read_preregistration`. `manifest_sha256` is the hash of the canonical
  case-file mapping -- the manifest's identity -- so embedding the record does
  not change it.
* **Retired repositories cannot be re-frozen.** Every repository an evaluation
  touches is added to a retired registry (`retire_repositories`), and
  `write_manifest` refuses to freeze any split that reuses one, naming the
  repository.
* **Synthetic tampers are a separate class.** A tamper injected from the
  detector's own taxonomy is loadable and reportable like any case, but
  `SyntheticCase.gated` is False by construction -- no field in the record can
  flip it back -- so injected tampers never flatter a gate.
* **Gate inputs are admitted by class.** `GateInputClass` admits only real,
  adjudicated cases: a planted, synthetic or dev-split record is refused with
  the field named, source, repository identity, license, technique and split
  must all be present, and a class holds at most `GATE_MAX_PER_REPOSITORY`
  cases per repository (rejection, never silent capping).
* **The builder treats repository content as untrusted.** `read_repo_files`
  and `record_from_repo` read file bytes and hash them and do nothing else:
  no repository code, hook or filter runs, no repository-supplied git
  configuration is honored (no git runs at all), paths that escape the work
  tree are rejected, and file sizes and counts are bounded. A case needing
  replay carries a recorded, hashed replay result; live replay belongs to the
  integrity-checked sandbox, never to this builder.
* **Validation names the field.** Every issue starts with the offending
  field, and `technique` is checked by the taxonomy's `validate_technique`,
  so a case cannot cite a technique the detector never heard of.

The runner's seam, all callable without a CLI:

    cases = load_corpus(root)                     # manifest verified first
    gate_inputs = gate_cases(cases, split="frozen")
    gate_class = GateInputClass("positives", gate_inputs)
    record = record_from_repo(work_tree, spec)    # untrusted-input safe
    packets, key = double_label_inputs(cases)     # blind double annotation

This module extends the evidence kit rather than restating it: `read_json`
and `EvidenceError` come from `greenwash.evidence`, technique validation from
`greenwash.taxonomy`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from greenwash.evidence import EvidenceError, read_json
from greenwash.taxonomy import BY_ID, validate_technique

DEV = "dev"
FROZEN = "frozen"
SPLITS = (DEV, FROZEN)

TAMPERED = "tampered"
CLEAN = "clean"
LABELS = (TAMPERED, CLEAN)

NATURAL = "natural"
SYNTHETIC = "synthetic"
ORIGINS = (NATURAL, SYNTHETIC)

# The source category a record names before its first colon (`category: detail`
# is the corpus convention). `planted` and `synthetic` name by-construction
# material: loadable and reportable, never gate inputs.
PLANTED = "planted"
NON_GATE_SOURCES = (PLANTED, SYNTHETIC)

GATE_REQUIRED = ("source", "repository", "license", "technique", "split")
GATE_MAX_PER_REPOSITORY = 5

MAX_FILE_BYTES = 1_048_576          # one MiB per case file
MAX_FILES = 100                     # case files per record

MANIFEST = "FROZEN.json"

# The manifest's reserved key: the pre-registration record, stored inside the
# frozen manifest itself. A case file is named `<something>.json`, so the bare
# key can never collide with one.
PREREGISTRATION = "preregistration"

# Where the retired-repository registry lives, relative to the project that
# ships this kit. Callers may pass their own path everywhere.
RETIRED_REGISTRY = "benchmark/retired-repositories.json"

FIELDS = ("id", "source", "technique", "label", "split", "task", "repository",
          "license", "origin")
REQUIRED = ("id", "source", "task", "repository", "license")
# What the gold label turns on. A blind annotator must not see these; the key
# keeps them with the orchestrator until both annotations are in.
GOLD_FIELDS = ("id", "label", "technique", "origin", "split")


@dataclass(frozen=True)
class Case:
    """One corpus case: what it is, where it came from, and what it labels.

    `gated` is the seam gates read. It is a property, never a field, so the
    decision cannot be edited out of a record at load time.
    """

    id: str
    source: str
    technique: str
    label: str
    split: str
    task: str
    repository: str
    license: str
    origin: str = NATURAL

    @property
    def gated(self) -> bool:
        return True


@dataclass(frozen=True)
class SyntheticCase(Case):
    """A tamper injected from the detector's own taxonomy, not observed.

    Loadable and reportable like any case, and excluded from gate inputs by
    construction: `gated` is False on the class itself, so nothing in a
    record -- and no argument a caller passes -- can make an injected tamper
    count toward a gate.
    """

    @property
    def gated(self) -> bool:
        return False


# -- validating one record, naming the offending field -----------------------

def _required(record: Mapping, field: str, issues: list) -> None:
    if not str(record.get(field, "")).strip():
        issues.append(f"{field}: missing; a case record must carry {field}")


def _choice(record: Mapping, field: str, allowed: tuple, issues: list) -> None:
    value = record.get(field)
    if value is None or not str(value).strip():
        issues.append(f"{field}: missing; must be one of {', '.join(allowed)}")
    elif value not in allowed:
        issues.append(f"{field}: unknown value {value!r}; must be one of "
                      f"{', '.join(allowed)}")


def validate_case(record: Mapping) -> list:
    """Every way one case record is wrong, each naming the offending field.

    The technique check is the taxonomy's own `validate_technique`, verbatim,
    so a corpus record and a coverage row can never disagree about what
    techniques exist.
    """
    issues: list = []
    for field in REQUIRED:
        _required(record, field, issues)
    issues.extend(validate_technique(record, "technique"))
    _choice(record, "label", LABELS, issues)
    _choice(record, "split", SPLITS, issues)
    origin = record.get("origin", NATURAL)
    if origin not in ORIGINS:
        issues.append(f"origin: unknown value {origin!r}; must be one of "
                      f"{', '.join(ORIGINS)}")
    return issues


def _corpus_issues(records: list) -> list:
    """The corpus-wide contract: one split per task, one record per id."""
    issues: list = []
    seen: set = set()
    for record in records:
        case_id = str(record.get("id", "")).strip()
        if not case_id:
            continue
        if case_id in seen:
            issues.append(f"id: duplicate case id {case_id!r}")
        seen.add(case_id)
    splits_by_task: dict = {}
    for record in records:
        task = str(record.get("task", "")).strip()
        if task and record.get("split") in SPLITS:
            splits_by_task.setdefault(task, set()).add(record.get("split"))
    for task in sorted(splits_by_task):
        if len(splits_by_task[task]) > 1:
            issues.append(f"task: {task!r} has cases in both the {DEV} and "
                          f"{FROZEN} splits; a task lives in exactly one split")
    return issues


def validate_cases(records: Iterable[Mapping]) -> list:
    """One record each, then the corpus-wide contract.

    The corpus-wide half is the split rule and nothing else: a task lives in
    exactly one split -- a task with cases in both dev and frozen is rejected
    with `task` named -- and a case id identifies exactly one record.
    """
    records = list(records)
    issues = [issue for record in records for issue in validate_case(record)]
    issues.extend(_corpus_issues(records))
    return issues


def case_from_record(record: Mapping) -> Case:
    """A validated record as a Case (or SyntheticCase, by its origin)."""
    issues = validate_case(record)
    if issues:
        raise EvidenceError("; ".join(issues))
    data = dict(record)
    data.setdefault("origin", NATURAL)
    case_type = SyntheticCase if data["origin"] == SYNTHETIC else Case
    return case_type(**{field: data[field] for field in FIELDS})


def gate_cases(cases: Iterable[Case], split: str | None = None) -> tuple:
    """The records a gate may count.

    Synthetic injected tampers are excluded by construction (their class
    reports `gated` False), planted and synthetic source categories are
    excluded by their provenance -- both stay loadable and reportable as
    plumbing -- and `split` names the split a gate scores -- the frozen split,
    for any pre-registered gate.
    """
    return tuple(case for case in cases
                 if case.gated
                 and source_category(case) not in NON_GATE_SOURCES
                 and (split is None or case.split == split))


# -- gate inputs: only real, adjudicated cases decide a gate -----------------

def _field(entry, name):
    """One field of a record mapping or a Case, without prejudice."""
    if isinstance(entry, Mapping):
        return entry.get(name)
    return getattr(entry, name, None)


def _as_record(entry) -> dict:
    """One entry as a record mapping, whether it arrives as a record or a Case."""
    if isinstance(entry, Mapping):
        return dict(entry)
    return {field: getattr(entry, field, None) for field in FIELDS}


def source_category(entry) -> str:
    """The provenance category a source names before its first colon.

    The corpus convention is `category: detail` (`independent: ...`,
    `fixture: ...`, `synthetic: ...`). The categories `planted` and `synthetic`
    name material built from fixtures or the detector's own taxonomy: plumbing
    that may be reported, never gate inputs.
    """
    return str(_field(entry, "source") or "").split(":", 1)[0].strip().lower()


def gate_input_issues(entry) -> list:
    """Every way one record is not a gate input, each naming the field.

    A gate input is a real, adjudicated case and nothing else. Planted fixture
    cases and synthetic injected tampers are by-construction material reported
    as plumbing; a dev-split record is development material a frozen gate must
    never score (refusal 5 turns each of these into a refusal); and source,
    repository identity, license, technique and split must all be present so
    every published cell can be traced, licensed and attributed to its
    taxonomy row.
    """
    issues: list = []
    for field in GATE_REQUIRED:
        if not str(_field(entry, field) or "").strip():
            issues.append(f"{field}: missing; a gate input must carry {field}")
    category = source_category(entry)
    if category == PLANTED:
        issues.append("source: a planted fixture case; planted cases are "
                      "plumbing, never gate inputs")
    elif category == SYNTHETIC:
        issues.append("source: a synthetic injected tamper; synthetic cases "
                      "are plumbing, never gate inputs")
    if _field(entry, "origin") == SYNTHETIC:
        issues.append("origin: a synthetic injected tamper; synthetic cases "
                      "are plumbing, never gate inputs")
    if _field(entry, "split") == DEV:
        issues.append(f"split: a {DEV} record; gate inputs come from the "
                      f"{FROZEN} split")
    return issues


class GateInputClass:
    """One gate-input class: the cases whose results decide one gate's number.

    This is the admission point refusal 5 enforces. It admits only real,
    adjudicated cases: a record that is planted, synthetic, from the dev
    split, or missing source, repository identity, license, technique or
    split is refused with the offending field named.

    The per-repository cap rule is **rejection**, never silent capping: a
    class that would hold more than `GATE_MAX_PER_REPOSITORY` (5) cases from
    one repository is refused naming the repository, so the corpus author
    chooses which cases stay and the kit drops no evidence on its own. Cases
    from one repository are correlated; the cap keeps one busy repository
    from deciding a class by itself.
    """

    def __init__(self, name: str, records: Iterable) -> None:
        cases: list = []
        issues: list = []
        for entry in records:
            record = _as_record(entry)
            problems = validate_case(record) + gate_input_issues(record)
            if problems:
                case_id = str(_field(record, "id") or "?")
                issues.append(f"{case_id}: " + "; ".join(problems))
            else:
                cases.append(case_from_record(record))
        if issues:
            raise EvidenceError("; ".join(issues))
        counts: dict = {}
        for case in cases:
            counts[case.repository] = counts.get(case.repository, 0) + 1
        over = sorted((repo, n) for repo, n in counts.items()
                      if n > GATE_MAX_PER_REPOSITORY)
        if over:
            raise EvidenceError("; ".join(
                f"repository: {repo} contributes {n} cases to class {name!r}, "
                f"above the {GATE_MAX_PER_REPOSITORY}-case per-repository cap; "
                f"the class is rejected, never silently capped"
                for repo, n in over))
        self.name = name
        self.cases = tuple(cases)

    @property
    def ids(self) -> tuple:
        return tuple(case.id for case in self.cases)

    @property
    def counts_by_repository(self) -> dict:
        counts: dict = {}
        for case in self.cases:
            counts[case.repository] = counts.get(case.repository, 0) + 1
        return dict(sorted(counts.items()))


# -- the builder: repository content as untrusted input ----------------------

def _safe_path(work_tree: Path, rel: str) -> Path:
    """One repository-supplied path, checked before anything opens it.

    A path is data and this data is hostile. Rejected, each naming the field:
    an empty name; control characters; an absolute path; `.git` internals
    (hooks and repository configuration are never case content); a path that
    escapes the work tree via `..`; and any path that is, or travels through,
    a symlink -- whose resolution would land outside the work tree -- so case
    content is read as plain files and nothing outside the work tree is ever
    touched.
    """
    if not isinstance(rel, str) or not rel.strip():
        raise EvidenceError("files: missing; every case file must be named")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in rel):
        raise EvidenceError(f"files: {rel!r} contains control characters; "
                            "a case path is plain text")
    if PurePosixPath(rel).is_absolute() or PureWindowsPath(rel).is_absolute() \
            or PureWindowsPath(rel).drive:
        raise EvidenceError(f"files: {rel!r} is absolute; case paths are "
                            "relative to the work tree")
    parts = [part for part in rel.replace("\\", "/").split("/")
             if part not in ("", ".")]
    if not parts:
        raise EvidenceError("files: missing; every case file must be named")
    if parts[0].lower() == ".git":
        raise EvidenceError(f"files: {rel!r} is .git internals; hooks and "
                            "repository configuration are never case content")
    if ".." in parts:
        raise EvidenceError(f"files: {rel!r} escapes the work tree; case "
                            "paths stay inside it")
    root = work_tree.resolve()
    cursor = root
    for part in parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise EvidenceError(f"files: {rel!r} is or travels through a "
                                "symlink; case content is read as plain files "
                                "inside the work tree")
    candidate = root.joinpath(*parts)
    try:
        real = candidate.resolve()
    except OSError as exc:                      # pragma: no cover - exotic FS
        raise EvidenceError(f"files: {rel!r} cannot be resolved: {exc}") from exc
    if real != root and root not in real.parents:
        raise EvidenceError(f"files: {rel!r} resolves outside the work tree "
                            f"({real}); rejected")
    return candidate


def read_repo_files(work_tree: str | Path, rel_paths: Iterable[str]) -> dict:
    """Case files as data: digests and sizes, and nothing else.

    Plain file reads only. No subprocess and no import runs, so no repository
    code, hook or filter can execute and repository-supplied git configuration
    can never be honored -- no git is consulted at all. Every path passes
    `_safe_path` first, and file counts and sizes are bounded so a hostile
    repository cannot exhaust the builder.
    """
    work_tree = Path(work_tree)
    paths = list(rel_paths)
    if len(paths) > MAX_FILES:
        raise EvidenceError(f"files: {len(paths)} case files, above the "
                            f"{MAX_FILES}-file bound; a case is bounded input")
    out = {}
    for rel in paths:
        path = _safe_path(work_tree, rel)
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise EvidenceError(f"files: {rel}: {exc}") from exc
        if size > MAX_FILE_BYTES:
            raise EvidenceError(f"files: {rel} is {size} bytes, above the "
                                f"{MAX_FILE_BYTES}-byte bound; a case is "
                                "bounded input")
        try:
            raw = path.read_bytes()
        except OSError as exc:                  # pragma: no cover - exotic FS
            raise EvidenceError(f"files: {rel}: {exc}") from exc
        out[rel.replace("\\", "/")] = {"sha256": hashlib.sha256(raw).hexdigest(),
                                       "size": len(raw)}
    return out


def _replay_issues(record) -> list:
    """The replay contract: recorded and hashed, or refused.

    Catching some techniques needs the pinned original tests replayed. The
    builder never runs them -- repository content is untrusted, and live
    replay is the integrity-checked sandbox's job (no network, no secrets,
    resource limits) -- so a case whose technique needs replay must carry the
    replay outcome as a recorded, hashed result: `replay` with `result` and
    `sha256` over the result's UTF-8 bytes. A missing result or a hash that
    does not match it is refused naming the field.
    """
    technique = BY_ID.get(str(record.get("technique") or ""))
    if technique is None or not technique.replay:
        return []
    replay = record.get("replay")
    if not isinstance(replay, Mapping):
        return ["replay: missing; catching this technique needs replay, so "
                "the record must carry a recorded, hashed replay result"]
    result = replay.get("result")
    digest = replay.get("sha256")
    if not isinstance(result, str) or not result.strip():
        return ["replay: missing recorded result; a replay result is recorded "
                "and hashed before the case is built"]
    expected = hashlib.sha256(result.encode("utf-8")).hexdigest()
    if digest != expected:
        return [f"replay: sha256 {digest!r} does not hash the recorded result; "
                f"expected {expected}"]
    return []


def record_from_repo(work_tree: str | Path, spec: Mapping) -> dict:
    """One case record built from repository content, untrusted-input safe.

    The repository is hostile input and the builder reads it as data: file
    bytes, hashed, and nothing else. It never executes repository code,
    hooks or filters and never honors repository-supplied git configuration
    (no git runs), rejects paths that escape the work tree, and bounds file
    sizes and counts. A case whose technique needs replay carries a recorded,
    hashed replay result (see `_replay_issues`); replaying live belongs to
    the integrity-checked sandbox, never to this builder.
    """
    issues = validate_case(spec) + _replay_issues(spec)
    if issues:
        raise EvidenceError("; ".join(issues))
    data = dict(spec)
    data.setdefault("origin", NATURAL)
    record = {field: data[field] for field in FIELDS}
    record["files"] = read_repo_files(work_tree, spec.get("files") or [])
    if "replay" in spec:
        record["replay"] = spec["replay"]
    return record


# -- the frozen manifest -----------------------------------------------------

def _case_files(root: Path) -> list:
    """Every case file in the corpus root: top-level JSON, manifest aside."""
    return sorted(path for path in root.glob("*.json") if path.name != MANIFEST)


def _sha256(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise EvidenceError(f"could not read {path}: {exc}") from exc
    return hashlib.sha256(raw).hexdigest()


def write_manifest(root: str | Path, retired_registry=None) -> dict:
    """Hash-record the frozen split's case files into FROZEN.json.

    Freezing refuses to record a corpus it cannot validate, so the manifest
    can never bless a record with an unknown technique or a missing field.
    It also refuses to rewrite a manifest that is already pre-registered (the
    record is committed once) and to freeze any case from a retired
    repository, naming the repository and the registry.
    """
    root = Path(root)
    existing = read_manifest(root)
    if PREREGISTRATION in existing:
        raise EvidenceError(f"{MANIFEST}: already pre-registered; a frozen "
                            "manifest is pre-registered once and its record "
                            "cannot be rewritten")
    retired = read_retired_repositories(retired_registry)
    manifest = {}
    for path in _case_files(root):
        record, _ = read_json(path)
        try:
            case = case_from_record(record)
        except EvidenceError as exc:
            raise EvidenceError(f"{path.name}: {exc}") from exc
        if case.split == FROZEN:
            if case.repository in retired:
                raise EvidenceError(
                    f"{path.name}: repository {case.repository!r} is retired "
                    f"({retired_registry_path(retired_registry)}); a new "
                    f"frozen split may not reuse a repository an evaluation "
                    f"already consumed")
            manifest[path.relative_to(root).as_posix()] = _sha256(path)
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n",
                                 encoding="utf-8")
    return manifest


def read_manifest(root: str | Path) -> dict:
    """FROZEN.json as written, {} when the corpus is not frozen.

    The `preregistration` key is reserved for the pre-registration record and
    validated by `read_preregistration`; every other key must name a case file
    by a lowercase sha256 digest.
    """
    path = Path(root) / MANIFEST
    if not path.exists():
        return {}
    payload, _ = read_json(path)
    for name, digest in payload.items():
        if name == PREREGISTRATION:
            continue
        if not (isinstance(digest, str) and len(digest) == 64
                and all(ch in "0123456789abcdef" for ch in digest)):
            raise EvidenceError(f"{MANIFEST}: {name} is not a lowercase sha256 "
                                f"digest: {digest!r}")
    return payload


def manifest_sha256(root: str | Path) -> str:
    """The frozen manifest's identity: sha256 over its canonical case-file mapping.

    The mapping is serialized as compact JSON with sorted keys, never as the
    file's bytes, so the hash is stable across formatting and line-ending
    settings and is unchanged by embedding the pre-registration record.
    """
    root = Path(root)
    if not (root / MANIFEST).exists():
        raise EvidenceError(f"{MANIFEST}: no frozen manifest in {root}")
    cases = {name: digest for name, digest in read_manifest(root).items()
             if name != PREREGISTRATION}
    canonical = json.dumps(cases, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# -- the pre-registration record, stored inside the frozen manifest -----------

PREREGISTRATION_REQUIRED = ("thresholds_sha256", "launch_configuration",
                            "detector_sha256", "detector_version",
                            "baseline_pins", "taxonomy_version", "tool_commit",
                            "manifest_sha256")
PREREGISTRATION_DIGESTS = ("thresholds_sha256", "detector_sha256",
                           "manifest_sha256")


def validate_preregistration(record) -> list:
    """Every way the pre-registration record is incomplete, naming the field."""
    issues: list = []
    if not isinstance(record, dict):
        return ["preregistration: must be a JSON object of pinned fields"]
    for field in PREREGISTRATION_REQUIRED:
        if field == "baseline_pins":
            continue
        if not str(record.get(field, "")).strip():
            issues.append(f"preregistration: {field} is missing; the record "
                          f"must pin {field}")
    for field in PREREGISTRATION_DIGESTS:
        value = str(record.get(field, ""))
        if value and not (len(value) == 64
                          and all(ch in "0123456789abcdef" for ch in value)):
            issues.append(f"preregistration: {field} is not a lowercase sha256 "
                          f"digest: {value!r}")
    pins = record.get("baseline_pins")
    if not isinstance(pins, dict) or not pins:
        issues.append("preregistration: baseline_pins is missing; every "
                      "baseline version, including the competitor's, must be "
                      "pinned")
    return issues


def read_preregistration(root: str | Path) -> dict:
    """The pre-registration record inside FROZEN.json, {} when there is none."""
    record = read_manifest(root).get(PREREGISTRATION)
    if record is None:
        return {}
    issues = validate_preregistration(record)
    if issues:
        raise EvidenceError(f"{MANIFEST}: " + "; ".join(issues))
    return record


def write_preregistration(root: str | Path, record: Mapping) -> dict:
    """Store the pre-registration record inside FROZEN.json -- exactly once.

    The case-file hash records are preserved verbatim; only the reserved
    `preregistration` key is added. A manifest may be pre-registered once, so
    the commitment cannot be quietly replaced after the fact.
    """
    root = Path(root)
    manifest = read_manifest(root)
    if not manifest:
        raise EvidenceError(f"{MANIFEST}: no frozen manifest in {root} to "
                            "pre-register; freeze the split first")
    if PREREGISTRATION in manifest:
        raise EvidenceError(f"{MANIFEST}: already pre-registered; a frozen "
                            "manifest is pre-registered once")
    issues = validate_preregistration(record)
    if issues:
        raise EvidenceError("; ".join(issues))
    payload = {name: digest for name, digest in manifest.items()
               if name != PREREGISTRATION}
    payload[PREREGISTRATION] = dict(record)
    (root / MANIFEST).write_text(json.dumps(payload, indent=2) + "\n",
                                 encoding="utf-8")
    return dict(record)


def load_corpus(root: str | Path) -> tuple:
    """Every case record in `root`, with the frozen manifest verified first.

    Verification order is deliberate: the bytes are hashed before any of
    them is trusted as a record. A tampered case file fails naming the file
    and both hashes; a frozen case the manifest does not hash-record refuses
    to load; an invalid record names the file and the offending field.
    """
    root = Path(root)
    manifest = read_manifest(root)
    paths = _case_files(root)
    digests = {path.relative_to(root).as_posix(): _sha256(path) for path in paths}
    cases_recorded = {name: digest for name, digest in manifest.items()
                      if name != PREREGISTRATION}
    for name in sorted(cases_recorded):
        if name not in digests:
            raise EvidenceError(f"{MANIFEST} hash-records {name} but the "
                                "file is missing")
        if digests[name] != cases_recorded[name]:
            raise EvidenceError(f"{MANIFEST}: {name} hash mismatch: recorded "
                                f"{cases_recorded[name]}, found {digests[name]}")
    loaded = {}
    for path in paths:
        record, _ = read_json(path)
        loaded[path.relative_to(root).as_posix()] = record
    issues: list = []
    for name in sorted(loaded):
        issues.extend(f"{name}: {issue}" for issue in validate_case(loaded[name]))
    issues.extend(_corpus_issues(list(loaded.values())))
    if issues:
        raise EvidenceError("; ".join(issues))
    cases = tuple(case_from_record(record) for record in loaded.values())
    frozen_files = {name for name in sorted(loaded)
                    if loaded[name].get("split") == FROZEN}
    unrecorded = sorted(frozen_files - set(cases_recorded))
    mislabelled = sorted(set(cases_recorded) - frozen_files)
    if unrecorded or mislabelled:
        problems = [f"{MANIFEST} does not hash-record frozen case(s): "
                    f"{', '.join(unrecorded)}"] if unrecorded else []
        problems += [f"{MANIFEST} hash-records {name} but its split is not "
                     f"{FROZEN}" for name in mislabelled]
        raise EvidenceError("; ".join(problems))
    return cases


# -- the retired-repository registry -----------------------------------------

def retired_registry_path(path=None) -> Path:
    """The registry file: `path`, or the project's own by default."""
    return (Path(path) if path is not None
            else Path(__file__).resolve().parent.parent / RETIRED_REGISTRY)


def read_retired_repositories(path=None) -> tuple:
    """The retired repositories, sorted; () before any evaluation retires one.

    A repository is retired by being *evaluated*: the registry only grows, so
    a frozen split can never be rebuilt from a repository whose evidence is
    already spent.
    """
    registry = retired_registry_path(path)
    if not registry.exists():
        return ()
    payload, _ = read_json(registry)
    repositories = payload.get("repositories")
    if (not isinstance(repositories, list)
            or not all(isinstance(repo, str) and repo.strip()
                       for repo in repositories)):
        raise EvidenceError(f"{registry.name}: 'repositories' must be a list "
                            "of repository identities")
    return tuple(sorted(set(repositories)))


def retire_repositories(repositories: Iterable, path=None) -> tuple:
    """Add every repository to the retired registry and return the registry."""
    registry = retired_registry_path(path)
    merged = sorted(set(read_retired_repositories(path))
                    | {str(repo).strip() for repo in repositories
                       if str(repo).strip()})
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps({"repositories": merged}, indent=2) + "\n",
                        encoding="utf-8")
    return tuple(merged)


# -- double-labeling inputs for blind annotation -----------------------------

def double_label_inputs(cases: Iterable[Case]) -> tuple:
    """Blind annotation packets, and the key that stays with the orchestrator.

    Two annotators each label every packet without seeing the gold fields
    (id, label, technique, origin, split) or the case's identity, so a
    technique name cannot leak the label it implies. The key maps each
    packet back to the case and its gold fields, which is what a later
    agreement figure (raw agreement, kappa, PABAK) is computed against.

    Generation is deterministic: the same cases produce the same packets.
    """
    packets: list = []
    key: dict = {}
    for number, case in enumerate(cases, start=1):
        packet_id = f"P{number}"
        packet = {"packet": packet_id}
        packet.update({field: getattr(case, field) for field in FIELDS
                       if field not in GOLD_FIELDS})
        packets.append(packet)
        key[packet_id] = {field: getattr(case, field) for field in GOLD_FIELDS}
    return packets, key
