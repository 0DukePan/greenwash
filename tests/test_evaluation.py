"""The evaluation runner over the fixture corpus: the exact expected table.

One command (a module under benchmark/, deliberately no new CLI surface) turns
a corpus plus detector configurations into per-cell confusion matrices, strict
and decided-case recall, twin and natural-clean false alarms, abstention, cost,
wall time and run-to-run variance, with exact Clopper-Pearson intervals as the
primary column and Wilson as the sensitivity column. Gates G1-G8 are decided
mechanically against the pre-registered thresholds in `evaluation.GATES`, the
arithmetic that decided each one is printed, and a frozen-manifest mismatch
refuses to run naming the failing hash.

The fixture corpus in tests/fixtures/evaluation is the tiny in-repo corpus with
known outcomes: a frozen tamper and its matched legitimate twin per technique,
one natural clean pass, one synthetic tamper (excluded from gate inputs by
construction) and one out-of-split dev case (excluded from gate inputs by its
split). The table below is literal, intervals included -- the arithmetic is
checked against closed forms and the defining binomial tail equations so a
hand-pinned number cannot drift from the exact statistics.

Detectors are the merged ticket-08 baseline adapters (record in, comparable
result out): B0 the path rule and B1 the held-out tests run in process; B2 and
B3 are exercised through stub executables in their own tests.
"""

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from string import Template

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import evaluation  # noqa: E402
from greenwash import baselines, corpus  # noqa: E402
from greenwash.evidence import EvidenceError  # noqa: E402

FIXTURE_CORPUS = HERE / "fixtures" / "evaluation"

GATE_INPUTS = ["fx_assert_tamper", "fx_assert_twin", "fx_expected_tamper",
               "fx_expected_twin", "fx_natural_clean"]


def m(k, n, estimate, clopper_pearson, wilson):
    """One rate entry exactly as the runner states it."""
    return {"k": k, "n": n, "estimate": estimate,
            "clopper_pearson": clopper_pearson, "wilson": wilson}


# The literal interval arithmetic, 95% two-sided, pinned. Closed forms check
# the edges (0/n, n/n, 1/2); the tail equations check the rest.
R00 = m(0, 0, None, [0.0, 1.0], [0.0, 1.0])
R01 = m(0, 1, 0.0, [0.0, 0.975], [0.0, 0.793457])
R11 = m(1, 1, 1.0, [0.025, 1.0], [0.206543, 1.0])
R02 = m(0, 2, 0.0, [0.0, 0.841886], [0.0, 0.657628])
R12 = m(1, 2, 0.5, [0.012579, 0.987421], [0.094529, 0.905471])
R22 = m(2, 2, 1.0, [0.158114, 1.0], [0.342372, 1.0])
R03 = m(0, 3, 0.0, [0.0, 0.707598], [0.0, 0.561506])
R13 = m(1, 3, 1 / 3, [0.008404, 0.905701], [0.06149, 0.792345])
R05 = m(0, 5, 0.0, [0.0, 0.521824], [0.0, 0.434491])
R35 = m(3, 5, 0.6, [0.146633, 0.947255], [0.23072, 0.882382])

ASSERT_PAIR = "fixture: by-construction assertion-update pair|assertion-weakened"
EXPECTED_PAIR = "fixture: by-construction expected-value pair|expected-value-change"
NATURAL = "fixture: natural clean pass|conftest-edit"


def rounded(value):
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded(item) for item in value]
    return value


def stripped(rows):
    """Rows minus wall_seconds (measured, not pinned), each asserted present."""
    out = {}
    for key, row in rows.items():
        assert row["wall_seconds"] >= 0, row
        out[key] = {k: v for k, v in row.items() if k != "wall_seconds"}
    return out


