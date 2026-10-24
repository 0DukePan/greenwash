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


def test_in_order_stage_beyond_assemble_is_the_skeleton_refused_by_name(
        tmp_path, capsys):
    candidates = write_candidates(tmp_path / "candidates", [candidate("R1-0001")])
    run = tmp_path / "dev-run"
    assert dev_run.dev_run(["assemble", str(candidates),
                            "--run-dir", str(run)]) == 0
    capsys.readouterr()
    assert dev_run.dev_run(["calibrate", "--run-dir", str(run)]) == 2
    err = capsys.readouterr().err
    assert "calibrate" in err
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
