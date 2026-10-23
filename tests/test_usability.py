"""The usability kit seam: eight representative outputs, the answer key, and
the scorer that checks the 80 percent target after one wording-fix round.

One seam, `benchmark/usability.py` plus its data file
`benchmark/usability-kit.json`. The acceptance criteria asserted here are the
ticket's, literally: the four-two-two split with all four message parts, an
answer key that decides each interpretation without ambiguity, share correct
and median time from fixture responses, and the target checked only after the
recorded wording round.

Every respondent label below starts with `fixture-`: these rows are invented
fixtures for these tests, never real participant data. The real usability
session is human work under the operator's control and lives outside this
repository.

Everything here is offline: plain dicts and strings, no network, no telemetry.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import usability  # noqa: E402
from greenwash.domain import Evidence, Signal, TrustReport, VerificationResult  # noqa: E402
from greenwash.report import terminal  # noqa: E402


def test_the_kit_is_the_four_two_two_split_with_every_message_part():
    kit = usability.load_kit()
    split = {}
    for sample in kit["samples"]:
        split[sample["verdict"]] = split.get(sample["verdict"], 0) + 1
        assert sample["reason"].strip().endswith("."), sample["id"]
        assert ". " not in sample["reason"], f"{sample['id']}: more than one sentence"
        assert sample["evidence"], sample["id"]
        assert all(line.strip() for line in sample["evidence"]), sample["id"]
        assert sample["next_step"].strip(), sample["id"]
    assert split == {"TAMPERED": 4, "INCONCLUSIVE": 2, "CLEAN": 2}
    assert len(kit["samples"]) == 8
    assert sum(1 for s in kit["samples"]
               if s["verdict"] == "CLEAN" and s.get("note")) == 2


def test_load_kit_refuses_a_sample_without_its_next_step_naming_the_field():
    kit = copy.deepcopy(usability.load_kit())
    del kit["samples"][0]["next_step"]
    with pytest.raises(usability.KitError) as exc:
        usability.validate_kit(kit)
    assert "next_step" in str(exc.value)


# -- the message, and its fidelity to what the tool prints -------------------

# The evidence-line prefixes, exactly as greenwash.report.terminal prints them.
EVIDENCE_PREFIXES = {"Expected: ": "expected", "Observed: ": "observed",
                     "Source:   ": "source", "Command:  ": "command"}


def _norm(text):
    return " ".join(text.split())


def _report(sample):
    """The same content as a TrustReport, to compare against the renderer.

    The reason rides on a signal's explanation for TAMPERED and on the notes
    otherwise; the evidence becomes a real `Evidence` record. If any evidence
    line does not carry the renderer's own prefix, this raises -- the message
    may not invent a shape the tool does not print.
    """
    fields = {}
    for line in sample["evidence"]:
        for prefix, field in EVIDENCE_PREFIXES.items():
            if line.startswith(prefix):
                fields[field] = line[len(prefix):]
                break
        else:
            raise AssertionError(
                f"{sample['id']}: evidence line does not match terminal "
                f"rendering: {line!r}")
    notes = [n for n in (sample["reason"], sample.get("note", "")) if n]
    report = TrustReport.build(
        verification=VerificationResult(evidence=[Evidence(**fields)]),
        signals=([Signal(explanation=sample["reason"])]
                 if sample["verdict"] == "TAMPERED" else []),
        notes=notes)
    report.verdict = sample["verdict"]
    return report


def test_the_message_shows_the_verdict_first_then_reason_evidence_next_step():
    for sample in usability.load_kit()["samples"]:
        lines = usability.message(sample).splitlines()
        assert lines[0] == (f"Verdict: {sample['verdict']} -- "
                            f"{terminal.VERDICT_BLURB[sample['verdict']]}")
        assert lines[1] == f"Reason: {sample['reason']}"
        assert lines[2] == "Evidence:"
        body = lines[3:3 + len(sample["evidence"])]
        assert all(line.startswith("  ") for line in body)
        assert lines[-1] == f"Next step: {sample['next_step']}"
        if sample.get("note"):
            assert f"note: {sample['note']}" in lines


def test_message_content_matches_what_the_tool_prints():
    for sample in usability.load_kit()["samples"]:
        rendered = _norm(terminal.render(_report(sample), color=False))
        message = usability.message(sample)
        assert _norm(message.splitlines()[0]) in rendered, sample["id"]
        for line in [sample["reason"], *sample["evidence"]]:
            assert _norm(line) in rendered, f"{sample['id']}: {line!r}"
        if sample.get("note"):
            assert _norm("note: " + sample["note"]) in rendered, sample["id"]


def test_messages_never_accuse_and_inconclusive_asks_for_evidence():
    for sample in usability.load_kit()["samples"]:
        text = usability.message(sample).lower()
        assert "cheat" not in text, sample["id"]
        if sample["verdict"] == "INCONCLUSIVE":
            assert "evidence" in text, sample["id"]
        if sample["verdict"] == "TAMPERED":
            assert "tests weakened" in text, sample["id"]


# -- the answer key and the scorer -------------------------------------------

# FIXTURE responses. Every respondent label starts with `fixture-`: these rows
# are invented fixtures for these tests and are never real participant data.
# A real session's rows are recorded by the operator, outside this repository.
FIXTURE_ROUND_1 = [
    {"respondent": "fixture-01", "sample": "T1-assertion-weakened",
     "answer": "restore-tests", "seconds": 18, "round": 1},
    {"respondent": "fixture-02", "sample": "T2-test-file-deleted",
     "answer": "restore-tests", "seconds": 22, "round": 1},
    {"respondent": "fixture-03", "sample": "T3-test-skipped",
     "answer": "restore-tests", "seconds": 17, "round": 1},
    {"respondent": "fixture-04", "sample": "T4-hardcoded-return",
     "answer": "supply-evidence", "seconds": 30, "round": 1},
    {"respondent": "fixture-05", "sample": "I1-no-check-run",
     "answer": "supply-evidence", "seconds": 21, "round": 1},
    {"respondent": "fixture-06", "sample": "I2-pinned-evidence-missing",
     "answer": "proceed", "seconds": 16, "round": 1},
    {"respondent": "fixture-07", "sample": "C1-clean-flaky-note",
     "answer": "proceed", "seconds": 27, "round": 1},
    {"respondent": "fixture-08", "sample": "C2-clean-baseline-note",
     "answer": "supply-evidence", "seconds": 24, "round": 1},
]

FIXTURE_ROUND_2 = [
    {"respondent": "fixture-01", "sample": "T1-assertion-weakened",
     "answer": "restore-tests", "seconds": 12, "round": 2},
    {"respondent": "fixture-02", "sample": "T2-test-file-deleted",
     "answer": "restore-tests", "seconds": 20, "round": 2},
    {"respondent": "fixture-03", "sample": "T3-test-skipped",
     "answer": "restore-tests", "seconds": 15, "round": 2},
    {"respondent": "fixture-04", "sample": "T4-hardcoded-return",
     "answer": "restore-tests", "seconds": 18, "round": 2},
    {"respondent": "fixture-05", "sample": "I1-no-check-run",
     "answer": "supply-evidence", "seconds": 9, "round": 2},
    {"respondent": "fixture-06", "sample": "I2-pinned-evidence-missing",
     "answer": "proceed", "seconds": 25, "round": 2},
    {"respondent": "fixture-07", "sample": "C1-clean-flaky-note",
     "answer": "proceed", "seconds": 14, "round": 2},
    {"respondent": "fixture-08", "sample": "C2-clean-baseline-note",
     "answer": "proceed", "seconds": 11, "round": 2},
]


def test_the_answer_key_decides_each_interpretation_without_ambiguity():
    kit = usability.load_kit()
    key = kit["answer_key"]
    expected = {"TAMPERED": "restore-tests", "INCONCLUSIVE": "supply-evidence",
                "CLEAN": "proceed"}
    for sample in kit["samples"]:
        entry = key[sample["id"]]
        assert entry["interpretation"] == expected[sample["verdict"]], sample["id"]
        assert entry["interpretation"] in usability.INTERPRETATIONS
        assert entry["what_happened"].strip(), sample["id"]
        assert entry["reader_action"].strip(), sample["id"]


def test_the_scorer_computes_share_correct_and_median_time_from_fixtures():
    result = usability.score(FIXTURE_ROUND_2)
    assert result["responses"] == 8
    assert result["correct"] == 7
    assert result["share_correct"] == 0.875
    assert result["median_seconds"] == 14.5


def test_the_scorer_refuses_a_row_it_cannot_read_naming_the_field():
    broken = [
        ("sample", lambda r: r.update(sample="X-not-in-the-kit")),
        ("answer", lambda r: r.update(answer="merge-anyway")),
        ("seconds", lambda r: r.update(seconds=0)),
        ("round", lambda r: r.update(round=3)),
        ("respondent", lambda r: r.update(respondent="")),
    ]
    for field, break_row in broken:
        rows = [dict(row) for row in FIXTURE_ROUND_2]
        break_row(rows[0])
        with pytest.raises(usability.KitError) as exc:
            usability.score(rows)
        assert f"response.{field}" in str(exc.value), field
    with pytest.raises(usability.KitError) as exc:
        usability.score([])
    assert "responses" in str(exc.value)


# -- the wording-fix round and the target ------------------------------------

def test_the_wording_revision_round_is_recorded_with_both_wordings():
    kit = usability.load_kit()
    ids = {sample["id"] for sample in kit["samples"]}
    wording = kit["wording_round"]
    assert wording["applied_after_round"] == 1
    assert wording["changes"]
    for change in wording["changes"]:
        assert change["sample"] in ids
        assert change["was"] != change["now"]
        assert change["was"].strip() and change["now"].strip()
        assert "cheat" not in change["was"].lower()


def test_the_target_is_checked_after_the_wording_fix_round():
    result = usability.check_target(FIXTURE_ROUND_2)
    assert result["target"] == 0.80
    assert result["share_correct"] == 0.875
    assert result["median_seconds"] == 14.5
    assert result["met"] is True


def test_the_target_is_never_checked_before_the_wording_fix_round():
    # round 1 predates the wording fix: those rows are scored, never checked
    with pytest.raises(usability.KitError) as exc:
        usability.check_target(FIXTURE_ROUND_1)
    assert "response.round" in str(exc.value)
    round_one = usability.score(FIXTURE_ROUND_1)
    assert round_one["share_correct"] == 0.625
    assert round_one["median_seconds"] == 21.5
    # and with no wording round recorded there is no target check at all
    kit = copy.deepcopy(usability.load_kit())
    del kit["wording_round"]
    with pytest.raises(usability.KitError) as exc:
        usability.check_target(FIXTURE_ROUND_2, kit)
    assert "wording_round" in str(exc.value)


def test_the_kit_carries_no_user_data_and_the_scorer_makes_no_network_calls():
    raw = usability.DEFAULT_KIT.read_text(encoding="utf-8")
    kit = json.loads(raw)
    assert "responses" not in kit
    assert "respondent" not in raw
    source = Path(usability.__file__).read_text(encoding="utf-8")
    for importer in ("import urllib", "import socket", "import requests",
                     "import http", "import telemetry"):
        assert importer not in source, importer
