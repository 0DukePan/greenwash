"""The dev-run command: the assemble stage and the checkpoint state.

One seam, `benchmark/dev_run.py`, driven at its public command. The
acceptance criteria of .scratch/dev-corpus-run/issues/01, each one literal
here:

* assembling a fixture candidate set yields a manifest, counts by route and
  class, and no adjudicated record;
* a duplicate diff hash, an over-cap repository, a synthetic record and a
  missing field are each refused by name;
* re-running assemble on changed inputs replaces the manifest and records
  the new input hashes;
* a bare invocation names the next stage; an out-of-order stage is refused
  by name.

The candidate fixtures are miner- and importer-shaped unadjudicated records
(case record v2): route, base and head refs, diff hash, a taxonomy
technique, and no `labels` block.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import dev_run  # noqa: E402
import gate_a  # noqa: E402


def candidate(case_id="R1-0001", **overrides):
    """One unadjudicated candidate record, miner-shaped (case record v2)."""
    record = {
        "id": case_id,
        "source": "history: mined from repository history as git objects",
        "technique": "skip-or-xfail",
        "label": "tampered",
        "split": "dev",
        "task": f"commit:{case_id}",
        "repository": "example/repo-one",
        "license": "MIT",
        "route": "R1",
        "base_ref": "a" * 40,
        "head_ref": "b" * 40,
        "diff_hash": hashlib.sha256(case_id.encode("utf-8")).hexdigest(),
    }
    record.update(overrides)
    return record


def write_candidates(root, records):
    """One JSON case file per record, the miners' and importers' layout."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for record in records:
        name = str(record.get("id") or "record")
        (root / f"{name}.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return root


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# -- the checkpoint state: where the run is, and what is next ----------------

def test_bare_invocation_prints_the_current_stage_and_the_next_required_one(
        tmp_path, capsys):
    run = tmp_path / "dev-run"
    assert dev_run.dev_run(["--run-dir", str(run)]) == 0
    out = capsys.readouterr().out
    assert "current stage: none" in out
    assert "next required stage: assemble" in out


def test_out_of_order_stage_is_a_refusal_naming_the_stage_and_its_prerequisite(
        tmp_path, capsys):
    run = tmp_path / "dev-run"
    assert dev_run.dev_run(["calibrate", "--run-dir", str(run)]) == 2
    err = capsys.readouterr().err
    assert "calibrate" in err
    assert "assemble" in err
    assert "out of order" in err


def test_bare_invocation_after_assemble_names_the_next_stage(tmp_path, capsys):
    run = tmp_path / "dev-run"
    write_candidates(tmp_path / "candidates", [candidate("R1-0001")])
    assert dev_run.dev_run(["assemble", str(tmp_path / "candidates"),
                            "--run-dir", str(run)]) == 0
    capsys.readouterr()
    assert dev_run.dev_run(["--run-dir", str(run)]) == 0
    out = capsys.readouterr().out
    assert "current stage: assemble" in out
    assert "next required stage: calibrate" in out


# -- assemble: the manifest, the counts, and no adjudicated record -----------

def test_assemble_writes_a_versioned_manifest_with_input_hashes_and_counts(
        tmp_path, capsys):
    candidates = write_candidates(tmp_path / "candidates", [
        candidate("R1-0001", repository="example/repo-one"),
        candidate("R1-0002", repository="example/repo-one"),
        candidate("R3-0001", route="R3", label="clean",
                  repository="example/repo-two"),
    ])
    run = tmp_path / "dev-run"
    assert dev_run.dev_run(["assemble", str(candidates),
                            "--run-dir", str(run)]) == 0
    manifest = json.loads((run / "dev-manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 1
    assert manifest["split"] == "dev"
    assert manifest["inputs"] == {
        name: sha256_of(candidates / name)
        for name in ("R1-0001.json", "R1-0002.json", "R3-0001.json")}
    assert [record["id"] for record in manifest["records"]] == \
        ["R1-0001", "R1-0002", "R3-0001"]
    assert manifest["counts_by_route"] == {"R1": 2, "R3": 1}
    assert manifest["counts_by_class"] == {"clean": 1, "tampered": 2}
    out = capsys.readouterr().out
    assert "counts by route: R1=2, R3=1" in out
    assert "counts by class: clean=1, tampered=2" in out


def test_assembled_manifest_carries_no_labels_and_no_adjudication(tmp_path):
    candidates = write_candidates(tmp_path / "candidates", [
        candidate("R1-0001"), candidate("R1-0002")])
    run = tmp_path / "dev-run"
    assert dev_run.dev_run(["assemble", str(candidates),
                            "--run-dir", str(run)]) == 0
    manifest = json.loads((run / "dev-manifest.json").read_text(encoding="utf-8"))
    for record in manifest["records"]:
        assert "labels" not in record
        assert record.get("adjudicated") is None


# -- the named refusals -----------------------------------------------------

def assemble_refusal(tmp_path, records, capsys):
    candidates = write_candidates(tmp_path / "candidates", records)
    run = tmp_path / "dev-run"
    assert dev_run.dev_run(["assemble", str(candidates),
                            "--run-dir", str(run)]) == 2
    assert not (run / "dev-manifest.json").exists()
    return capsys.readouterr().err


def test_duplicate_diff_hash_across_routes_is_refused_by_name(tmp_path, capsys):
    shared = hashlib.sha256(b"one change").hexdigest()
    err = assemble_refusal(tmp_path, [
        candidate("R1-0001", route="R1", diff_hash=shared),
        candidate("R3-0001", route="R3", label="clean", diff_hash=shared),
    ], capsys)
    assert "diff_hash" in err
    assert shared in err
    assert "R1-0001.json" in err and "R3-0001.json" in err


def test_over_cap_repository_is_refused_by_name(tmp_path, capsys):
    err = assemble_refusal(tmp_path, [
        candidate(f"R1-000{i}", repository="example/repo-one")
        for i in range(1, 7)
    ], capsys)
    assert "repository: example/repo-one" in err
    assert "cap" in err
    assert "6 cases to class 'tampered'" in err


def test_cap_is_per_class_so_five_per_class_from_one_repository_assembles(
        tmp_path, capsys):
    candidates = write_candidates(tmp_path / "candidates", [
        candidate(f"R1-000{i}", repository="example/repo-one") for i in range(1, 6)
    ] + [
        candidate(f"R1-100{i}", repository="example/repo-one", label="clean")
        for i in range(1, 6)
    ])
    run = tmp_path / "dev-run"
    assert dev_run.dev_run(["assemble", str(candidates),
                            "--run-dir", str(run)]) == 0
    manifest = json.loads((run / "dev-manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts_by_class"] == {"clean": 5, "tampered": 5}


@pytest.mark.parametrize("overrides", [
    {"source": "synthetic: injected from the detector's own taxonomy"},
    {"origin": "synthetic"},
    {"source": "planted: fixture case"},
])
def test_synthetic_and_planted_records_are_refused_by_name(
        tmp_path, capsys, overrides):
    err = assemble_refusal(tmp_path, [candidate("R1-0001", **overrides)], capsys)
    assert "source" in err or "origin" in err
    assert "R1-0001.json" in err


@pytest.mark.parametrize("field", ["route", "technique", "license", "diff_hash"])
def test_missing_field_is_refused_by_name(tmp_path, capsys, field):
    record = candidate("R1-0001")
    del record[field]
    err = assemble_refusal(tmp_path, [record], capsys)
    assert f"{field}:" in err
    assert "R1-0001.json" in err


@pytest.mark.parametrize("labels", [
    {"labeler1": "tampered"},
    {"adjudicated": "tampered"},
    {"labeler1": "tampered", "labeler2": "clean", "adjudicated": "tampered",
     "disagreement": True},
])
def test_a_record_carrying_labels_or_adjudication_is_refused_by_name(
        tmp_path, capsys, labels):
    err = assemble_refusal(tmp_path, [candidate("R1-0001", labels=labels)],
                           capsys)
    assert "labels:" in err
    assert "unadjudicated" in err
    assert "R1-0001.json" in err


def test_in_order_stage_beyond_calibrate_is_the_skeleton_refused_by_name(
        tmp_path, capsys):
    run = assembled(tmp_path)
    calibration = write_calibration(tmp_path / "calibration-input.json",
                                    readings(30.0))
    assert dev_run.dev_run(["calibrate", str(calibration),
                            "--run-dir", str(run),
                            "--register", str(register_copy(tmp_path))]) == 0
    capsys.readouterr()
    assert dev_run.dev_run(["label", "--run-dir", str(run)]) == 2
    err = capsys.readouterr().err
    assert "label" in err
    assert "not built" in err


# -- reruns and warnings ----------------------------------------------------

def test_rerun_on_changed_inputs_replaces_the_manifest_and_records_new_hashes(
        tmp_path, capsys):
    candidates = write_candidates(tmp_path / "candidates", [
        candidate("R1-0001"), candidate("R1-0002")])
    run = tmp_path / "dev-run"
    assert dev_run.dev_run(["assemble", str(candidates),
                            "--run-dir", str(run)]) == 0
    first = json.loads((run / "dev-manifest.json").read_text(encoding="utf-8"))
    changed = candidate("R1-0002", technique="assertion-weakened")
    write_candidates(candidates, [changed])
    capsys.readouterr()
    assert dev_run.dev_run(["assemble", str(candidates),
                            "--run-dir", str(run)]) == 0
    second = json.loads((run / "dev-manifest.json").read_text(encoding="utf-8"))
    assert second["inputs"]["R1-0002.json"] == sha256_of(
        candidates / "R1-0002.json")
    assert second["inputs"]["R1-0002.json"] != first["inputs"]["R1-0002.json"]
    assert second["inputs"]["R1-0001.json"] == first["inputs"]["R1-0001.json"]
    techniques = {record["id"]: record["technique"]
                  for record in second["records"]}
    assert techniques == {"R1-0001": "skip-or-xfail",
                          "R1-0002": "assertion-weakened"}


def test_a_class_under_the_dev_minimum_is_warned_about_not_silently_accepted(
        tmp_path, capsys):
    candidates = write_candidates(tmp_path / "candidates", [
        candidate("R1-0001"), candidate("R1-0002")])
    run = tmp_path / "dev-run"
    assert dev_run.dev_run(["assemble", str(candidates),
                            "--run-dir", str(run)]) == 0
    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert "under the dev minimum of 60" in captured.err
    manifest = json.loads((run / "dev-manifest.json").read_text(encoding="utf-8"))
    assert any("under the dev minimum of 60" in warning
               for warning in manifest["warnings"])
    assert manifest["counts_by_class"] == {"tampered": 2}


# -- the calibrate stage: measurement, artifact, closed assumption -----------

CASE_IDS = [f"R1-{index:04d}" for index in range(1, 21)]


def assembled(tmp_path):
    """A twenty-case dev manifest, assembled through the command itself."""
    run = tmp_path / "dev-run"
    candidates = write_candidates(tmp_path / "candidates", [
        candidate(case_id, repository=f"example/repo-{index // 5}")
        for index, case_id in enumerate(CASE_IDS)])
    assert dev_run.dev_run(["assemble", str(candidates),
                            "--run-dir", str(run)]) == 0
    return run


def readings(seconds=30.0):
    """One measured time per case, the calibration file's readings."""
    return [{"case": case_id, "seconds": seconds} for case_id in CASE_IDS]


def write_calibration(path, measured, labeler="fixture-labeler"):
    path.write_text(json.dumps({"labeler": labeler, "readings": measured},
                               indent=2) + "\n", encoding="utf-8")
    return path


def register_copy(tmp_path):
    """The shipped assumptions register, copied somewhere a test may write."""
    register = tmp_path / "assumptions.json"
    register.write_text(
        (ROOT / "benchmark" / "assumptions.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    return register


def calibrate_refusal(tmp_path, register=None):
    """Run the calibrate stage and return the refusal, by name."""
    run = assembled(tmp_path)
    calibration = write_calibration(tmp_path / "calibration-input.json",
                                    readings(30.0))
    if register is not None:
        payload = json.loads(register.read_text(encoding="utf-8"))
        for entry in payload["assumptions"]:
            if entry["id"] == "competitor-overhead-figures":
                entry["status"] = "verified"
        register.write_text(json.dumps(payload, indent=2) + "\n",
                            encoding="utf-8")
    assert dev_run.dev_run(["calibrate", str(calibration),
                            "--run-dir", str(run),
                            "--register",
                            str(register or register_copy(tmp_path))]) == 2
    return run


def test_calibrate_writes_a_measurement_artifact_carrying_its_input_hashes(
        tmp_path, capsys):
    run = assembled(tmp_path)
    measured = readings(30.0)
    measured[0]["seconds"] = 60.0
    calibration = write_calibration(tmp_path / "calibration-input.json", measured)
    assert dev_run.dev_run(["calibrate", str(calibration),
                            "--run-dir", str(run),
                            "--register", str(register_copy(tmp_path))]) == 0
    artifact = json.loads((run / "calibration.json").read_text(encoding="utf-8"))
    assert artifact["inputs"] == {
        "calibration-input.json": sha256_of(calibration),
        "dev-manifest.json": sha256_of(run / "dev-manifest.json")}
    assert artifact["cases"] == 20
    assert artifact["total_seconds"] == 630.0
    assert artifact["seconds_per_case"] == 31.5


def test_calibrate_closes_the_labeling_time_assumption_with_the_measurement_and_the_artifact_path(
        tmp_path, capsys):
    run = assembled(tmp_path)
    calibration = write_calibration(tmp_path / "calibration-input.json",
                                    readings(30.0))
    register = register_copy(tmp_path)
    assert dev_run.dev_run(["calibrate", str(calibration),
                            "--run-dir", str(run),
                            "--register", str(register)]) == 0
    out = capsys.readouterr().out
    entry = {row["id"]: row for row in json.loads(
        register.read_text(encoding="utf-8"))["assumptions"]}
    closed = entry["labeling-time-per-case"]
    assert closed["status"] == "verified"
    assert closed["number"] == "30 seconds per case"
    assert closed["evidence"] == str(run / "calibration.json")
    assert "labeling-time-per-case" in out
    assert "verified" in out


def test_a_case_id_outside_the_dev_manifest_is_refused_by_name(tmp_path, capsys):
    run = assembled(tmp_path)
    measured = readings(30.0)
    measured[7]["case"] = "R9-9999"
    calibration = write_calibration(tmp_path / "calibration-input.json", measured)
    assert dev_run.dev_run(["calibrate", str(calibration),
                            "--run-dir", str(run),
                            "--register", str(register_copy(tmp_path))]) == 2
    err = capsys.readouterr().err
    assert "R9-9999" in err
    assert not (run / "calibration.json").exists()


def test_the_calibrate_write_path_refuses_a_verified_assumption_without_an_evidence_path_by_name(
        tmp_path, capsys):
    register = register_copy(tmp_path)
    run = calibrate_refusal(tmp_path, register)
    err = capsys.readouterr().err
    assert "competitor-overhead-figures" in err
    assert not (run / "calibration.json").exists()


def test_calibrate_refuses_without_the_assembly_manifest_naming_it(tmp_path):
    run = tmp_path / "dev-run"
    run.mkdir()
    calibration = write_calibration(tmp_path / "calibration-input.json",
                                    readings(30.0))
    with pytest.raises(dev_run.DevRunError) as excinfo:
        dev_run.calibrate(calibration, run, register=register_copy(tmp_path))
    message = str(excinfo.value)
    assert "assemble" in message
    assert "dev-manifest.json" in message


def test_gate_a_consumes_the_closed_register_without_a_hand_edit(tmp_path):
    run = assembled(tmp_path)
    calibration = write_calibration(tmp_path / "calibration-input.json",
                                    readings(30.0))
    register = register_copy(tmp_path)
    payload = json.loads(register.read_text(encoding="utf-8"))
    for entry in payload["assumptions"]:
        if entry["id"] == "competitor-overhead-figures":
            entry["status"] = "verified"
            entry["evidence"] = "dev-run/baselines.json"
    register.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    assert dev_run.dev_run(["calibrate", str(calibration),
                            "--run-dir", str(run),
                            "--register", str(register)]) == 0
    fixture = ROOT / "tests" / "fixtures" / "gate_a" / "go"

    def read(name):
        return json.loads((fixture / name).read_text(encoding="utf-8"))

    record = gate_a.gate_a(read("dev-table.json"), read("labelled.json"),
                           read("baselines.json"),
                           json.loads(register.read_text(encoding="utf-8")))
    assert record["decision"] == "go"
