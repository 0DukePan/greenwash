"""The Gate A report over the development split: three fixture dev runs,
two refusal paths, and the machine summary beside the report.

One seam, `benchmark/gate_a.py`, driven at its public functions and its
command. The fixture dev runs under tests/fixtures/gate_a/ are tiny dev
splits with known arithmetic: 6 positives (tasks gtask-p1..p6), 8 matched
twins (clean, sharing the positives' tasks), 4 natural clean passes, all
labeled and split "dev". Each outcome directory is a complete dev run:
the dev evaluation table, the labelled dev cases, the baseline results
(B0/B1/B2/B3 as the adapters compute them) and an assumptions register.

The acceptance criteria of .scratch/validation-program/issues/06, each
one literal here:

* a fixture dev run yields go, pivot and stop under the three registered
  conditions (go: H2 confirmed and H3 holds with abstention at or below
  0.20; pivot: Greenwash and the pinned competitor indistinguishable at
  the fixed n; stop: recall clearly lower or abstention above 0.20);
* the report names each hypothesis, its numbers, and the deciding
  threshold;
* any frozen record in the input refuses the run, naming it;
* an open assumption in the register refuses the run, naming it;
* the machine summary matches the report and contains no prose verdict.

The exact McNemar and rate numbers below are checked against closed
forms, so a hand-pinned number cannot drift from the statistics.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import gate_a  # noqa: E402

FIXTURES = HERE / "fixtures" / "gate_a"


def load(name):
    """One fixture dev run as the four inputs the seam consumes."""
    base = FIXTURES / name
    read = lambda fname: json.loads((base / fname).read_text(encoding="utf-8"))
    return (read("dev-table.json"), read("labelled.json"),
            read("baselines.json"), read("assumptions.json"))


def decide(name):
    return gate_a.gate_a(*load(name))


# -- the three registered outcomes -------------------------------------------

def test_go_fixture_dev_run_yields_go_with_every_hypothesis_number():
    record = decide("go")
    assert record["decision"] == "go"
    assert record["deciding_threshold"] == "go-confirmed"
    assert record["split"] == "dev"
    assert record["counts"] == {"positives": 6, "twins": 8, "natural_clean": 4}
    assert record["fixed_n"] == 8
    h1 = record["hypotheses"]["H1"]
    assert h1["status"] == "confirmed"
    assert h1["recall_greenwash"] == {"k": 6, "n": 6, "estimate": 1.0}
    assert h1["recall_judge"] == {"k": 6, "n": 6, "estimate": 1.0}
    assert h1["recall_gap"] == 0.0
    assert h1["cost_per_case_greenwash"] == 1.0
    assert h1["cost_per_case_judge"] == 30.0
    assert h1["cost_ratio"] == 30.0
    assert h1["variance_greenwash"] == 0.0 and h1["variance_judge"] == 0.0
    assert h1["variance_reported"] is True
    h2 = record["hypotheses"]["H2"]
    assert h2["status"] == "confirmed"
    assert h2["twin_false_alarm_greenwash"] == {"k": 0, "n": 8, "estimate": 0.0}
    assert h2["twin_false_alarm_b0"] == {"k": 8, "n": 8, "estimate": 1.0}
    assert h2["discordant"] == {"greenwash_only": 0, "b0_only": 8}
    assert h2["mcnemar_p"] == pytest.approx(2 / 256)      # 2 * (1/2)^8
    h3 = record["hypotheses"]["H3"]
    assert h3["status"] == "holds"
    assert h3["twin_false_alarm_b3"] == {"k": 6, "n": 8, "estimate": 0.75}
    assert h3["twin_edge_gap"] == pytest.approx(0.75)
    assert h3["abstention"] == {"k": 0, "n": 18, "estimate": 0.0}
    h0 = record["hypotheses"]["H0"]
    assert h0["status"] == "distinguishable"
    assert h0["discordant"] == {"greenwash_only": 0, "b3_only": 6}
    assert h0["mcnemar_p"] == pytest.approx(2 / 64)       # 2 * (1/2)^6


def test_pivot_fixture_dev_run_yields_pivot_when_competitor_indistinguishable():
    record = decide("pivot")
    assert record["decision"] == "pivot"
    assert record["deciding_threshold"] == "pivot-indistinguishable"
    h0 = record["hypotheses"]["H0"]
    assert h0["status"] == "indistinguishable"
    assert h0["mcnemar_p"] == pytest.approx(1.0)          # 0 discordant pairs
    h3 = record["hypotheses"]["H3"]
    assert h3["status"] == "not-holds"
    assert h3["twin_edge_gap"] == pytest.approx(0.0)
    h2 = record["hypotheses"]["H2"]
    assert h2["status"] == "confirmed"
    assert h2["discordant"] == {"greenwash_only": 0, "b0_only": 6}
    assert h2["mcnemar_p"] == pytest.approx(2 / 64)


def test_stop_fixture_dev_run_yields_stop_when_abstention_above_ceiling():
    record = decide("stop-abstention")
    assert record["decision"] == "stop"
    assert record["deciding_threshold"] == "stop-abstention"
    h3 = record["hypotheses"]["H3"]
    assert h3["abstention"] == {"k": 4, "n": 18, "estimate": pytest.approx(4 / 18)}
    assert h3["abstention"]["estimate"] > 0.20


def test_stop_fixture_dev_run_yields_stop_when_recall_clearly_lower():
    record = decide("stop-recall")
    assert record["decision"] == "stop"
    assert record["deciding_threshold"] == "stop-recall"
    h1 = record["hypotheses"]["H1"]
    assert h1["recall_greenwash"] == {"k": 3, "n": 6, "estimate": 0.5}
    assert h1["recall_judge"] == {"k": 6, "n": 6, "estimate": 1.0}
    assert h1["recall_gap"] == pytest.approx(-0.5)
    assert h1["status"] == "partial"        # the cost edge alone is partial


# -- the two refusal paths ---------------------------------------------------

def test_any_frozen_record_in_the_input_refuses_the_run_naming_it():
    with pytest.raises(gate_a.GateAError) as excinfo:
        decide("frozen-record")
    message = str(excinfo.value)
    assert "gtwin-01" in message
    assert "frozen" in message


def test_an_open_assumption_in_the_register_refuses_the_run_naming_it():
    with pytest.raises(gate_a.GateAError) as excinfo:
        decide("open-assumption")
    message = str(excinfo.value)
    assert "speed-slos" in message
    assert "open" in message


def test_the_shipped_register_refuses_only_on_the_assumptions_gate_a_consumes():
    register = json.loads(
        (ROOT / "benchmark" / "assumptions.json").read_text(encoding="utf-8"))
    with pytest.raises(gate_a.GateAError) as excinfo:
        gate_a.gate_a(*load("go")[:3], register)
    message = str(excinfo.value)
    assert "labeling-time-per-case" in message
    assert "competitor-overhead-figures" in message
    assert "speed-slos" not in message, (
        "a Stage 5 speed target must not block Gate A")


def test_a_missing_field_is_a_refusal_naming_the_field():
    dev_table, labelled, baselines, assumptions = load("go")
    del baselines["results"][3]["cost"]
    with pytest.raises(gate_a.GateAError) as excinfo:
        gate_a.gate_a(dev_table, labelled, baselines, assumptions)
    assert "cost" in str(excinfo.value)


# -- the report and the machine summary -------------------------------------

def test_report_prints_each_hypothesis_with_its_numbers_and_threshold():
    record = decide("go")
    text = gate_a.render(record)
    for line_id in ("H1", "H2", "H3", "H0"):
        assert line_id in text
    assert "6/6" in text and "0/8" in text and "6/8" in text   # the numbers
    assert "margin -0.100" in text                             # H1 threshold
    assert "McNemar alpha 0.05" in text                        # H2/H0 threshold
    assert "twin edge 0.100" in text                           # H3 threshold
    assert "abstention 0/18=0.000 <= 0.200" in text
    assert "decision: go" in text
    assert "go-confirmed" in text                              # the deciding threshold


def test_machine_summary_matches_the_report_and_contains_no_prose_verdict():
    record = decide("go")
    summary = gate_a.summary(record)
    assert summary["decision"] == "go"                         # exactly go/pivot/stop
    assert summary["decision"] in ("go", "pivot", "stop")
    assert summary["decision"] == record["decision"]
    assert "decision: go" in gate_a.render(record)
    strings = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                strings.append(key)
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            strings.append(node)

    walk(summary)
    assert strings
    # No prose verdict: every string is a whitespace-free token or key.
    assert all(not any(char.isspace() for char in s) for s in strings)
    assert summary["deciding_threshold"] == "go-confirmed"


@pytest.mark.parametrize("name", ["go", "pivot", "stop-abstention", "stop-recall"])
def test_summary_decision_is_one_of_the_three_outcomes_for_every_fixture(name):
    summary = gate_a.summary(decide(name))
    assert summary["decision"] in ("go", "pivot", "stop")


# -- the command: the report file and the summary beside it ------------------

def run_main(arguments):
    return subprocess.run(
        [sys.executable, "benchmark/gate_a.py", *arguments],
        cwd=ROOT, capture_output=True, text=True)


def test_the_command_writes_the_report_and_the_machine_summary_beside_it(tmp_path):
    base = FIXTURES / "go"
    out = tmp_path / "gate_a_report.txt"
    result = run_main([
        "--dev", str(base / "dev-table.json"),
        "--labelled", str(base / "labelled.json"),
        "--baselines", str(base / "baselines.json"),
        "--assumptions", str(base / "assumptions.json"),
        "--out", str(out)])
    assert result.returncode == 0
    report = out.read_text(encoding="utf-8")
    assert "decision: go" in report
    summary_path = gate_a.summary_path(out)
    assert summary_path.parent == out.parent                  # beside the report
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["decision"] == "go"


def test_the_command_refuses_a_frozen_record_naming_it(tmp_path):
    base = FIXTURES / "frozen-record"
    out = tmp_path / "gate_a_report.txt"
    result = run_main([
        "--dev", str(base / "dev-table.json"),
        "--labelled", str(base / "labelled.json"),
        "--baselines", str(base / "baselines.json"),
        "--assumptions", str(base / "assumptions.json"),
        "--out", str(out)])
    assert result.returncode == 2
    assert "gtwin-01" in result.stderr
    assert not out.exists()


def test_the_command_refuses_an_open_assumption_naming_it(tmp_path):
    base = FIXTURES / "open-assumption"
    out = tmp_path / "gate_a_report.txt"
    result = run_main([
        "--dev", str(base / "dev-table.json"),
        "--labelled", str(base / "labelled.json"),
        "--baselines", str(base / "baselines.json"),
        "--assumptions", str(base / "assumptions.json"),
        "--out", str(out)])
    assert result.returncode == 2
    assert "speed-slos" in result.stderr
    assert not out.exists()
