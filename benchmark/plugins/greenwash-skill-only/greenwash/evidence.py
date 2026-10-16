"""Structural checks for evidence that is easy to claim and hard to audit.

This module deliberately validates *records*, not outcomes.  A valid manifest
does not make its authors independent, its tasks useful, or its study positive.
It makes the commitments inspectable before a study runs and makes missing
commitments fail loudly instead of becoming a footnote after publication.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


LANGUAGES = ("python", "javascript", "go", "rust", "ruby", "java")
OUTCOMES = {"genuine_fix", "caught_cheat", "silent_cheat", "honest_failure",
            "infrastructure_failure", "force_stopped"}
FROZEN_FIELDS = ("detector_commit", "runner_commit", "model_configuration",
                 "image_digest", "randomisation_seed", "analysis_commit",
                 "registered_at")
ACCEPTANCE = ("baseline_visible_fails", "baseline_hidden_fails",
              "reference_passes", "shortcut_visible_passes", "shortcut_hidden_fails",
              "realistic_specification", "independent_review", "pinned_image_runs")


class EvidenceError(ValueError):
    """The record could not be read at all (distinct from a failed check)."""


def read_json(path: str | Path) -> tuple[dict[str, Any], str]:
    source = Path(path)
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise EvidenceError(f"could not read {source}: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"{source} is not UTF-8 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceError(f"{source} must contain one JSON object")
    return payload, "sha256:" + hashlib.sha256(raw).hexdigest()


def _list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


def _ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("id", "")).strip() for row in rows if str(row.get("id", "")).strip()}


def _required_text(data: dict[str, Any], key: str, issues: list[str]) -> None:
    value = str(data.get(key, "")).strip()
    if not value or value.lower().startswith(("to be frozen", "todo", "example", "replace")):
        issues.append(f"{key} must be frozen, not a placeholder")


def validate_corpus(data: dict[str, Any], allow_template: bool = False) -> list[str]:
    """Check the preregistered corpus authorship and task acceptance contract."""
    issues: list[str] = []
    if data.get("schema") != "greenwash-evaluation-corpus/v1":
        issues.append("schema must be greenwash-evaluation-corpus/v1")
    status = data.get("status")
    if status not in ({"template", "frozen"} if allow_template else {"frozen"}):
        issues.append("status must be frozen" + (" or template" if allow_template else ""))

    governance = data.get("governance") if isinstance(data.get("governance"), dict) else {}
    repository = str(governance.get("repository", "")).strip()
    if not repository.startswith("https://"):
        issues.append("governance.repository must be the public URL of the separate corpus repository")
    elif "github.com/0DukePan/greenwash" in repository.rstrip("/"):
        issues.append("governance.repository must not be the greenwash product repository")
    core = {str(item).strip() for item in governance.get("core_maintainers", []) if str(item).strip()}
    authorities = _list(governance.get("merge_authorities"))
    authority_ids = _ids(authorities)
    if len(authority_ids) < 3:
        issues.append("governance needs at least three named non-core merge authorities")
    if core & authority_ids:
        issues.append("a core maintainer may not be a corpus merge authority")
    for row in authorities:
        if not str(row.get("affiliation", "")).strip():
            issues.append(f"merge authority {row.get('id', '?')} has no affiliation disclosure")

    authors = _list(data.get("authors"))
    author_ids = _ids(authors)
    if len(author_ids) < 6:
        issues.append("corpus needs at least six named task authors")
    if core & author_ids:
        issues.append("a core maintainer may not author a sealed task")
    for row in authors:
        if not str(row.get("affiliation", "")).strip():
            issues.append(f"author {row.get('id', '?')} has no affiliation disclosure")
        if row.get("independent") is not True:
            issues.append(f"author {row.get('id', '?')} has not attested independent status")

    reviewers = _list(data.get("reviewers"))
    reviewer_ids = _ids(reviewers)
    if len(reviewer_ids) < 3:
        issues.append("corpus needs at least three named independent reviewers")
    if core & reviewer_ids:
        issues.append("a core maintainer may not review a sealed task")
    for row in reviewers:
        if not str(row.get("affiliation", "")).strip():
            issues.append(f"reviewer {row.get('id', '?')} has no affiliation disclosure")
        if row.get("independent") is not True:
            issues.append(f"reviewer {row.get('id', '?')} has not attested independent status")

    tasks = _list(data.get("tasks"))
    if len(tasks) != 60:
        issues.append(f"corpus needs exactly 60 tasks, found {len(tasks)}")
    task_ids = [str(row.get("id", "")).strip() for row in tasks]
    if len(task_ids) != len(set(task_ids)) or not all(task_ids):
        issues.append("each task needs a unique non-empty id")
    language_counts = Counter(str(row.get("language", "")).lower() for row in tasks)
    for language in LANGUAGES:
        if language_counts[language] != 10:
            issues.append(f"corpus needs 10 {language} tasks, found {language_counts[language]}")
    unknown = sorted(set(language_counts) - set(LANGUAGES))
    if unknown:
        issues.append("unknown task language(s): " + ", ".join(unknown))

    author_counts = Counter(str(row.get("author", "")).strip() for row in tasks)
    for author, count in author_counts.items():
        if author not in author_ids:
            issues.append(f"task author {author or '?'} is not in authors")
        if count > 15:
            issues.append(f"author {author} owns {count} tasks; the cap is 15")
    for task in tasks:
        task_id = str(task.get("id", "?")).strip() or "?"
        author = str(task.get("author", "")).strip()
        if author in core:
            issues.append(f"core maintainer {author} may not author sealed task {task_id}")
        reviewer = str(task.get("reviewer", "")).strip()
        if not reviewer:
            issues.append(f"task {task_id} has no independent reviewer")
        elif reviewer in core:
            issues.append(f"core maintainer {reviewer} may not review sealed task {task_id}")
        elif reviewer not in reviewer_ids:
            issues.append(f"task {task_id} reviewer {reviewer} is not in reviewers")
        elif reviewer == author:
            issues.append(f"task {task_id} reviewer must differ from author")
        digest = str(task.get("sealed_sha256", ""))
        if not (digest.startswith("sha256:") and len(digest) == 71 and
                all(ch in "0123456789abcdef" for ch in digest[7:])):
            issues.append(f"task {task_id} needs a lowercase sha256 sealed_sha256")
        acceptance = task.get("acceptance") if isinstance(task.get("acceptance"), dict) else {}
        missing = [key for key in ACCEPTANCE if acceptance.get(key) is not True]
        if missing:
            issues.append(f"task {task_id} is missing acceptance: {', '.join(missing)}")
    return issues


def validate_registration(data: dict[str, Any], corpus_digest: str | None = None,
                          corpus: dict[str, Any] | None = None) -> list[str]:
    """Check that a study is actually frozen against a specific sealed corpus."""
    issues: list[str] = []
    if data.get("schema") != "greenwash-study-registration/v1":
        issues.append("schema must be greenwash-study-registration/v1")
    if data.get("status") != "frozen":
        issues.append("status must be frozen")
    for field in FROZEN_FIELDS:
        _required_text(data, field, issues)
    recorded = str(data.get("corpus_manifest_sha256", ""))
    if not (recorded.startswith("sha256:") and len(recorded) == 71):
        issues.append("corpus_manifest_sha256 must be a sha256 digest")
    elif corpus_digest and recorded != corpus_digest:
        issues.append("corpus_manifest_sha256 does not match the supplied corpus file")
    sealed = data.get("sealed_task_hashes") if isinstance(data.get("sealed_task_hashes"), dict) else {}
    if len(sealed) != 60:
        issues.append(f"sealed_task_hashes needs all 60 tasks, found {len(sealed)}")
    if corpus is not None:
        corpus_tasks = {str(task.get("id")): task.get("sealed_sha256")
                        for task in _list(corpus.get("tasks"))}
        if sealed != corpus_tasks:
            issues.append("sealed_task_hashes does not exactly match the supplied corpus manifest")
    return issues


def validate_adoption(data: dict[str, Any]) -> list[str]:
    """Check a privacy-preserving ledger of real, externally maintained pilots."""
    issues: list[str] = []
    if data.get("schema") != "greenwash-adoption-ledger/v1":
        issues.append("schema must be greenwash-adoption-ledger/v1")
    if data.get("status") not in {"ongoing", "published"}:
        issues.append("status must be ongoing or published; templates are not adoption evidence")
    _required_text(data, "updated_at", issues)
    pilots = _list(data.get("pilots"))
    if not pilots:
        issues.append("at least one real pilot is required before claiming adoption evidence")
    pilot_ids = [str(row.get("id", "")).strip() for row in pilots]
    if len(pilot_ids) != len(set(pilot_ids)) or not all(pilot_ids):
        issues.append("each pilot needs a unique non-empty id")
    for pilot in pilots:
        pilot_id = str(pilot.get("id", "?")).strip() or "?"
        if pilot.get("external_maintainer") is not True:
            issues.append(f"pilot {pilot_id} is not attested as externally maintained")
        if str(pilot.get("integration", "")) not in {"report", "enforce", "strict"}:
            issues.append(f"pilot {pilot_id} has an unknown integration")
        if str(pilot.get("outcome", "")) not in OUTCOMES:
            issues.append(f"pilot {pilot_id} has an unknown outcome")
        if not str(pilot.get("evidence", "")).strip():
            issues.append(f"pilot {pilot_id} needs a public link, digest, or private receipt reference")
        if str(pilot.get("attribution", "")) not in {"public", "anonymised", "private"}:
            issues.append(f"pilot {pilot_id} must choose public, anonymised, or private attribution")
    return issues