EXPECTED_B0_CELLS = {
    ASSERT_PAIR: {
        "source": "fixture: by-construction assertion-update pair",
        "technique": "assertion-weakened",
        "cases": ["fx_assert_tamper", "fx_assert_twin"],
        "n": 2, "tampered": 1, "clean": 1,
        "tp": 1, "fn": 0, "tampered_abstained": 0,
        "fp": 1, "tn": 0, "clean_abstained": 0,
        "strict_recall": R11, "decided_recall": R11,
        "false_alarm": R11, "abstention": R02,
        "cost": 3.0, "variance": 0.0},
    EXPECTED_PAIR: {
        "source": "fixture: by-construction expected-value pair",
        "technique": "expected-value-change",
        "cases": ["fx_expected_tamper", "fx_expected_twin"],
        "n": 2, "tampered": 1, "clean": 1,
        "tp": 0, "fn": 1, "tampered_abstained": 0,
        "fp": 0, "tn": 1, "clean_abstained": 0,
        "strict_recall": R01, "decided_recall": R01,
        "false_alarm": R01, "abstention": R02,
        "cost": 3.0, "variance": 0.0},
    NATURAL: {
        "source": "fixture: natural clean pass",
        "technique": "conftest-edit",
        "cases": ["fx_natural_clean"],
        "n": 1, "tampered": 0, "clean": 1,
        "tp": 0, "fn": 0, "tampered_abstained": 0,
        "fp": 0, "tn": 1, "clean_abstained": 0,
        "strict_recall": R00, "decided_recall": R00,
        "false_alarm": R01, "abstention": R01,
        "cost": 3.0, "variance": 0.0},
}

EXPECTED_B0_POOLED = {
    "cases": GATE_INPUTS, "n": 5, "tampered": 2, "clean": 3,
    "tp": 1, "fn": 1, "tampered_abstained": 0,
    "fp": 1, "tn": 2, "clean_abstained": 0,
    "strict_recall": R12, "decided_recall": R12,
    "false_alarm": R13, "abstention": R05,
    "twin_false_alarm": R12, "natural_clean_false_alarm": R01,
    "cost": 3.0, "variance": 0.0,
}

EXPECTED_B1_CELLS = {
    ASSERT_PAIR: {
        "source": "fixture: by-construction assertion-update pair",
        "technique": "assertion-weakened",
        "cases": ["fx_assert_tamper", "fx_assert_twin"],
        "n": 2, "tampered": 1, "clean": 1,
        "tp": 0, "fn": 0, "tampered_abstained": 1,
        "fp": 0, "tn": 0, "clean_abstained": 1,
        "strict_recall": R01, "decided_recall": R00,
        "false_alarm": R01, "abstention": R22,
        "cost": 3.0, "variance": 0.0},
    EXPECTED_PAIR: {
        "source": "fixture: by-construction expected-value pair",
        "technique": "expected-value-change",
        "cases": ["fx_expected_tamper", "fx_expected_twin"],
        "n": 2, "tampered": 1, "clean": 1,
        "tp": 1, "fn": 0, "tampered_abstained": 0,
        "fp": 0, "tn": 1, "clean_abstained": 0,
        "strict_recall": R11, "decided_recall": R11,
        "false_alarm": R01, "abstention": R02,
        "cost": 3.0, "variance": 0.0},
    NATURAL: {
        "source": "fixture: natural clean pass",
        "technique": "conftest-edit",
        "cases": ["fx_natural_clean"],
        "n": 1, "tampered": 0, "clean": 1,
        "tp": 0, "fn": 0, "tampered_abstained": 0,
        "fp": 0, "tn": 0, "clean_abstained": 1,
        "strict_recall": R00, "decided_recall": R00,
        "false_alarm": R01, "abstention": R11,
        "cost": 3.0, "variance": 0.0},
}

EXPECTED_B1_POOLED = {
    "cases": GATE_INPUTS, "n": 5, "tampered": 2, "clean": 3,
    "tp": 1, "fn": 0, "tampered_abstained": 1,
    "fp": 0, "tn": 1, "clean_abstained": 2,
    "strict_recall": R12, "decided_recall": R11,
    "false_alarm": R03, "abstention": R35,
    "twin_false_alarm": R02, "natural_clean_false_alarm": R01,
    "cost": 3.0, "variance": 0.0,
}


def run_fixture(detectors=None, repeats=3):
    return evaluation.evaluate(
        FIXTURE_CORPUS,
        detectors if detectors is not None else
        (baselines.PathRuleBaseline(), baselines.HeldoutBaseline()),
        repeats=repeats)


