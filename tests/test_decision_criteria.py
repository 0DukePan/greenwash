"""Decision criteria: one config, one state machine, one decision.

The launch decision must be computable only from data, must use the same
thresholds the documentation states, and must never return LAUNCH while any
criterion is UNMEASURED. These tests pin the boundary values, the degenerate
inputs, the conflicting-cell rule, the small-sample rule, and the docs pin.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import criteria_engine  # noqa: E402
import evaluation  # noqa: E402
import preregistration  # noqa: E402
from claim_ledger import Claim  # noqa: E402

THRESHOLDS = preregistration.load_thresholds(ROOT / "benchmark" / "thresholds.json")
SPEC = (ROOT / "docs" / "specs" / "launch-benchmark.md").read_text(encoding="utf-8")
CASES = ([f"pos{i:03d}" for i in range(100)]
         + [f"twin{i:03d}" for i in range(100)]
         + [f"nat{i:03d}" for i in range(100)])


def entry(k, n, prefix, per_repo=1):
    outcomes = [(f"{prefix}{i // per_repo:03d}", 1 if i < k else 0)
                for i in range(n)]
    return evaluation.rate(outcomes)


def fixture(case_prefixes=("pos", "twin", "nat")):
    pos, twin, nat = case_prefixes
    pooled = {
        "cases": (CASES if case_prefixes == ("pos", "twin", "nat") else []),
        "strict_recall": entry(100, 100, pos),
        "twin_false_alarm": entry(0, 100, twin),
        "natural_clean_false_alarm": entry(0, 100, nat),
        "twin_abstention": entry(0, 100, twin),
        "natural_clean_abstention": entry(0, 100, nat),
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


def decide(f):
    return criteria_engine.evaluate_criteria(
        f["table"], f["record"], f["rows"], f["rebuild_equal"], f["announcement"],
        thresholds=THRESHOLDS)


def crit(decision, cid):
    return next(row for row in decision["criteria"] if row["id"] == cid)


def test_the_fixture_reaches_launch_as_the_control():
    assert decide(fixture())["decision"] == "LAUNCH"


def test_l1_boundary_four_misses_pass_and_five_fail():
    passing = fixture()
    passing["table"]["detectors"]["B1"]["pooled"]["strict_recall"] = entry(96, 100, "pos")
    assert decide(passing)["decision"] == "LAUNCH"

    failing = fixture()
    failing["table"]["detectors"]["B1"]["pooled"]["strict_recall"] = entry(95, 100, "pos")
    decision = decide(failing)
    assert decision["decision"] == "NARROW"
    assert decision["deciding_criterion"] == "L1"


def test_l2_boundary_four_twin_alarms_pass_and_five_fail():
    passing = fixture()
    passing["table"]["detectors"]["B1"]["pooled"]["twin_false_alarm"] = entry(4, 100, "twin")
    assert decide(passing)["decision"] == "LAUNCH"

    failing = fixture()
    failing["table"]["detectors"]["B1"]["pooled"]["twin_false_alarm"] = entry(5, 100, "twin")
    assert decide(failing)["decision"] == "NARROW"
    assert "L2" in decide(failing)["failing_criteria"]


def test_an_empty_dataset_is_unmeasured_and_never_launch():
    f = fixture()
    for key in ("strict_recall", "twin_false_alarm"):
        f["table"]["detectors"]["B1"]["pooled"][key] = evaluation.rate([])
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert "L1" in decision["unmeasured_criteria"]
    assert decision["decision"] != "LAUNCH"


def test_a_malformed_report_is_unmeasured_and_never_launch():
    f = fixture()
    f["table"]["detectors"] = {}
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert decision["unmeasured_criteria"], "no criterion was marked UNMEASURED"
    assert all(row["state"] == criteria_engine.UNMEASURED
               for row in decision["criteria"] if row["id"] in ("L1", "L2"))


def test_conflicting_cells_never_rescue_the_launch_cell():
    """A perfect non-launch detector cell must not change a failing launch cell."""
    f = fixture()
    f["table"]["detectors"]["B1"]["pooled"]["strict_recall"] = entry(95, 100, "pos")
    f["table"]["detectors"]["B9"] = {
        "pooled": {k: v for k, v in f["table"]["detectors"]["B1"]["pooled"].items()},
        "cells": {},
    }
    f["table"]["detectors"]["B9"]["pooled"]["strict_recall"] = entry(100, 100, "pos")
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert decision["launch_configuration"] == "B1"


def test_a_too_small_sample_fails_the_floor():
    f = fixture()
    small = ([f"pos{i:02d}" for i in range(30)] + [f"twin{i:02d}" for i in range(30)]
             + [f"nat{i:02d}" for i in range(30)])
    f["table"]["gate_inputs"] = list(small)
    for key, prefix in (("strict_recall", "pos"), ("twin_false_alarm", "twin"),
                        ("natural_clean_false_alarm", "nat")):
        f["table"]["detectors"]["B1"]["pooled"][key] = entry(30, 30, prefix)
    decision = decide(f)
    assert decision["decision"] == "NARROW"
    assert "L8" in decision["failing_criteria"]


def test_the_config_matches_the_documented_thresholds():
    """thresholds.json and the spec's L-table must state the same numbers."""
    def spec_row(cid):
        for line in SPEC.splitlines():
            if line.startswith(f"| {cid} |"):
                return line
        raise AssertionError(f"the spec has no row for {cid}")

    criteria = THRESHOLDS["criteria"]
    assert criteria["L1"]["value"] == 0.9 and "0.90" in spec_row("L1")
    assert criteria["L2"]["value"] == 0.1 and "0.10" in spec_row("L2")
    assert criteria["L3"]["value"] == 0.2 and "0.20" in spec_row("L3")
    floor = criteria["L8"]["value"]
    row = spec_row("L8")
    assert floor["effective_n_per_class"] == 100 and "100" in row
    assert floor["distinct_repositories_per_class"] == 24 and "24" in row
    assert floor["max_cases_per_repository"] == 5 and "5" in row
    labels = criteria["L9"]["value"]
    assert labels["double_labeled_cases"] == 100 and "100" in spec_row("L9")
    assert labels["pabak"] == 0.7 and "0.70" in spec_row("L9")
