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

import hashlib
import json
import os
import subprocess
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


# -- gate inputs: a class admits only real, adjudicated cases ----------------

def gate_record(**overrides):
    """A real, adjudicated case from the frozen split: what a gate may count."""
    row = {
        "id": "gate-1",
        "source": "independent: published cheat-survey, table 3",
        "technique": "expected-value-change",
        "label": "tampered",
        "split": "frozen",
        "task": "gate-task-1",
        "repository": "https://example.org/org/real-project",
        "license": "MIT",
    }
    row.update(overrides)
    return row


def test_a_real_frozen_case_is_a_gate_input():
    gate_class = corpus.GateInputClass("positives", [gate_record()])
    assert gate_class.name == "positives"
    assert [case.id for case in gate_class.cases] == ["gate-1"]


@pytest.mark.parametrize("field,overrides", [
    ("source", {"source": "planted: benchmark task, a planted cheat"}),
    ("origin", {"origin": "synthetic"}),
    ("source", {"source": "synthetic: taxonomy-injected always-equal"}),
    ("split", {"split": "dev"}),
])
def test_a_planted_synthetic_or_dev_record_is_rejected_naming_the_field(
        field, overrides):
    with pytest.raises(EvidenceError) as excinfo:
        corpus.GateInputClass("positives", [gate_record(**overrides)])
    assert f"{field}:" in str(excinfo.value), excinfo.value


@pytest.mark.parametrize("field", ["source", "repository", "license",
                                   "technique", "split"])
def test_a_gate_input_missing_a_required_field_is_rejected_naming_the_field(
        field):
    with pytest.raises(EvidenceError) as excinfo:
        corpus.GateInputClass("positives", [gate_record(**{field: ""})])
    message = str(excinfo.value)
    assert f"{field}:" in message and "missing" in message, message


def test_a_class_holds_at_most_five_cases_per_repository():
    # The documented cap rule is rejection, never silent capping: a class
    # over the cap is refused naming the repository, so the corpus author
    # decides which cases stay rather than the kit dropping evidence.
    rows = [gate_record(id=f"gate-{n}", task=f"gate-task-{n}")
            for n in range(5)]
    assert len(corpus.GateInputClass("positives", rows).cases) == 5
    rows.append(gate_record(id="gate-6", task="gate-task-6"))
    with pytest.raises(EvidenceError) as excinfo:
        corpus.GateInputClass("positives", rows)
    message = str(excinfo.value)
    assert "repository:" in message and "real-project" in message, message
    assert "cap" in message, message


def test_the_cap_counts_per_repository_per_class():
    rows = [gate_record(id=f"gate-{n}", task=f"gate-task-{n}")
            for n in range(5)]
    rows += [gate_record(id=f"gate-b-{n}", task=f"gate-task-b-{n}",
                         repository="https://example.org/org/other-project")
             for n in range(5)]
    gate_class = corpus.GateInputClass("positives", rows)
    assert len(gate_class.cases) == 10
    assert gate_class.counts_by_repository == {
        "https://example.org/org/other-project": 5,
        "https://example.org/org/real-project": 5,
    }


def test_kept_out_of_the_class_the_gate_numbers_are_identical():
    honest = [gate_record(),
              gate_record(id="gate-2", task="gate-task-2", label="clean",
                          technique="skip-or-xfail")]
    contaminants = [
        gate_record(id="planted-1", task="gate-task-3",
                    source="planted: benchmark task, a planted cheat"),
        gate_record(id="synth-1", task="gate-task-4", origin="synthetic"),
        gate_record(id="dev-1", task="gate-task-5", split="dev"),
    ]
    plain = corpus.GateInputClass("positives", honest)
    cases = [corpus.case_from_record(row) for row in honest + contaminants]
    kept_out = corpus.GateInputClass(
        "positives", corpus.gate_cases(cases, split="frozen"))
    assert [case.id for case in kept_out.cases] == \
        [case.id for case in plain.cases]
    assert [case.label for case in kept_out.cases] == \
        [case.label for case in plain.cases]


# -- the builder treats repository content as untrusted ----------------------
#
# T18's seam: hostile fixture repositories must create no canary file, touch
# nothing outside the work tree, and be rejected.

SENTINEL = "outside content that must never change"
CANARY = "CANARY.txt"
WIDGET = b"def test_ok():\n    assert True\n"


def build_spec(**overrides):
    spec = {
        "id": "built-1",
        "source": "independent: published cheat-survey, table 3",
        "technique": "skip-or-xfail",       # catching it needs no replay
        "label": "tampered",
        "split": "frozen",
        "task": "built-task-1",
        "repository": "https://example.org/org/real-project",
        "license": "MIT",
        "files": ["tests/test_widget.py"],
    }
    spec.update(overrides)
    return spec


