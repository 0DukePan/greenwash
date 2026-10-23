"""Pre-registration, the thresholds file, and the burn ledger.

A frozen manifest is pre-registered once: the record stored inside FROZEN.json
carries the thresholds-file hash, the launch configuration id, the detector
hash and version, the pinned baseline versions (including the competitor), the
taxonomy version, the tool commit and the frozen manifest hash. The nine
launch criteria live in one versioned thresholds data file. Every evaluation
appends one hash-chained entry to an append-only ledger keyed on the manifest,
detector and thresholds hashes; an identical rerun appends nothing and
reproduces the same decision and bytes, and a rerun with a changed detector is
refused. Every repository an evaluation touches is retired, and the corpus kit
rejects a new frozen split that reuses one. Drifted frozen artifacts, drifted
thresholds, a drifted launch configuration and a missing baseline pin are
refused before any evaluation, and a refusal writes no ledger entry.

This is the seam the launch command will call. It deliberately grows no CLI
surface.
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import preregistration  # noqa: E402
from greenwash import baselines, corpus, taxonomy  # noqa: E402
from greenwash.evidence import EvidenceError  # noqa: E402

THRESHOLDS = ROOT / "benchmark" / "thresholds.json"
GENESIS = "0" * 64


def record(**overrides):
    row = {
        "id": "case-1",
        "source": "independent: published cheat-survey, table 3",
        "technique": "expected-value-change",
        "label": "tampered",
        "split": "frozen",
        "task": "task-1",
        "repository": "https://example.org/org/project",
        "license": "MIT",
    }
    row.update(overrides)
    return row


def frozen_corpus(tmp_path, *rows, name="corpus"):
    root = tmp_path / name
    root.mkdir(exist_ok=True)
    for row in rows:
        (root / f"{row['id']}.json").write_text(
            json.dumps(row, indent=2) + "\n", encoding="utf-8")
    corpus.write_manifest(root)
    return root


def thresholds_copy(tmp_path):
    path = tmp_path / "thresholds.json"
    path.write_bytes(THRESHOLDS.read_bytes())
    return path


DETECTOR = {"id": "B1", "baseline": "held-out",
            "version": baselines.HeldoutBaseline.version}


def register(root, thresholds, detector=DETECTOR, launch="B1", commit="c0ffee"):
    return preregistration.preregister(
        root, thresholds, launch, detector, tool_commit=commit)


def recorded(tmp_path, root, thresholds, detector=DETECTOR, launch="B1",
             decision="NARROW"):
    return preregistration.record_evaluation(
        root, thresholds, launch, detector, decision,
        ledger_path=tmp_path / "ledger.jsonl",
        retired_path=tmp_path / "retired.json")


# -- the pre-registration record ---------------------------------------------

def test_the_record_carries_every_hash_the_spec_lists(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    entry = corpus.read_preregistration(root)
    assert entry["thresholds_sha256"] == preregistration.thresholds_sha256(thresholds)
    assert entry["launch_configuration"] == "B1"
    assert entry["detector_sha256"] == preregistration.detector_sha256(DETECTOR)
    assert entry["detector_version"] == DETECTOR["version"]
    assert entry["taxonomy_version"] == taxonomy.TAXONOMY_VERSION
    assert entry["tool_commit"] == "c0ffee"
    assert entry["manifest_sha256"] == corpus.manifest_sha256(root)
    pins = entry["baseline_pins"]
    assert pins["B3"] == baselines.COMPETITOR_VERSION, pins
    for baseline in ("B0", "B1", "B2", "B3"):
        assert pins.get(baseline), pins
    # the record is inside the frozen manifest, not a file beside it
    manifest = json.loads((root / "FROZEN.json").read_text(encoding="utf-8"))
    assert manifest["preregistration"] == entry


def test_a_frozen_manifest_is_pre_registered_only_once(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    with pytest.raises(EvidenceError) as excinfo:
        register(root, thresholds)
    assert "pre-registered once" in str(excinfo.value), excinfo.value


def test_a_preregistered_manifest_still_loads_and_may_not_be_refrozen(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    assert [case.id for case in corpus.load_corpus(root)] == ["case-1"]
    with pytest.raises(EvidenceError) as excinfo:
        corpus.write_manifest(root)
    assert "pre-registered" in str(excinfo.value), excinfo.value


# -- the thresholds file: one versioned data file naming L1-L9 ----------------

def test_the_thresholds_file_names_l1_to_l9_with_values_and_a_version():
    payload = preregistration.load_thresholds(THRESHOLDS)
    assert payload["version"] >= 1
    assert set(payload["criteria"]) == {f"L{n}" for n in range(1, 10)}
    for name, entry in payload["criteria"].items():
        assert "value" in entry, name
        assert str(entry["criterion"]).strip(), name


@pytest.mark.parametrize("broken", ["no-version", "no-L7", "no-value"])
def test_a_thresholds_file_that_cannot_name_its_criteria_is_refused(tmp_path, broken):
    payload = {"version": 1,
               "criteria": {f"L{n}": {"criterion": f"criterion {n}", "value": n}
                            for n in range(1, 10)}}
    if broken == "no-version":
        payload.pop("version")
    elif broken == "no-L7":
        payload["criteria"].pop("L7")
    else:
        payload["criteria"]["L2"].pop("value")
    path = tmp_path / "thresholds.json"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(EvidenceError) as excinfo:
        preregistration.load_thresholds(path)
    assert "thresholds" in str(excinfo.value), excinfo.value


# -- refusals 1-3 and the missing-baseline-pin refusal ------------------------

def test_a_drifted_frozen_artifact_is_refused_naming_the_artifact(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    path = root / "case-1.json"
    row = json.loads(path.read_text(encoding="utf-8"))
    row["label"] = "clean"                      # the silent edit
    path.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(EvidenceError) as excinfo:
        preregistration.verify_preregistration(root, thresholds, "B1", DETECTOR)
    assert "case-1.json" in str(excinfo.value), excinfo.value


def test_a_drifted_thresholds_file_is_refused_naming_the_file_and_both_hashes(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    before = preregistration.thresholds_sha256(thresholds)
    payload = json.loads(thresholds.read_text(encoding="utf-8"))
    payload["criteria"]["L1"]["value"] = 0.5    # moving the goalposts
    thresholds.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(EvidenceError) as excinfo:
        preregistration.verify_preregistration(root, thresholds, "B1", DETECTOR)
    message = str(excinfo.value)
    assert "thresholds" in message, message
    assert before in message, message
    assert preregistration.thresholds_sha256(thresholds) in message, message


def test_a_drifted_launch_configuration_is_refused_naming_the_field(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    with pytest.raises(EvidenceError) as excinfo:
        preregistration.verify_preregistration(root, thresholds, "B2", DETECTOR)
    assert "launch configuration" in str(excinfo.value), excinfo.value
    changed = {**DETECTOR, "version": "held-out/2"}
    with pytest.raises(EvidenceError) as excinfo:
        preregistration.verify_preregistration(root, thresholds, "B1", changed)
    message = str(excinfo.value)
    assert "detector" in message, message
    assert preregistration.detector_sha256(DETECTOR) in message, message


def test_a_missing_or_unverifiable_baseline_pin_is_refused_naming_the_pin(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    entry = preregistration.preregistration_record(
        root, thresholds, "B1", DETECTOR, tool_commit="c0ffee")
    missing = dict(entry["baseline_pins"])
    missing.pop("B3")
    corpus.write_preregistration(root, {**entry, "baseline_pins": missing})
    with pytest.raises(EvidenceError) as excinfo:
        preregistration.verify_baseline_pins(corpus.read_preregistration(root))
    assert "B3" in str(excinfo.value), excinfo.value

    root = frozen_corpus(tmp_path, record(), name="second")
    wrong = dict(entry["baseline_pins"])
    wrong["B3"] = "9.9.9"
    corpus.write_preregistration(root, {**entry, "baseline_pins": wrong})
    with pytest.raises(EvidenceError) as excinfo:
        preregistration.verify_baseline_pins(corpus.read_preregistration(root))
    message = str(excinfo.value)
    assert "B3" in message, message
    assert "9.9.9" in message, message
    assert baselines.COMPETITOR_VERSION in message, message


def test_verification_writes_nothing(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    before = (root / "FROZEN.json").read_bytes()
    preregistration.verify_preregistration(root, thresholds, "B1", DETECTOR)
    assert (root / "FROZEN.json").read_bytes() == before
    assert not (tmp_path / "ledger.jsonl").exists()
    assert not (tmp_path / "retired.json").exists()


# -- the evaluation ledger: append-only, hash-chained -------------------------

def test_the_first_evaluation_appends_one_hash_chained_entry(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    result = recorded(tmp_path, root, thresholds)
    assert result.appended is True
    entries = preregistration.read_ledger(tmp_path / "ledger.jsonl")
    assert len(entries) == 1
    entry = entries[0]
    assert entry["manifest_sha256"] == corpus.manifest_sha256(root)
    assert entry["detector_sha256"] == preregistration.detector_sha256(DETECTOR)
    assert entry["thresholds_sha256"] == preregistration.thresholds_sha256(thresholds)
    assert entry["decision"] == "NARROW"
    assert entry["prev"] == GENESIS
    assert result.entry == entry
    line = (tmp_path / "ledger.jsonl").read_bytes()
    assert line.endswith(b"\n") and b"\r" not in line
    assert json.loads(line) == entry


def test_an_identical_rerun_appends_nothing_and_reproduces_the_decision_and_bytes(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    first = recorded(tmp_path, root, thresholds)
    before = (tmp_path / "ledger.jsonl").read_bytes()
    second = recorded(tmp_path, root, thresholds)
    assert second.appended is False
    assert second.entry == first.entry
    assert second.as_bytes() == first.as_bytes()
    assert (tmp_path / "ledger.jsonl").read_bytes() == before


def test_an_identical_rerun_with_a_different_decision_is_refused(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    recorded(tmp_path, root, thresholds, decision="NARROW")
    with pytest.raises(EvidenceError) as excinfo:
        recorded(tmp_path, root, thresholds, decision="LAUNCH")
    message = str(excinfo.value)
    assert "NARROW" in message and "LAUNCH" in message, message


def test_a_rerun_with_a_changed_detector_is_refused_and_changes_nothing(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    recorded(tmp_path, root, thresholds)
    before = (tmp_path / "ledger.jsonl").read_bytes()
    changed = {**DETECTOR, "version": "held-out/2"}
    with pytest.raises(EvidenceError) as excinfo:
        recorded(tmp_path, root, thresholds, detector=changed)
    message = str(excinfo.value)
    assert corpus.manifest_sha256(root) in message, message
    assert preregistration.detector_sha256(changed) in message, message
    assert (tmp_path / "ledger.jsonl").read_bytes() == before


def test_a_tampered_ledger_entry_is_caught_by_the_chain(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    recorded(tmp_path, root, thresholds, decision="NARROW")
    recorded(tmp_path, root, thresholds, decision="NARROW")   # identical rerun
    path = tmp_path / "ledger.jsonl"
    raw = path.read_bytes()
    path.write_bytes(raw.replace(b'"decision":"NARROW"', b'"decision":"LAUNCH"'))
    with pytest.raises(EvidenceError) as excinfo:
        preregistration.verify_ledger(path)
    assert "entry 1" in str(excinfo.value), excinfo.value


# -- retired repositories: populated by any evaluation, enforced at freeze ----

def test_any_evaluation_retires_its_repositories(tmp_path):
    root = frozen_corpus(tmp_path, record(), record(id="case-2", task="task-2"))
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    recorded(tmp_path, root, thresholds)
    assert preregistration.read_retired_repositories(
        tmp_path / "retired.json") == ("https://example.org/org/project",)
    recorded(tmp_path, root, thresholds)   # a rerun retires again, harmlessly
    assert preregistration.read_retired_repositories(
        tmp_path / "retired.json") == ("https://example.org/org/project",)


def test_a_new_frozen_split_reusing_a_retired_repository_is_rejected(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    recorded(tmp_path, root, thresholds)
    reused = tmp_path / "reused"
    reused.mkdir()
    (reused / "case-9.json").write_text(json.dumps(record(id="case-9")) + "\n",
                                        encoding="utf-8")
    with pytest.raises(EvidenceError) as excinfo:
        corpus.write_manifest(reused, retired_registry=tmp_path / "retired.json")
    message = str(excinfo.value)
    assert "https://example.org/org/project" in message, message
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    (fresh / "case-8.json").write_text(
        json.dumps(record(id="case-8", task="task-8",
                          repository="https://example.org/org/other")) + "\n",
        encoding="utf-8")
    written = corpus.write_manifest(fresh, retired_registry=tmp_path / "retired.json")
    assert set(written) == {"case-8.json"}


# -- a refusal writes no ledger entry ----------------------------------------

def test_a_refused_run_writes_no_ledger_entry(tmp_path):
    root = frozen_corpus(tmp_path, record())
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    path = root / "case-1.json"
    row = json.loads(path.read_text(encoding="utf-8"))
    row["label"] = "clean"
    path.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(EvidenceError):
        recorded(tmp_path, root, thresholds)
    assert not (tmp_path / "ledger.jsonl").exists()
    assert not (tmp_path / "retired.json").exists()
