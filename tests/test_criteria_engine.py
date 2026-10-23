"""The launch criteria engine: L1-L9 decided in one place, LAUNCH or NARROW.

One library call turns the computed evaluation table, the pre-registration
record and the claim-ledger rows -- plus the two injected results whose
inputs live elsewhere (the rebuild-equality flag for L6, the
announcement-check result for L7) -- into exactly one decision: LAUNCH when
every criterion holds, NARROW otherwise, with the first failing criterion in
fixed order (L1-L9) and every failing criterion named. The engine reads no
prose and no file outside its named inputs: the thresholds are gate-as-data,
injected or loaded through the path the pre-registration record pins.

The tests below pin the criterion semantics literally: L1 and L2 decide on
the effective-n Clopper-Pearson bound of the launch configuration's rates,
L3 holds the measured abstention rate under its ceiling separately on twins
and on natural clean passes, L4 applies the determinism rule, L5 requires
the integrity suite ran with zero successful modifications, L6 and L7 are
decided from injected results, L8 is the per-class sample floor, and L9 is
the double-labeled count and PABAK. Fail closed everywhere: a missing cell,
an empty class or an unevaluable check fails with reason `not evaluated`,
and a non-launch detector cell never rescues the launch cell.
"""

import json
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import criteria_engine  # noqa: E402
import evaluation  # noqa: E402
import preregistration  # noqa: E402
from claim_ledger import Claim  # noqa: E402
from greenwash.evidence import EvidenceError  # noqa: E402

THRESHOLDS = preregistration.load_thresholds(ROOT / "benchmark" / "thresholds.json")

# The fixture corpus is synthetic on purpose: 300 cases in distinct
# repositories (100 positives, 100 twins, 100 natural clean) with perfect
# outcomes, so every criterion passes and each one can be broken alone.
CASES = ([f"pos{i:03d}" for i in range(100)]
         + [f"twin{i:03d}" for i in range(100)]
         + [f"nat{i:03d}" for i in range(100)])


def entry(k, n, prefix, per_repo=1):
    """One computed-table rate entry over synthetic (repository, counted) pairs,
    built by the merged `evaluation.rate` machinery -- the engine must decide
    on real effective-n intervals, not hand-typed numbers."""
    outcomes = [(f"{prefix}{i // per_repo:03d}", 1 if i < k else 0)
                for i in range(n)]
    return evaluation.rate(outcomes)


def fixture():
    pooled = {
        "cases": list(CASES),
        "strict_recall": entry(100, 100, "pos"),
        "twin_false_alarm": entry(0, 100, "twin"),
        "natural_clean_false_alarm": entry(0, 100, "nat"),
        "twin_abstention": entry(0, 100, "twin"),
        "natural_clean_abstention": entry(0, 100, "nat"),
    }
    return {
        "table": {
            "gate_inputs": list(CASES),
            "detectors": {
                "B1": {"pooled": pooled,
                       "cells": {"src|technique-a": {"technique": "technique-a"}}},
            },
            "determinism": {"byte_differences": 0, "runs": 5,
                            "cases": list(CASES), "techniques": ["technique-a"]},
            "integrity": {"suite_ran": True, "successful_modifications": 0},
            "labels": {"double_labeled_cases": 100, "pabak": 0.80,
                       "kappa": 0.75, "raw_agreement": 0.90},
        },
        "record": {"launch_configuration": "B1",
                   "thresholds_file": str(ROOT / "benchmark" / "thresholds.json")},
        "rows": [Claim(claim="detector-recall", evidence="", status="", allowed="")],
        "rebuild_equal": True,
        "announcement": {"claims_outside_ledger": 0, "claims": ["detector-recall"]},
    }


def decide(f, thresholds=THRESHOLDS):
    return criteria_engine.evaluate_criteria(
        f["table"], f["record"], f["rows"], f["rebuild_equal"], f["announcement"],
        thresholds=thresholds)


def crit(decision, cid):
    return next(row for row in decision["criteria"] if row["id"] == cid)


# -- one place, one decision -------------------------------------------------

def test_all_criteria_passing_yields_launch():
    decision = decide(fixture())
    assert decision["decision"] == "LAUNCH"
    assert decision["deciding_criterion"] is None
    assert decision["failing_criteria"] == []
    assert [row["id"] for row in decision["criteria"]] == [
        "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9"]
    assert decision["launch_configuration"] == "B1"
    assert decision["designed_for"] == evaluation.designed_for_table()


