"""The external-evidence promises have executable acceptance criteria."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from greenwash import evidence


ROOT = Path(__file__).resolve().parent.parent


def digest(number: int) -> str:
    return "sha256:" + f"{number:064x}"


def corpus():
    authors = [{"id": f"author-{number}", "affiliation": f"independent-{number}",
                "independent": True} for number in range(6)]
    tasks = []
    for language_index, language in enumerate(evidence.LANGUAGES):
        for offset in range(10):
            number = language_index * 10 + offset
            tasks.append({
                "id": f"{language}-{offset + 1:02d}", "language": language,
                "author": authors[number % len(authors)]["id"],
                "reviewer": f"reviewer-{number % 3}",
                "sealed_sha256": digest(number),
                "acceptance": {key: True for key in evidence.ACCEPTANCE},
            })
    return {
        "schema": "greenwash-evaluation-corpus/v1", "status": "frozen",
        "governance": {
            "core_maintainers": ["core-maintainer"],
            "repository": "https://code.example.org/external/greenwash-evaluation",
            "merge_authorities": [
                {"id": "governor-a", "affiliation": "group-a"},
                {"id": "governor-b", "affiliation": "group-b"},
                {"id": "governor-c", "affiliation": "group-c"},
            ],
        },
        "authors": authors,
        "reviewers": [{"id": f"reviewer-{number}", "affiliation": f"review-group-{number}",
                       "independent": True} for number in range(3)],
        "tasks": tasks,
    }


def registration(manifest_digest: str, source: dict):
    return {
        "schema": "greenwash-study-registration/v1", "status": "frozen",
        "corpus_manifest_sha256": manifest_digest,
        "sealed_task_hashes": {task["id"]: task["sealed_sha256"] for task in source["tasks"]},
        "detector_commit": "a" * 40, "runner_commit": "b" * 40,
        "model_configuration": "provider/model, temperature 0",
        "image_digest": "sha256:" + "c" * 64, "randomisation_seed": "20260928",
        "analysis_commit": "d" * 40, "registered_at": "2026-09-28T00:00:00Z",
    }


def test_frozen_corpus_contract_accepts_a_complete_independent_shape():
    assert evidence.validate_corpus(corpus()) == []


def test_corpus_contract_rejects_core_authorship_and_unreviewed_tasks():
    data = corpus()
    data["tasks"][0]["author"] = "core-maintainer"
    data["tasks"][0]["reviewer"] = "core-maintainer"
    issues = evidence.validate_corpus(data)
    assert any("not in authors" in issue for issue in issues)
    assert any("may not review" in issue for issue in issues)


def test_registration_binds_exact_bytes_and_all_task_hashes(tmp_path):
    source = corpus()
    manifest = tmp_path / "corpus.json"
    manifest.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")
    _, manifest_digest = evidence.read_json(manifest)
    data = registration(manifest_digest, source)
    assert evidence.validate_registration(data, manifest_digest, source) == []
    data["sealed_task_hashes"].pop("python-01")
    issues = evidence.validate_registration(data, manifest_digest, source)
    assert any("60 tasks" in issue for issue in issues)
    assert any("does not exactly match" in issue for issue in issues)


def test_adoption_requires_a_real_external_receipt():
    data = {"schema": "greenwash-adoption-ledger/v1", "status": "ongoing",
            "updated_at": "2026-09-28T00:00:00Z", "pilots": []}
    issues = evidence.validate_adoption(data)
    assert any("real pilot" in issue for issue in issues)


def test_cli_emits_a_machine_readable_failed_evidence_check(tmp_path):
    record = tmp_path / "adoption.json"
    record.write_text(json.dumps({"schema": "greenwash-adoption-ledger/v1",
                                  "status": "ongoing", "updated_at": "2026-09-28",
                                  "pilots": []}), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "greenwash", "evidence", "adoption",
                             str(record), "--json"], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8")
    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["valid"] is False
    assert payload["sha256"] == "sha256:" + hashlib.sha256(record.read_bytes()).hexdigest()