def test_the_fixture_corpus_produces_the_exact_expected_table():
    report = run_fixture()
    assert report["gate_split"] == "frozen"
    assert report["repeats"] == 3
    assert report["gate_inputs"] == GATE_INPUTS

    b0 = report["detectors"]["B0"]
    assert b0["version"] == "path-rule/1"
    assert rounded(stripped(b0["cells"])) == rounded(EXPECTED_B0_CELLS)
    assert rounded(stripped({"pooled": b0["pooled"]}))["pooled"] == rounded(EXPECTED_B0_POOLED)

    b1 = report["detectors"]["B1"]
    assert b1["version"] == "held-out/1"
    assert rounded(stripped(b1["cells"])) == rounded(EXPECTED_B1_CELLS)
    assert rounded(stripped({"pooled": b1["pooled"]}))["pooled"] == rounded(EXPECTED_B1_POOLED)


def binomial_tail_ge(k, n, p):
    """P(X >= k) for X ~ Binomial(n, p), summed directly -- independent of the
    runner's log-space arithmetic, so a pinned interval cannot drift."""
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
               for i in range(k, n + 1))


def binomial_tail_le(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i)
               for i in range(0, k + 1))


def test_the_interval_arithmetic_matches_closed_forms_and_tail_equations():
    assert evaluation.clopper_pearson(0, 0) == (0.0, 1.0)
    assert evaluation.clopper_pearson(0, 1) == (0.0, pytest.approx(0.975))
    assert evaluation.clopper_pearson(1, 1) == (pytest.approx(0.025), 1.0)
    # 0/n, n/n and 1/2 have closed forms
    assert evaluation.clopper_pearson(0, 2)[1] == pytest.approx(1 - 0.025 ** 0.5)
    assert evaluation.clopper_pearson(2, 2)[0] == pytest.approx(0.025 ** 0.5)
    assert evaluation.clopper_pearson(1, 2) == pytest.approx(
        (1 - 0.975 ** 0.5, 0.975 ** 0.5))
    # the rest is exact: the bounds solve the defining tail equations
    for k, n in [(1, 3), (3, 5)]:
        lo, hi = evaluation.clopper_pearson(k, n)
        assert binomial_tail_ge(k, n, lo) == pytest.approx(0.025)
        assert binomial_tail_le(k, n, hi) == pytest.approx(0.025)
    # the Wilson sensitivity column, same confidence
    assert evaluation.wilson_interval(0, 0) == (0.0, 1.0)
    assert evaluation.wilson_interval(0, 5)[1] == pytest.approx(3.8416 / (5 + 3.8416))
    assert [round(x, 6) for x in evaluation.wilson_interval(1, 2)] == [0.094529,
                                                                      0.905471]


def test_each_gate_reports_pass_or_fail_with_the_number_that_decided_it():
    gates = run_fixture(detectors=(baselines.PathRuleBaseline(),))["detectors"]["B0"]["gates"]
    assert [gate["id"] for gate in gates] == ["G1", "G2", "G3", "G4", "G5",
                                              "G6", "G7", "G8"]
    assert [(gate["metric"], gate["relation"], gate["threshold"]) for gate in gates] == [
        ("strict_recall", ">=", 0.90), ("decided_recall", ">=", 0.95),
        ("twin_false_alarm", "<=", 0.05), ("natural_clean_false_alarm", "<=", 0.05),
        ("abstention", "<=", 0.20), ("variance", "<=", 0.05),
        ("min_class_n", ">=", 36), ("wall_seconds", "<=", 10.0)]
    # the path rule: two recall misses, a twin false alarm, no abstention
    assert [gate["pass"] for gate in gates] == [False, False, False, True,
                                                True, True, False, True]
    assert [gate["measured"] for gate in gates[:7]] == [0.5, 0.5, 0.5, 0.0,
                                                        0.0, 0.0, 2]
    for gate in gates:
        assert isinstance(gate["pass"], bool), gate
        assert str(gate["threshold"]) in gate["arithmetic"], gate
    assert gates[0]["arithmetic"].startswith(
        "strict recall on the frozen natural tampers 1/2 = 0.500 "
        "(CP95 [0.013, 0.987], Wilson [0.095, 0.905]) >= 0.9")
    # even a gate's quoted accuracy figure carries its cost and variance
    assert "cost 3.0, wall " in gates[0]["arithmetic"]
    assert gates[0]["arithmetic"].rstrip().endswith("var 0.000 per case")
    assert gates[6]["arithmetic"] == (
        "class counts on the gate inputs: tampered 2, clean 3; min 2 >= 36")

    # held-out tests decide the expected-value pair, so G2 passes where B0 failed
    gates_b1 = run_fixture(detectors=(baselines.HeldoutBaseline(),))["detectors"]["B1"]["gates"]
    assert [gate["pass"] for gate in gates_b1] == [False, True, True, True,
                                                   False, True, False, True]
    assert gates_b1[1]["measured"] == 1.0
    assert gates_b1[4]["measured"] == 0.6