# -- each criterion forced to fail, one at a time -----------------------------

def break_l1(f):
    f["table"]["detectors"]["B1"]["pooled"]["strict_recall"] = entry(95, 100, "pos")


def break_l2(f):
    f["table"]["detectors"]["B1"]["pooled"]["twin_false_alarm"] = entry(5, 100, "twin")


def break_l3_twins(f):
    f["table"]["detectors"]["B1"]["pooled"]["twin_abstention"] = entry(25, 100, "twin")


def break_l3_natural(f):
    f["table"]["detectors"]["B1"]["pooled"]["natural_clean_abstention"] = entry(
        25, 100, "nat")


def break_l4(f):
    f["table"]["determinism"]["byte_differences"] = 3


def break_l5(f):
    f["table"]["integrity"]["successful_modifications"] = 2


def break_l6(f):
    f["rebuild_equal"] = False


def break_l7(f):
    f["announcement"] = {"claims_outside_ledger": 1, "claims": ["detector-recall"]}


def break_l8(f):
    # 100 twins in 20 repositories of 5: the design effect drops the
    # effective n below the floor and the repository count below 24.
    f["table"]["detectors"]["B1"]["pooled"]["twin_false_alarm"] = entry(
        0, 100, "twin", per_repo=5)


def break_l9(f):
    f["table"]["labels"]["double_labeled_cases"] = 99


@pytest.mark.parametrize("break_it, named", [
    (break_l1, "L1"), (break_l2, "L2"), (break_l3_twins, "L3"),
    (break_l3_natural, "L3"), (break_l4, "L4"), (break_l5, "L5"),
    (break_l6, "L6"), (break_l7, "L7"), (break_l8, "L8"), (break_l9, "L9"),
])
def test_each_criterion_failing_alone_yields_narrow_naming_only_it(break_it, named):
    f = fixture()
    break_it(f)
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert decision["deciding_criterion"] == named
    assert decision["failing_criteria"] == [named]
    assert crit(decision, named)["reason"] is None  # evaluated, and failed


def test_several_failing_list_all_and_decide_the_first_in_fixed_order():
    f = fixture()
    break_l7(f)                       # created first on purpose
    break_l3_natural(f)
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert decision["failing_criteria"] == ["L3", "L7"]
    assert decision["deciding_criterion"] == "L3"


# -- fail closed: never a skip, never LAUNCH ---------------------------------

def test_a_missing_launch_cell_is_not_evaluated_and_never_launch():
    f = fixture()
    del f["table"]["detectors"]["B1"]
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert decision["failing_criteria"] == ["L1", "L2", "L3", "L8"]
    for cid in decision["failing_criteria"]:
        assert crit(decision, cid)["reason"] == "not evaluated"


def test_an_empty_class_is_not_evaluated_and_never_launch():
    f = fixture()
    pooled = f["table"]["detectors"]["B1"]["pooled"]
    pooled["twin_false_alarm"] = evaluation.rate([])
    pooled["twin_abstention"] = evaluation.rate([])
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert decision["failing_criteria"] == ["L2", "L3", "L8"]
    for cid in decision["failing_criteria"]:
        assert crit(decision, cid)["reason"] == "not evaluated"


def test_unevaluable_checks_fail_with_reason_not_evaluated():
    f = fixture()
    f["rebuild_equal"] = None
    f["announcement"] = None
    del f["table"]["integrity"]
    del f["table"]["determinism"]
    f["table"]["labels"]["pabak"] = float("nan")
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert decision["failing_criteria"] == ["L4", "L5", "L6", "L7", "L9"]
    for cid in decision["failing_criteria"]:
        assert crit(decision, cid)["reason"] == "not evaluated"
        assert crit(decision, cid)["pass"] is False


def test_a_threshold_that_is_not_a_number_fails_closed():
    f = fixture()
    thresholds = json.loads(json.dumps(THRESHOLDS))
    thresholds["criteria"]["L1"]["value"] = "high"
    decision = decide(f, thresholds=thresholds)
    assert decision["decision"] == "NARROW"
    assert decision["failing_criteria"] == ["L1"]
    assert crit(decision, "L1")["reason"] == "not evaluated"


