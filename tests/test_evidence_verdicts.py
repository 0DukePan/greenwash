"""Evidence verdicts, secondary flags, and the fields that sit beside them.

The verdict domain gains `TAMPERED`, `WEAK_VERIFIER` and `CLEAN`. Findings
carry `mechanism` and `grade_relevance` as separate fields, overlapping
findings resolve by TAMPERED > INCONCLUSIVE > WEAK_VERIFIER > CLEAN without
dropping any of them, and the secondary flags live beside the verdict rather
than folded into it. Everything is asserted on the report JSON a user stores
beside a CI run -- the public report seam, at its literal wire values.
"""

import json

from greenwash.domain import (Outcome, Signal, TrustReport, VerificationResult)

PASS = Outcome.PASS.value
FAIL = Outcome.FAIL.value

FLAGS = {"spec_edited": False, "strength_low": False, "edits_listed": False,
         "flaky_original": False, "replay_infra_error": False}


def suite(outcome=PASS, **kwargs):
    return VerificationResult(outcome=outcome, **kwargs)


def finding(evidence_verdict="", mechanism="", grade_relevance="",
            rule_id="expected-value-changed"):
    return Signal(rule_id=rule_id, evidence_verdict=evidence_verdict,
                  mechanism=mechanism, grade_relevance=grade_relevance)


def verdict_of(report):
    return json.loads(report.to_json())["verdict"]


# -- mechanism and grade relevance, as separate fields ------------------------

def test_a_tampering_finding_carries_mechanism_and_grade_relevance_separately():
    report = TrustReport.build(signals=[finding(
        mechanism="the expected value in tests/test_calc.py:4 was rewritten",
        grade_relevance="the rewritten value is what the suite grades")])
    payload = json.loads(report.to_json())
    assert payload["verdict"] == "TAMPERED"
    assert payload["signals"][0]["mechanism"] == \
        "the expected value in tests/test_calc.py:4 was rewritten"
    assert payload["signals"][0]["grade_relevance"] == \
        "the rewritten value is what the suite grades"


def test_tampered_is_never_emitted_without_both_fields():
    """A pattern alone stays INCONCLUSIVE: the tool does not convict on it."""
    partial = [
        finding(evidence_verdict="TAMPERED",
                mechanism="the expected value was rewritten"),
        finding(evidence_verdict="TAMPERED",
                grade_relevance="the rewritten value is what the suite grades"),
        finding(evidence_verdict="TAMPERED"),
    ]
    for signal in partial:
        payload = json.loads(TrustReport.build(verification=suite(),
                                               signals=[signal]).to_json())
        assert payload["verdict"] == "INCONCLUSIVE", signal
        assert payload["verdict"] != "TAMPERED", signal


# -- precedence over overlapping findings -------------------------------------

def test_precedence_resolves_overlapping_findings_and_drops_none():
    overlapping = [
        finding(rule_id="weak-suite", evidence_verdict="WEAK_VERIFIER"),
        finding(rule_id="pattern-only", evidence_verdict="INCONCLUSIVE"),
        finding(rule_id="expected-value-changed",
                mechanism="the expected value was rewritten",
                grade_relevance="the rewritten value is what the suite grades"),
        finding(rule_id="docstring-rewrite", evidence_verdict="CLEAN",
                mechanism="the docstring was rewritten",
                grade_relevance="the docstring states the stated contract"),
    ]
    payload = json.loads(TrustReport.build(verification=suite(),
                                           signals=overlapping).to_json())
    assert payload["verdict"] == "TAMPERED"
    assert [s["rule_id"] for s in payload["signals"]] == [
        "weak-suite", "pattern-only", "expected-value-changed", "docstring-rewrite"]


def test_each_rung_wins_when_it_is_the_highest_standing():
    assert verdict_of(TrustReport.build(verification=suite(), signals=[
        finding(evidence_verdict="WEAK_VERIFIER"),
        finding(evidence_verdict="CLEAN")])) == "WEAK_VERIFIER"
    assert verdict_of(TrustReport.build(verification=suite(), signals=[
        finding(evidence_verdict="INCONCLUSIVE"),
        finding(evidence_verdict="WEAK_VERIFIER")])) == "INCONCLUSIVE"
    assert verdict_of(TrustReport.build(verification=suite(), signals=[
        finding(evidence_verdict="CLEAN")])) == "CLEAN"


def test_a_cleared_finding_does_not_erase_a_standing_pattern():
    payload = json.loads(TrustReport.build(verification=suite(), signals=[
        finding(evidence_verdict="CLEAN"),
        Signal(rule_id="hardcoded-return", severity="HIGH")]).to_json())
    assert payload["verdict"] == "SUSPICIOUS"
    assert len(payload["signals"]) == 2


# -- secondary flags, beside the verdict --------------------------------------

def test_secondary_flags_live_beside_the_verdict_and_never_fold_into_it():
    tampering = [finding(mechanism="the expected value was rewritten",
                         grade_relevance="the rewritten value is what the suite grades")]
    plain = json.loads(TrustReport.build(verification=suite(),
                                         signals=tampering).to_json())
    flagged = json.loads(TrustReport.build(
        verification=suite(), signals=tampering,
        flags={"strength_low": True, "edits_listed": True}).to_json())
    assert plain["verdict"] == flagged["verdict"] == "TAMPERED"
    assert plain["flags"] == FLAGS
    assert flagged["flags"] == dict(FLAGS, strength_low=True, edits_listed=True)


# -- the wire format is stable ------------------------------------------------

def test_the_report_json_is_stable_enough_to_store_beside_a_ci_run():
    report = TrustReport.build(
        verification=suite(),
        signals=[finding(mechanism="the expected value was rewritten",
                         grade_relevance="the rewritten value is what the suite grades")],
        flags={"spec_edited": True})
    payload = json.loads(report.to_json())
    assert list(payload)[0] == "schema_version"
    assert payload["schema_version"] == "1"
    assert json.loads(TrustReport.from_dict(payload).to_json()) == payload


# -- the prefactor lock -------------------------------------------------------

def test_recorded_runs_classify_exactly_as_they_did():
    """Before this change, and after it, these runs answer identically."""
    high = Signal(rule_id="hardcoded-return", severity="HIGH")
    medium = Signal(rule_id="mock-in-test", severity="MEDIUM")
    broken = VerificationResult(outcome=Outcome.UNAVAILABLE.value,
                                harness_error="timed out after 120s")
    assert verdict_of(TrustReport.build(verification=suite(FAIL))) == "NOT_VERIFIED"
    assert verdict_of(TrustReport.build(verification=suite(),
                                        signals=[high])) == "SUSPICIOUS"
    assert verdict_of(TrustReport.build(verification=suite(),
                                        signals=[medium])) == "PARTIALLY_VERIFIED"
    assert verdict_of(TrustReport.build(verification=suite())) == "VERIFIED"
    assert verdict_of(TrustReport.build(verification=VerificationResult())) == "INCONCLUSIVE"
    assert verdict_of(TrustReport.build(verification=broken)) == "VERIFICATION_FAILED"
