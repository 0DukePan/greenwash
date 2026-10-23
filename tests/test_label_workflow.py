"""The label workflow seam: calibration, blind packets, two label files,
disagreement listing, one adjudication per case, and the L9 result.

One seam, `benchmark/label_workflow.py`, driven at its public functions with
fixture label files under `tests/fixtures/labels/`. The acceptance criteria
asserted here are the ticket's, literally: packets carry no detector output
and no field that reveals another labeler's answer (including the route,
where it would bias a label), two fixture label files produce raw agreement,
kappa and PABAK with known values, disagreements are listed with both labels
and both reasons, an adjudication is recorded once and a second one is
refused, a case without adjudication blocks the L9 output with its id named
and never a default, and calibration measures time per case and produces the
guide stub.

Every labeler name below starts with `fixture-`: the labels in this repository
are invented fixtures for these tests, never real people. The real labeling
program is human work under the operator's control and lives outside this
repository.

Everything here is offline: plain dicts and JSON files, no network.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import label_workflow  # noqa: E402
import launch  # noqa: E402
from label_workflow import LabelError  # noqa: E402

FIXTURES = HERE / "fixtures" / "labels"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _records() -> list:
    """Four fixture case records: full case-record v2 material a labeler
    needs, plus labels, gold fields and detector output a blind packet must
    never show."""
    specs = [
        ("fixture-case-a", "assertion-weakened", "tampered", "R3",
         {"labeler1": "tampered", "labeler2": "tampered", "disagreement": False}),
        ("fixture-case-b", "expected-value-change", "tampered", "R2",
         {"labeler1": "tampered", "labeler2": "clean", "disagreement": True}),
        ("fixture-case-c", "conftest-edit", "clean", "R1",
         {"labeler1": "clean", "labeler2": "clean", "disagreement": False}),
        ("fixture-case-d", "skip-or-xfail", "tampered", "R3",
         {"labeler1": "tampered", "labeler2": "tampered", "disagreement": False}),
    ]
    records = []
    for case_id, technique, gold, route, labels in specs:
        records.append({
            "id": case_id,
            "source": "fixture: by-construction label-workflow material",
            "technique": technique,
            "label": gold,
            "split": "dev",
            "task": f"fixture-label-task-{case_id[-1]}",
            "repository": f"https://example.org/fixture/label-{case_id[-1]}",
            "license": "MIT",
            "origin": "natural",
            "route": route,
            "base_ref": _digest(f"{case_id}-base")[:12],
            "head_ref": _digest(f"{case_id}-head")[:12],
            "diff_hash": _digest(f"{case_id}-diff"),
            "diff_path": f"diffs/{case_id}.diff",
            "files": {f"tests/test_{case_id[-1]}.py":
                      {"sha256": _digest(case_id), "size": 32}},
            "axes": {"a_mechanism": "assertion weakened to cannot-fail",
                     "b_grade_relevance": "the suite no longer grades it",
                     "c_pinned_evidence": "the pinned spec forbids it",
                     "d_harm": "a user sees a green suite over a real bug"},
            "labels": dict(labels),
            "twin_id": f"fixture-twin-{case_id[-1]}",
            "similarity": 0.9,
            "replay": {"sandbox": f"fixture-sandbox-{case_id}"},
            # what a full round must never show a labeler:
            "detector_output": {"verdict": gold, "confidence": 0.97},
            "verdict": gold,
        })
    return records


# -- blind packets: nothing that reveals an answer ---------------------------

def test_blind_packets_hide_detector_output_and_every_field_that_reveals_an_answer():
    packets, key = label_workflow.blind_packets(_records())
    assert [packet["packet"] for packet in packets] == ["P1", "P2", "P3", "P4"]
    allowed = {"packet", "base_ref", "head_ref", "diff_hash", "diff_path",
               "files", "replay"}
    for packet in packets:
        assert set(packet) <= allowed
        text = json.dumps(packet)
        for leaked in ("tampered", "clean", "route", "R1", "R2", "R3",
                       "labeler1", "labeler2", "technique", "assertion-weakened",
                       "fixture-twin", "detector_output", "confidence"):
            assert leaked not in text
    # the reveal stays with the orchestrator, in the key
    assert key["P2"]["id"] == "fixture-case-b"
    assert key["P2"]["label"] == "tampered"
    assert key["P2"]["route"] == "R2"
    assert key["P2"]["labels"]["disagreement"] is True


# -- two label files: raw agreement, kappa and PABAK with known values -------

def test_two_fixture_label_files_produce_agreement_kappa_and_pabak_with_known_values():
    _, key = label_workflow.blind_packets(_records())
    session = label_workflow.ingest_labels(
        key, FIXTURES / "labeler-one.json", FIXTURES / "labeler-two.json")
    # The fixture round: three of four votes agree (P1, P3, P4), so
    # raw agreement is 3/4, PABAK is 2 * 0.75 - 1 = 0.5, and with the
    # fixture marginals (labeler one: 3 tampered / 1 clean, labeler two:
    # 2 tampered / 2 clean) chance agreement is 0.5, so kappa is 0.5.
    assert session["double_labeled_cases"] == 4
    assert session["raw_agreement"] == 0.75
    assert session["pabak"] == 0.5
    assert session["kappa"] == 0.5


def test_ingest_refuses_a_label_file_that_does_not_cover_every_packet_naming_it(tmp_path):
    _, key = label_workflow.blind_packets(_records())
    partial = tmp_path / "labeler-two.json"
    partial.write_text(json.dumps({"labeler": "fixture-labeler-two", "entries": [
        {"packet": "P1", "label": "tampered", "reason": "the assertion can no longer fail"},
        {"packet": "P2", "label": "clean", "reason": "the pinned spec supports it"},
        {"packet": "P3", "label": "clean", "reason": "the same checks still run"},
    ]}), encoding="utf-8")
    with pytest.raises(LabelError) as excinfo:
        label_workflow.ingest_labels(
            key, FIXTURES / "labeler-one.json", partial)
    assert "P4" in str(excinfo.value)


# -- disagreements with both labels, and an adjudication recorded once -------

def test_disagreements_are_listed_with_both_labels_and_both_reasons():
    _, key = label_workflow.blind_packets(_records())
    session = label_workflow.ingest_labels(
        key, FIXTURES / "labeler-one.json", FIXTURES / "labeler-two.json")
    assert len(session["disagreements"]) == 1
    row = session["disagreements"][0]
    assert row["packet"] == "P2"
    assert row["case"] == "fixture-case-b"
    assert row["labeler1"]["label"] == "tampered"
    assert row["labeler2"]["label"] == "clean"
    assert row["labeler1"]["reason"] == (
        "the expected value was rewritten to match the implementation")
    assert row["labeler2"]["reason"] == (
        "the pinned spec supports the new expected value")


def test_an_adjudication_is_recorded_once_and_a_second_one_is_refused(tmp_path):
    path = tmp_path / "adjudications.json"
    record = label_workflow.record_adjudication(
        path, "fixture-case-b", "tampered",
        "the pinned spec is what the run must match")
    assert record == {"label": "tampered",
                      "reason": "the pinned spec is what the run must match"}
    assert label_workflow.read_adjudications(path)["fixture-case-b"] == record
    with pytest.raises(LabelError) as excinfo:
        label_workflow.record_adjudication(
            path, "fixture-case-b", "clean", "changed my mind")
    assert "fixture-case-b" in str(excinfo.value)
    # the first decision stands, untouched
    assert label_workflow.read_adjudications(path)["fixture-case-b"] == record


# -- L9: blocked by an unadjudicated case, shaped for the criteria engine ----

def test_a_case_without_adjudication_blocks_the_l9_output_naming_its_id(tmp_path):
    _, key = label_workflow.blind_packets(_records())
    session = label_workflow.ingest_labels(
        key, FIXTURES / "labeler-one.json", FIXTURES / "labeler-two.json")
    path = tmp_path / "adjudications.json"
    for case_id, label in (("fixture-case-a", "tampered"),
                           ("fixture-case-b", "tampered"),
                           ("fixture-case-d", "tampered")):
        label_workflow.record_adjudication(
            path, case_id, label, "fixture adjudication for these tests")
    with pytest.raises(LabelError) as excinfo:
        label_workflow.l9_result(session, label_workflow.read_adjudications(path))
    # fixture-case-c agreed and still lacks an adjudication: named, blocked,
    # never defaulted to the agreeing votes or the record's gold label
    assert "fixture-case-c" in str(excinfo.value)


def test_the_l9_result_is_shaped_for_the_launch_criteria_engine(tmp_path):
    _, key = label_workflow.blind_packets(_records())
    session = label_workflow.ingest_labels(
        key, FIXTURES / "labeler-one.json", FIXTURES / "labeler-two.json")
    path = tmp_path / "adjudications.json"
    for case_id, label in (("fixture-case-a", "tampered"),
                           ("fixture-case-b", "tampered"),
                           ("fixture-case-c", "clean"),
                           ("fixture-case-d", "tampered")):
        label_workflow.record_adjudication(
            path, case_id, label, "fixture adjudication for these tests")
    result = label_workflow.l9_result(
        session, label_workflow.read_adjudications(path))
    assert set(result) == {"double_labeled_cases", "pabak", "kappa",
                           "raw_agreement"}
    assert result == {"double_labeled_cases": 4, "pabak": 0.5, "kappa": 0.5,
                      "raw_agreement": 0.75}
    # the launch criteria engine's own input assembly agrees, byte for byte
    assert result == launch.labels_result(
        {"annotations": session["annotations"]})


# -- calibration: measured time per case, and the guide stub -----------------

def test_calibration_measures_time_per_case_and_produces_the_guide_stub():
    round = label_workflow.calibration_round(FIXTURES / "calibration.json")
    readings = json.loads(
        (FIXTURES / "calibration.json").read_text(encoding="utf-8"))["readings"]
    total = sum(row["seconds"] for row in readings)
    assert round["cases"] == 20
    assert round["total_seconds"] == total
    assert round["seconds_per_case"] == pytest.approx(total / 20)
    guide = round["guide"]
    assert set(guide["axes"]) == {"a_mechanism", "b_grade_relevance",
                                  "c_pinned_evidence", "d_harm"}
    # the measurement replaces the fifteen-minute assumption
    assert guide["time_per_case_seconds"] == pytest.approx(total / 20)


def test_calibration_refuses_a_round_that_is_not_twenty_cases_or_a_reading_without_seconds(tmp_path):
    readings = [{"case": f"fixture-cal-{n:02d}", "seconds": 600}
                for n in range(1, 20)]
    short = tmp_path / "calibration-short.json"
    short.write_text(json.dumps({"labeler": "fixture-labeler-one",
                                 "readings": readings}), encoding="utf-8")
    with pytest.raises(LabelError) as excinfo:
        label_workflow.calibration_round(short)
    assert "19" in str(excinfo.value)

    readings.append({"case": "fixture-cal-20"})
    broken = tmp_path / "calibration-broken.json"
    broken.write_text(json.dumps({"labeler": "fixture-labeler-one",
                                  "readings": readings}), encoding="utf-8")
    with pytest.raises(LabelError) as excinfo:
        label_workflow.calibration_round(broken)
    assert "seconds" in str(excinfo.value)