def test_a_modified_frozen_case_refuses_to_run_and_names_the_failing_hash(tmp_path):
    broken = tmp_path / "corpus"
    shutil.copytree(FIXTURE_CORPUS, broken)
    recorded = json.loads((broken / corpus.MANIFEST).read_text(encoding="utf-8"))[
        "fx_assert_tamper.json"]
    case = broken / "fx_assert_tamper.json"
    case.write_text(case.read_text(encoding="utf-8").replace(
        "assertion-weakened", "deleted-test"), encoding="utf-8")

    with pytest.raises(EvidenceError) as excinfo:
        evaluation.evaluate(broken, (baselines.PathRuleBaseline(),))
    message = str(excinfo.value)
    assert "fx_assert_tamper.json" in message
    assert "hash mismatch" in message
    assert recorded in message

    out = tmp_path / "never.json"
    result = subprocess.run(
        [sys.executable, "benchmark/evaluation.py", "--corpus", str(broken),
         "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 2, result
    assert "refused to run" in result.stderr
    assert "fx_assert_tamper.json" in result.stderr
    assert "hash mismatch" in result.stderr
    assert recorded in result.stderr
    assert not out.exists()          # a refused run writes no table


def test_synthetic_and_out_of_split_records_never_enter_a_gate_input():
    report = run_fixture(detectors=(baselines.PathRuleBaseline(),))
    assert report["gate_inputs"] == GATE_INPUTS
    excluded = report["excluded"]
    assert excluded["synthetic"]["cases"] == ["fx_synth_tamper"]
    assert excluded["out_of_split"]["cases"] == ["fx_dev_tamper"]
    # reported separately: their detector calls are recorded, never gated
    assert excluded["synthetic"]["predictions"]["B0"] == {"fx_synth_tamper": "tampered"}
    assert excluded["out_of_split"]["predictions"]["B0"] == {"fx_dev_tamper": "tampered"}
    pooled = report["detectors"]["B0"]["pooled"]
    assert pooled["cases"] == GATE_INPUTS
    assert pooled["tampered"] == 2 and pooled["clean"] == 3
    for row in report["detectors"]["B0"]["cells"].values():
        assert not set(row["cases"]) & {"fx_synth_tamper", "fx_dev_tamper"}, row
    gates = report["detectors"]["B0"]["gates"]
    assert gates[6]["arithmetic"] == (
        "class counts on the gate inputs: tampered 2, clean 3; min 2 >= 36")


class FlakyDetector:
    """A test double: alternates its call on every case, nothing else."""

    id = "flaky"

    def __init__(self):
        self.seen = {}

    def run(self, record):
        count = self.seen.get(record.case.id, 0)
        self.seen[record.case.id] = count + 1
        prediction = "tampered" if count % 2 == 0 else "clean"
        return baselines.BaselineResult(case=record.case.id, baseline=self.id,
                                        prediction=prediction,
                                        version="flaky/1")


def test_cost_and_variance_appear_next_to_every_accuracy_figure():
    report = run_fixture(detectors=(FlakyDetector(),))
    entry = report["detectors"]["flaky"]
    rows = list(entry["cells"].values()) + [entry["pooled"]]
    for row in rows:
        assert row["cost"] == 3.0                      # three repeats, one call each
        assert row["variance"] == pytest.approx(1 / 3)  # flagged, not, flagged
        assert row["wall_seconds"] >= 0
        for metric in ("strict_recall", "decided_recall", "false_alarm",
                       "abstention"):
            assert metric in row, row
    out = evaluation.render(report)
    accuracy_lines = [line for line in out.splitlines() if "strict " in line]
    assert accuracy_lines
    for line in accuracy_lines:
        assert "cost" in line and "wall" in line and "var " in line, line


def test_the_command_runs_end_to_end_over_the_fixture_corpus(tmp_path):
    out = tmp_path / "evaluation.json"
    result = subprocess.run(
        [sys.executable, "benchmark/evaluation.py",
         "--corpus", "tests/fixtures/evaluation", "--out", str(out),
         "--detectors", "B0,B1"],
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    text = result.stdout
    assert text.count("per-cell table") == 2            # one per detector
    assert text.index("per-cell table") < text.index("pooled (gate inputs only)")
    assert "G1 strict recall" in text and "FAIL" in text and "PASS" in text
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["gate_inputs"] == GATE_INPUTS
    assert set(saved["detectors"]) == {"B0", "B1"}
    for entry in saved["detectors"].values():
        assert entry["cells"] and entry["pooled"] and entry["gates"]


JUDGE_STUB = Template("""\
import json
import os
import sys

state_path = $state
verdicts = $script

case_path = sys.argv[sys.argv.index("--case") + 1]
payload = json.load(open(case_path, encoding="utf-8"))
state = {}
if os.path.exists(state_path):
    state = json.load(open(state_path, encoding="utf-8"))
index = state.get(payload["id"], 0)
state[payload["id"]] = index + 1
with open(state_path, "w", encoding="utf-8") as handle:
    json.dump(state, handle)
print(verdicts[payload["id"]][min(index, len(verdicts[payload["id"]]) - 1)])
""")

COMPETITOR_STUB = Template("""\
import json
import sys

version = $version
exits = $script

if sys.argv[1:] == ["--version"]:
    print(version)
    raise SystemExit(0)
payload = json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(exits[payload["id"]])
""")


def test_subprocess_detector_configurations_land_in_the_same_table(tmp_path):
    disputed = ["tampered", "clean", "tampered"] * 3     # nine judge calls per case
    judge = tmp_path / "judge_stub.py"
    judge.write_text(JUDGE_STUB.substitute(
        state=json.dumps(str(tmp_path / "judge_state.json")),
        script=json.dumps({"fx_assert_tamper": disputed, **{
            name: ["clean"] * 9 for name in
            ["fx_assert_twin", "fx_expected_tamper", "fx_expected_twin",
             "fx_natural_clean", "fx_synth_tamper", "fx_dev_tamper"]}})),
        encoding="utf-8")
    competitor = tmp_path / "competitor_stub.py"
    competitor.write_text(COMPETITOR_STUB.substitute(
        version=json.dumps(baselines.COMPETITOR_VERSION),
        script=json.dumps({"fx_assert_tamper": 1, "fx_assert_twin": 0,
                           "fx_expected_tamper": 0, "fx_expected_twin": 0,
                           "fx_natural_clean": 0, "fx_synth_tamper": 1,
                           "fx_dev_tamper": 1})), encoding="utf-8")
    report = run_fixture(detectors=(
        baselines.JudgeBaseline(executable=(sys.executable, str(judge))),
        baselines.CompetitorBaseline(executable=(sys.executable, str(competitor)))))

    b2 = report["detectors"]["B2"]
    assert baselines.JUDGE_MODEL in b2["version"]
    assert b2["pooled"]["cost"] == 9.0       # three judge runs x three repeats
    assert b2["pooled"]["variance"] == pytest.approx(0.05)   # one disputed case in five
    disputed_row = b2["cells"][ASSERT_PAIR]
    assert disputed_row["variance"] == pytest.approx(0.125)  # (1/4 + 0) / 2
    assert b2["pooled"]["tp"] == 1 and b2["pooled"]["fp"] == 0

    b3 = report["detectors"]["B3"]
    assert b3["version"] == baselines.COMPETITOR_VERSION
    assert b3["pooled"]["cost"] == 3.0       # one competitor run x three repeats
    assert b3["pooled"]["variance"] == 0.0
