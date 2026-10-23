"""The importers: fixture sources turned into unadjudicated case records.

R3 imports local agent runs on impossible tasks where labels are fixed by
construction (any pass is an exploit) but the technique still needs review.
R4 imports public dataset entries only with an executable suite and a
recorded license decision that permits the use. R5 imports public agent pull
request metadata and diffs only where the license permits, and never touches
the repository. Every refusal names the offending field and the entry: a
missing license decision, a license that does not permit the use, an unknown
technique, an R4 entry without a suite. Nothing here touches the network --
the fixtures under tests/fixtures/importers are the outside sources.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import corpus, importers, taxonomy  # noqa: E402
from greenwash.evidence import EvidenceError  # noqa: E402

FIXTURES = HERE / "fixtures" / "importers"

ROUTES = (
    ("r3", "R3", "local-run", importers.import_local_runs),
    ("r4", "R4", "dataset", importers.import_dataset_entries),
    ("r5", "R5", "public-pr", importers.import_pull_requests),
)


def copy_source(tmp_path, name):
    destination = tmp_path / name
    shutil.copytree(FIXTURES / name, destination)
    return destination


def edit_entry(source, name, drop=(), **changes):
    path = source / name
    entry = json.loads(path.read_text(encoding="utf-8"))
    for field in drop:
        entry.pop(field, None)
    entry.update(changes)
    path.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    return entry


# -- each route imports a fixture source into unadjudicated records -----------

@pytest.mark.parametrize("dirname,route,category,importer", ROUTES)
def test_each_route_imports_a_fixture_source_into_unadjudicated_records(
        tmp_path, dirname, route, category, importer):
    source = copy_source(tmp_path, dirname)
    records = importer(source)
    assert records
    for record in records:
        assert corpus.validate_case(record) == []
        assert record["route"] == route
        assert record["source"].startswith(f"{category}: ")
        assert record["license"]
        assert record["technique"] in taxonomy.BY_ID
        assert taxonomy.validate_technique(record, "technique") == []
        case = corpus.case_from_record(record)
        assert case.adjudicated is None
        assert case.labels is None
        assert case.split == corpus.DEV
    assert corpus.validate_cases(records) == []


def test_r3_labels_are_by_construction_from_the_run_outcome(tmp_path):
    source = copy_source(tmp_path, "r3")
    records = {row["id"]: row for row in importers.import_local_runs(source)}
    assert records["r3-run-pass"]["label"] == corpus.TAMPERED
    assert records["r3-run-fail"]["label"] == corpus.CLEAN
    for row in records.values():
        assert "labels" not in row


def test_an_r3_entry_may_not_name_a_label_of_its_own(tmp_path):
    source = copy_source(tmp_path, "r3")
    edit_entry(source, "r3-run-pass.json", label="clean")
    with pytest.raises(EvidenceError) as excinfo:
        importers.import_local_runs(source)
    assert "label" in str(excinfo.value)
    assert "r3-run-pass" in str(excinfo.value)


def test_r5_imports_the_diff_and_records_its_hash(tmp_path):
    source = copy_source(tmp_path, "r5")
    records = importers.import_pull_requests(source)
    assert len(records) == 1
    raw = (source / "r5-pr-412.diff").read_bytes()
    assert records[0]["diff_hash"] == hashlib.sha256(raw).hexdigest()
    assert records[0]["diff_path"] == "r5-pr-412.diff"


# -- refusals, each naming the offending field and the entry ------------------

def test_an_r4_entry_without_an_executable_suite_is_refused_by_name(tmp_path):
    source = copy_source(tmp_path, "r4")
    edit_entry(source, "r4-entry-1.json", drop=("suite",))
    with pytest.raises(EvidenceError) as excinfo:
        importers.import_dataset_entries(source)
    assert "suite" in str(excinfo.value)
    assert "r4-entry-1" in str(excinfo.value)


@pytest.mark.parametrize("dirname,route,category,importer", ROUTES)
def test_a_source_without_a_recorded_license_decision_is_refused_never_defaulted(
        tmp_path, dirname, route, category, importer):
    source = copy_source(tmp_path, dirname)
    with pytest.raises(EvidenceError) as excinfo:
        importer(source, {})
    assert "license" in str(excinfo.value)
    assert "never defaulted" in str(excinfo.value)


def test_a_source_without_license_records_entirely_is_refused(tmp_path):
    source = copy_source(tmp_path, "r4")
    (source / "LICENSES.json").unlink()
    with pytest.raises(EvidenceError) as excinfo:
        importers.import_dataset_entries(source)
    assert "LICENSES.json" in str(excinfo.value)


def test_a_license_decision_that_does_not_permit_the_use_is_refused(tmp_path):
    source = copy_source(tmp_path, "r4")
    edit_entry(source, "r4-entry-1.json", license="CC-BY-ND-4.0")
    with pytest.raises(EvidenceError) as excinfo:
        importers.import_dataset_entries(source)
    assert "CC-BY-ND-4.0" in str(excinfo.value)
    assert "r4-entry-1" in str(excinfo.value)


def test_an_unknown_technique_is_refused_by_name(tmp_path):
    source = copy_source(tmp_path, "r4")
    edit_entry(source, "r4-entry-1.json", technique="made-up-technique")
    with pytest.raises(EvidenceError) as excinfo:
        importers.import_dataset_entries(source)
    assert "technique" in str(excinfo.value)
    assert "r4-entry-1" in str(excinfo.value)


def test_a_replay_needing_technique_without_a_replay_record_is_refused(tmp_path):
    source = copy_source(tmp_path, "r4")
    edit_entry(source, "r4-entry-1.json", drop=("replay",),
               technique="deleted-test")
    with pytest.raises(EvidenceError) as excinfo:
        importers.import_dataset_entries(source)
    assert "replay" in str(excinfo.value)
    assert "r4-entry-1" in str(excinfo.value)


def test_an_r5_entry_without_a_diff_file_is_refused_by_name(tmp_path):
    source = copy_source(tmp_path, "r5")
    edit_entry(source, "r5-pr-412.json", diff_path="gone.diff")
    with pytest.raises(EvidenceError) as excinfo:
        importers.import_pull_requests(source)
    assert "gone.diff" in str(excinfo.value)
    assert "r5-pr-412" in str(excinfo.value)


# -- the license check itself must be a recorded decision ---------------------

@pytest.mark.parametrize("decision,field", [
    ({"permits": True, "checked": "2026-04-02: read the terms"}, "license"),
    ({"license": "MIT", "checked": "2026-04-02: read the terms"}, "permits"),
    ({"license": "MIT", "permits": "yes"}, "permits"),
    ({"license": "MIT", "permits": True}, "checked"),
])
def test_a_license_decision_that_cannot_be_recorded_is_refused(
        tmp_path, decision, field):
    path = tmp_path / "LICENSES.json"
    path.write_text(json.dumps({"decisions": [decision]}), encoding="utf-8")
    with pytest.raises(EvidenceError) as excinfo:
        importers.read_license_decisions(path)
    assert field in str(excinfo.value)


def test_a_recorded_license_decision_round_trips(tmp_path):
    source = copy_source(tmp_path, "r3")
    decisions = importers.read_license_decisions(source / "LICENSES.json")
    assert set(decisions) == {"MIT"}
    assert decisions["MIT"].permits is True
    assert decisions["MIT"].checked
    assert importers.import_local_runs(source, decisions)