# -- the launch cell decides alone -------------------------------------------

def test_a_non_launch_cell_passing_does_not_rescue_the_launch_cell():
    f = fixture()
    other = {"pooled": dict(f["table"]["detectors"]["B1"]["pooled"]),
             "cells": f["table"]["detectors"]["B1"]["cells"]}
    f["table"]["detectors"]["B0"] = other          # descriptive, and passing
    break_l1(f)                                    # the launch cell fails
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert decision["failing_criteria"] == ["L1"]


# -- L3: two ceilings, twins and natural clean -------------------------------

def test_abstention_above_the_ceiling_on_twins_fails_l3_by_name():
    f = fixture()
    break_l3_twins(f)
    decision = decide(f)
    assert decision["failing_criteria"] == ["L3"]
    row = crit(decision, "L3")
    assert row["value"]["twins"] == 0.25
    assert row["value"]["natural_clean"] == 0.0


def test_abstention_above_the_ceiling_on_natural_clean_fails_l3_by_name():
    f = fixture()
    break_l3_natural(f)
    decision = decide(f)
    assert decision["failing_criteria"] == ["L3"]
    row = crit(decision, "L3")
    assert row["value"]["natural_clean"] == 0.25
    assert row["value"]["twins"] == 0.0


# -- L6 and L7: injected results, decided here -------------------------------

def test_a_false_rebuild_flag_fails_l6_and_a_failing_announcement_fails_l7():
    f = fixture()
    f["rebuild_equal"] = False
    f["announcement"] = {"claims_outside_ledger": 2, "claims": ["detector-recall"]}
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert decision["failing_criteria"] == ["L6", "L7"]
    assert crit(decision, "L6")["value"] == {"byte_identical_rebuild": False}
    assert crit(decision, "L7")["value"]["claims_outside_ledger"] == 2


def test_an_announcement_claim_that_maps_to_no_ledger_row_fails_l7():
    f = fixture()
    f["announcement"] = {"claims_outside_ledger": 0, "claims": ["never-registered"]}
    decision = decide(f)
    assert decision["failing_criteria"] == ["L7"]
    assert crit(decision, "L7")["value"] == {
        "claims_outside_ledger": 1, "unmapped_claims": 1}


# -- L9: double-labeled count and PABAK -------------------------------------

def test_a_double_labeled_sample_below_the_floor_fails_l9():
    f = fixture()
    break_l9(f)
    decision = decide(f)
    assert decision["failing_criteria"] == ["L9"]
    assert crit(decision, "L9")["value"]["double_labeled_cases"] == 99


def test_pabak_below_its_floor_fails_l9():
    f = fixture()
    f["table"]["labels"]["pabak"] = 0.69
    decision = decide(f)
    assert decision["failing_criteria"] == ["L9"]
    assert crit(decision, "L9")["value"]["pabak"] == 0.69


# -- boundary pins on the gate-deciding interval -----------------------------

def test_boundary_pins_pass_and_fail_at_the_pre_registered_edges():
    f = fixture()
    f["table"]["detectors"]["B1"]["pooled"]["strict_recall"] = entry(96, 100, "pos")
    assert crit(decide(f), "L1")["value"] == pytest.approx(0.9007, abs=5e-4)
    assert crit(decide(f), "L1")["pass"] is True
    f["table"]["detectors"]["B1"]["pooled"]["strict_recall"] = entry(95, 100, "pos")
    assert crit(decide(f), "L1")["value"] == pytest.approx(0.8872, abs=5e-4)
    assert crit(decide(f), "L1")["pass"] is False

    f = fixture()
    f["table"]["detectors"]["B1"]["pooled"]["twin_false_alarm"] = entry(4, 100, "twin")
    assert crit(decide(f), "L2")["value"] == pytest.approx(0.0993, abs=5e-4)
    assert crit(decide(f), "L2")["pass"] is True
    f["table"]["detectors"]["B1"]["pooled"]["twin_false_alarm"] = entry(5, 100, "twin")
    assert crit(decide(f), "L2")["value"] == pytest.approx(0.1128, abs=5e-4)
    assert crit(decide(f), "L2")["pass"] is False

    f = fixture()
    f["table"]["detectors"]["B1"]["pooled"]["strict_recall"] = entry(36, 36, "pos")
    assert crit(decide(f), "L1")["value"] == pytest.approx(0.9026, abs=5e-4)
    assert crit(decide(f), "L1")["pass"] is True
    f["table"]["detectors"]["B1"]["pooled"]["strict_recall"] = entry(35, 35, "pos")
    assert crit(decide(f), "L1")["value"] == pytest.approx(0.89997, abs=5e-4)
    assert crit(decide(f), "L1")["pass"] is False