def hostile_repo(tmp_path):
    """A fixture repository beside an `outside` directory and a canary path.

    The canary sits outside the work tree: it would appear the moment any
    repository-supplied hook, filter or git configuration were honored, or
    any path escaped the work tree.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel.txt").write_text(SENTINEL, encoding="utf-8")
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_widget.py").write_bytes(WIDGET)
    return repo


def assert_untouched_outside(tmp_path):
    assert not (tmp_path / CANARY).exists(), "the canary was created"
    outside = tmp_path / "outside"
    assert (outside / "sentinel.txt").read_text(encoding="utf-8") == SENTINEL, \
        "a file outside the work tree was modified"
    assert sorted(path.name for path in outside.iterdir()) == \
        ["secret.txt", "sentinel.txt"], "something outside the work tree changed"


def plant_execution_sink(tmp_path, repo):
    """Executable hooks, hostile git configuration and a filter driver.

    Each one writes the canary the moment it is honored -- by a hook run, a
    fsmonitor invocation, a smudge or clean filter, or any git alias.
    """
    canary = tmp_path / CANARY
    sink = repo / "sink.bat"
    sink.write_text(f"@echo off\ntype nul > \"{canary}\"\n", encoding="utf-8")
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True)
    for name in ("pre-commit", "post-checkout", "pre-applypatch"):
        hook = hooks / name
        hook.write_text(f"#!/bin/sh\ntouch \"{canary}\"\n", encoding="utf-8")
        hook.chmod(0o755)
    (repo / ".git" / "config").write_text(
        "[core]\n"
        f"\thooksPath = {hooks}\n"
        f"\tfsmonitor = {sink}\n"
        "[filter \"evil\"]\n"
        f"\tsmudge = {sink}\n"
        f"\tclean = {sink}\n"
        "[alias]\n"
        f"\tstatus = {sink}\n",
        encoding="utf-8")
    (repo / ".gitattributes").write_text(
        "* filter=evil\n", encoding="utf-8")


def make_dir_link(target, link):
    """A directory symlink, or a junction where symlinks need a privilege."""
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError:                             # pragma: no cover - Windows
        import _winapi
        _winapi.CreateJunction(str(target), str(link))


def test_the_builder_reads_repository_content_as_data(tmp_path):
    repo = hostile_repo(tmp_path)
    record = corpus.record_from_repo(repo, build_spec())
    assert record["files"] == {
        "tests/test_widget.py": {"sha256": hashlib.sha256(WIDGET).hexdigest(),
                                 "size": len(WIDGET)}}
    assert record["id"] == "built-1"
    assert_untouched_outside(tmp_path)


def test_the_builder_never_executes_anything(tmp_path, monkeypatch):
    repo = hostile_repo(tmp_path)
    plant_execution_sink(tmp_path, repo)

    def boom(*args, **kwargs):
        raise AssertionError("the builder executed repository-supplied content")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(os, "system", boom)
    monkeypatch.setattr(os, "execv", boom)
    record = corpus.record_from_repo(repo, build_spec())
    assert record["id"] == "built-1"
    assert_untouched_outside(tmp_path)


def test_repository_hooks_are_never_executed(tmp_path):
    repo = hostile_repo(tmp_path)
    plant_execution_sink(tmp_path, repo)
    record = corpus.record_from_repo(repo, build_spec())
    assert record["id"] == "built-1"
    assert_untouched_outside(tmp_path)


def test_repository_supplied_git_configuration_is_ignored(tmp_path):
    repo = hostile_repo(tmp_path)
    plant_execution_sink(tmp_path, repo)
    assert ".git" in (repo / ".git" / "config").read_text(encoding="utf-8")
    record = corpus.record_from_repo(repo, build_spec())
    assert record["id"] == "built-1"
    assert_untouched_outside(tmp_path)


def test_hooks_and_git_configuration_are_not_case_content(tmp_path):
    repo = hostile_repo(tmp_path)
    plant_execution_sink(tmp_path, repo)
    for hostile in (".git/hooks/pre-commit", ".git/config"):
        with pytest.raises(EvidenceError) as excinfo:
            corpus.record_from_repo(repo, build_spec(files=[hostile]))
        assert "files:" in str(excinfo.value), (hostile, excinfo.value)
    assert_untouched_outside(tmp_path)


def test_a_path_that_escapes_the_work_tree_is_rejected(tmp_path):
    repo = hostile_repo(tmp_path)
    with pytest.raises(EvidenceError) as excinfo:
        corpus.record_from_repo(
            repo, build_spec(files=["../outside/sentinel.txt"]))
    message = str(excinfo.value)
    assert "files:" in message and "escapes" in message, message
    assert "outside/sentinel.txt" in message, message
    assert_untouched_outside(tmp_path)


@pytest.mark.parametrize("path", ["/etc/passwd", "C:\\Windows\\win.ini",
                                  "\\\\server\\share\\x"])
def test_an_absolute_path_is_rejected(tmp_path, path):
    repo = hostile_repo(tmp_path)
    with pytest.raises(EvidenceError) as excinfo:
        corpus.record_from_repo(repo, build_spec(files=[path]))
    message = str(excinfo.value)
    assert "files:" in message and "absolute" in message, message
    assert_untouched_outside(tmp_path)


@pytest.mark.parametrize("path", ["tests/\x01evil.py", "tests/evil\n.py",
                                  "tests/\x7f.py"])
def test_control_characters_in_a_filename_are_rejected(tmp_path, path):
    repo = hostile_repo(tmp_path)
    with pytest.raises(EvidenceError) as excinfo:
        corpus.record_from_repo(repo, build_spec(files=[path]))
    message = str(excinfo.value)
    assert "files:" in message and "control characters" in message, message
    assert_untouched_outside(tmp_path)


def test_a_symlink_escape_out_of_the_work_tree_is_rejected(tmp_path):
    repo = hostile_repo(tmp_path)
    outside = tmp_path / "outside"
    make_dir_link(outside, repo / "link")
    paths = ["link/secret.txt"]
    file_link = "file-link.txt"
    try:
        os.symlink(outside / "secret.txt", repo / file_link)
    except OSError:
        # A file symlink needs a privilege some Windows machines do not grant;
        # the directory link above exercises the same escape, and the paths
        # below still must reject.
        file_link = None
    if file_link:
        paths.append(file_link)
    for path in paths:
        with pytest.raises(EvidenceError) as excinfo:
            corpus.record_from_repo(repo, build_spec(files=[path]))
        message = str(excinfo.value)
        assert "files:" in message and path in message, message
    assert_untouched_outside(tmp_path)


def test_an_oversized_file_is_rejected(tmp_path):
    repo = hostile_repo(tmp_path)
    (repo / "big.bin").write_bytes(b"x" * (corpus.MAX_FILE_BYTES + 1))
    with pytest.raises(EvidenceError) as excinfo:
        corpus.record_from_repo(repo, build_spec(files=["big.bin"]))
    message = str(excinfo.value)
    assert "files:" in message and "big.bin" in message and "above" in message
    assert_untouched_outside(tmp_path)


def test_too_many_case_files_are_rejected(tmp_path):
    repo = hostile_repo(tmp_path)
    paths = [f"f{n}.txt" for n in range(corpus.MAX_FILES + 1)]
    with pytest.raises(EvidenceError) as excinfo:
        corpus.record_from_repo(repo, build_spec(files=paths))
    message = str(excinfo.value)
    assert "files:" in message and "above" in message, message
    assert_untouched_outside(tmp_path)


# -- replay: recorded and hashed, never run by the builder -------------------

def replay_spec(**overrides):
    spec = build_spec(technique="expected-value-change",   # catching it needs replay
                      files=[])
    spec.update(overrides)
    return spec


def recorded_replay(result="12 passed, 0 failed (the pinned original run)"):
    return {"result": result,
            "sha256": hashlib.sha256(result.encode("utf-8")).hexdigest()}


def test_a_replay_case_carries_a_recorded_hashed_replay_result(tmp_path):
    repo = hostile_repo(tmp_path)
    record = corpus.record_from_repo(repo, replay_spec(replay=recorded_replay()))
    assert record["replay"] == recorded_replay()


def test_a_replay_case_without_a_recorded_result_is_rejected_naming_the_field(
        tmp_path):
    repo = hostile_repo(tmp_path)
    with pytest.raises(EvidenceError) as excinfo:
        corpus.record_from_repo(repo, replay_spec())
    message = str(excinfo.value)
    assert "replay:" in message and "missing" in message, message


def test_a_replay_result_that_does_not_match_its_hash_is_rejected(tmp_path):
    repo = hostile_repo(tmp_path)
    for replay in ({"result": "12 passed", "sha256": "0" * 64},
                   {"result": "12 passed", "sha256": recorded_replay("other")["sha256"]},
                   {"sha256": recorded_replay()["sha256"]}):
        with pytest.raises(EvidenceError) as excinfo:
            corpus.record_from_repo(repo, replay_spec(replay=replay))
        message = str(excinfo.value)
        assert "replay:" in message, (replay, message)


def test_a_case_needing_no_replay_needs_no_recorded_result(tmp_path):
    repo = hostile_repo(tmp_path)
    record = corpus.record_from_repo(repo, build_spec())
    assert record["id"] == "built-1"
    assert "replay" not in record
