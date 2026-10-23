"""The corpus kit: case records, task-level splits, and the frozen manifest.

A case record carries source, technique, label, split, task and repository
identity, and license. Splits are enforced by task identity, so a task in
development can never appear in the frozen set. The frozen manifest is
hash-recorded and verified on load: a tampered case file fails with the file
and the failed hash named. Synthetic injected tampers live in a separate
class and are excluded from gate inputs by construction. Every validation
error names the offending field, and technique goes through the taxonomy's
`validate_technique`, so a corpus cannot cite a technique the detector never
heard of.

This is the seam the evaluation runner will call: load a corpus, take its
gate inputs, generate the double-labeling packets. It deliberately grows no
CLI surface.
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import corpus, taxonomy  # noqa: E402
from greenwash.evidence import EvidenceError  # noqa: E402


def record(**overrides):
    row = {
        "id": "case-1",
        "source": "independent: published cheat-survey, table 3",
        "technique": "expected-value-change",
        "label": "tampered",
        "split": "dev",
        "task": "task-1",
        "repository": "https://example.org/org/project",
        "license": "MIT",
    }
    row.update(overrides)
    return row


def corpus_dir(tmp_path, *rows):
    for row in rows:
        (tmp_path / f"{row['id']}.json").write_text(
            json.dumps(row, indent=2) + "\n", encoding="utf-8")
    return tmp_path


# -- a case record validates field by field -----------------------------------

def test_a_complete_record_validates_clean():
    assert corpus.validate_case(record()) == []


@pytest.mark.parametrize("field", ["id", "source", "task", "repository", "license"])
def test_a_missing_field_is_named(field):
    issues = corpus.validate_case(record(**{field: ""}))
    assert issues and issues[0].startswith(f"{field}:"), issues
    assert "missing" in issues[0], issues


def test_technique_is_validated_by_the_taxonomy():
    row = record(technique="made-up-technique")
    issues = corpus.validate_case(row)
    assert issues == taxonomy.validate_technique(row), (
        "validate_case must delegate to the merged taxonomy")
    assert issues[0].startswith("technique:"), issues
    assert f"taxonomy v{taxonomy.TAXONOMY_VERSION}" in issues[0], issues


@pytest.mark.parametrize("field,value", [("label", "cheat"),
                                         ("split", "holdout"),
                                         ("origin", "planted")])
def test_an_unknown_enumerated_value_is_named(field, value):
    issues = corpus.validate_case(record(**{field: value}))
    assert issues and issues[0].startswith(f"{field}:"), (field, issues)


def test_an_absent_origin_is_natural_and_a_record_still_validates():
    row = record()
    assert corpus.validate_case(row) == []
    assert corpus.case_from_record(row).origin == "natural"


# -- splits are enforced by task identity ------------------------------------

def test_a_task_in_both_dev_and_frozen_splits_is_rejected():
    rows = [record(split="dev"), record(id="case-2", split="frozen")]
    issues = corpus.validate_cases(rows)
    offenders = [issue for issue in issues if issue.startswith("task:")]
    assert offenders, issues
    assert "task-1" in offenders[0], issues


def test_two_cases_of_one_task_stay_in_one_split():
    rows = [record(split="frozen"),
            record(id="case-2", split="frozen", label="clean")]
    assert corpus.validate_cases(rows) == []


def test_two_records_may_not_share_an_id():
    issues = corpus.validate_cases([record(), record()])
    assert any(issue.startswith("id:") for issue in issues), issues


# -- the frozen manifest is hash-recorded and verified on load ----------------

def test_the_manifest_round_trips(tmp_path):
    corpus_dir(tmp_path, record(split="frozen"),
               record(id="case-2", split="dev", label="clean", task="task-2"))
    written = corpus.write_manifest(tmp_path)
    assert set(written) == {"case-1.json"}, written
    assert corpus.read_manifest(tmp_path) == written
    assert json.loads((tmp_path / "FROZEN.json").read_text(
        encoding="utf-8")) == written
    assert [case.id for case in corpus.load_corpus(tmp_path)] == ["case-1", "case-2"]


def test_a_tampered_case_file_fails_the_hash_check(tmp_path):
    corpus_dir(tmp_path, record(split="frozen"))
    manifest = corpus.write_manifest(tmp_path)
    path = tmp_path / "case-1.json"
    row = json.loads(path.read_text(encoding="utf-8"))
    row["label"] = "clean"                      # the silent edit a gate must catch
    path.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(EvidenceError) as excinfo:
        corpus.load_corpus(tmp_path)
    message = str(excinfo.value)
    assert "case-1.json" in message, message
    assert manifest["case-1.json"] in message, message


def test_a_frozen_case_without_a_manifest_refuses_to_load(tmp_path):
    corpus_dir(tmp_path, record(split="frozen"))
    with pytest.raises(EvidenceError) as excinfo:
        corpus.load_corpus(tmp_path)
    assert "case-1.json" in str(excinfo.value), excinfo.value


def test_a_dev_corpus_needs_no_manifest(tmp_path):
    corpus_dir(tmp_path, record())
    assert [case.id for case in corpus.load_corpus(tmp_path)] == ["case-1"]


def test_invalid_records_refuse_to_load_naming_the_file_and_field(tmp_path):
    corpus_dir(tmp_path, record(label="cheat"))
    with pytest.raises(EvidenceError) as excinfo:
        corpus.load_corpus(tmp_path)
    message = str(excinfo.value)
    assert "case-1.json" in message, message
    assert "label:" in message, message


# -- synthetic tampers are loadable but never gate inputs --------------------

def test_synthetic_records_load_but_never_count_toward_a_gate(tmp_path):
    corpus_dir(tmp_path, record(split="frozen"),
               record(id="case-2", split="frozen", origin="synthetic"))
    corpus.write_manifest(tmp_path)
    cases = corpus.load_corpus(tmp_path)
    assert {case.id for case in cases} == {"case-1", "case-2"}
    assert {case.id for case in corpus.gate_cases(cases)} == {"case-1"}
    assert {case.id for case in corpus.gate_cases(
        cases, split="frozen")} == {"case-1"}


def test_a_synthetic_case_cannot_gate_no_matter_who_builds_it():
    case = corpus.SyntheticCase(**{**record(origin="synthetic")})
    assert case.gated is False
    assert corpus.gate_cases([case]) == ()
    assert corpus.case_from_record(
        record(origin="synthetic")) is not None
    assert isinstance(corpus.case_from_record(
        record(origin="synthetic")), corpus.SyntheticCase)


# -- double-labeling inputs for blind annotation -----------------------------

def test_double_label_inputs_hide_the_gold_fields():
    rows = [record(split="frozen"),
            record(id="case-2", split="frozen", label="clean",
                   origin="synthetic")]
    cases = [corpus.case_from_record(row) for row in rows]
    packets, key = corpus.double_label_inputs(cases)
    assert [packet["packet"] for packet in packets] == ["P1", "P2"]
    for packet in packets:
        for hidden in ("id", "label", "technique", "origin", "split"):
            assert hidden not in packet, packet
    assert key["P1"] == {"id": "case-1", "label": "tampered",
                         "technique": "expected-value-change",
                         "origin": "natural", "split": "frozen"}
    assert key["P2"]["id"] == "case-2"
    assert key["P2"]["label"] == "clean"


def test_double_label_inputs_are_reproducible():
    cases = [corpus.case_from_record(record())]
    assert corpus.double_label_inputs(cases) == corpus.double_label_inputs(cases)