def test_the_effective_n_interval_decides_not_the_case_level_one():
    f = fixture()
    pooled = f["table"]["detectors"]["B1"]["pooled"]
    pooled["strict_recall"] = entry(96, 100, "pos", per_repo=5)
    row = pooled["strict_recall"]
    assert row["clopper_pearson"][0] >= 0.90          # case-level would pass
    assert row["clopper_pearson_effective"][0] < 0.90  # effective-n fails
    decision = decide(f)
    assert "L1" in decision["failing_criteria"]
    assert crit(decision, "L1")["reason"] is None
    assert crit(decision, "L1")["value"] == pytest.approx(
        row["clopper_pearson_effective"][0])


# -- no prose, no side inputs ------------------------------------------------

def test_the_engine_reads_no_prose_and_no_file_outside_its_inputs(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the engine read a file it must not read")

    monkeypatch.setattr("builtins.open", boom)
    monkeypatch.setattr(Path, "read_bytes", boom)
    monkeypatch.setattr(Path, "read_text", boom)
    f = fixture()
    decision = criteria_engine.evaluate_criteria(
        f["table"], f["record"], f["rows"], f["rebuild_equal"], f["announcement"],
        thresholds=THRESHOLDS)              # gate-as-data injected as data
    assert decision["decision"] == "LAUNCH"


def test_thresholds_load_through_the_pre_registration_record(tmp_path):
    pinned = tmp_path / "thresholds.json"
    pinned.write_text((ROOT / "benchmark" / "thresholds.json").read_text(
        encoding="utf-8"), encoding="utf-8")
    f = fixture()
    f["record"] = {"launch_configuration": "B1", "thresholds_file": str(pinned)}
    decision = criteria_engine.evaluate_criteria(
        f["table"], f["record"], f["rows"], f["rebuild_equal"], f["announcement"])
    assert decision["decision"] == "LAUNCH"


def test_unreadable_gate_data_fails_closed_and_never_launch(tmp_path):
    garbage = tmp_path / "thresholds.json"
    garbage.write_text("not json", encoding="utf-8")
    # The engine swallows exactly this EvidenceError into a fail-closed
    # decision: every criterion `not evaluated`, never a skip, never LAUNCH.
    with pytest.raises(EvidenceError):
        preregistration.load_thresholds(garbage)
    f = fixture()
    f["record"] = {"launch_configuration": "B1", "thresholds_file": str(garbage)}
    decision = criteria_engine.evaluate_criteria(
        f["table"], f["record"], f["rows"], f["rebuild_equal"], f["announcement"])
    assert decision["decision"] == "NARROW"
    assert decision["failing_criteria"] == [
        "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9"]
    assert all(row["reason"] == "not evaluated" for row in decision["criteria"])


def test_the_determinism_rule_accepts_every_case_or_a_covering_sample():
    f = fixture()
    f["table"]["determinism"]["cases"] = list(CASES)[:100]  # stratified sample
    assert decide(f)["failing_criteria"] == []              # 100 cases, all cells
    f["table"]["determinism"]["cases"] = list(CASES)[:99]   # below the floor
    assert decide(f)["failing_criteria"] == ["L4"]
    f["table"]["determinism"]["cases"] = list(CASES)        # every frozen case
    f["table"]["determinism"]["runs"] = 3
    assert decide(f)["failing_criteria"] == ["L4"]
    f["table"]["determinism"]["runs"] = 5
    f["table"]["determinism"]["techniques"] = ["not-a-cell"]  # covers no cell
    f["table"]["determinism"]["cases"] = list(CASES)[:100]
    assert decide(f)["failing_criteria"] == ["L4"]


def test_the_integrity_suite_must_have_run():
    f = fixture()
    f["table"]["integrity"]["suite_ran"] = False
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert decision["failing_criteria"] == ["L5"]
    assert crit(decision, "L5")["reason"] == "not evaluated"
