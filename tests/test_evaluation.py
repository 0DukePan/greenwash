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


def m(k, n, estimate, clopper_pearson, wilson, n_repos, cluster_sizes,
      rho_hat, rho_used, deff, n_eff, k_eff, effective):
    """One rate entry exactly as the runner states it.

    Every rate carries its repository clustering beside both interval
    columns: the cluster sizes, the ANOVA intraclass-correlation estimate,
    the floor-adjusted rho, the design effect, the effective counts, and the
    exact interval at those effective counts -- the gate-deciding column.
    """
    return {"k": k, "n": n, "estimate": estimate,
            "clopper_pearson": clopper_pearson, "wilson": wilson,
            "n_repos": n_repos, "cluster_sizes": cluster_sizes,
            "rho_hat": rho_hat, "rho_used": rho_used, "deff": deff,
            "n_eff": n_eff, "k_eff": k_eff,
            "clopper_pearson_effective": effective}


def unclustered(k, n, estimate, clopper_pearson, wilson, n_repos):
    """A rate whose cases sit in distinct repositories: no clustering is
    estimable (rho_hat 0.0), the floor 0.05 applies, m-bar is 1 so the design
    effect is 1.0, and the effective counts equal the case counts."""
    return m(k, n, estimate, clopper_pearson, wilson,
             n_repos, [1] * n_repos, 0.0, 0.05, 1.0, float(n), float(k),
             clopper_pearson)


# The literal interval arithmetic, 95% two-sided, pinned. Closed forms check
# the edges (0/n, n/n, 1/2); the tail equations check the rest.
R00 = unclustered(0, 0, None, [0.0, 1.0], [0.0, 1.0], 0)
R01 = unclustered(0, 1, 0.0, [0.0, 0.975], [0.0, 0.793457], 1)
R11 = unclustered(1, 1, 1.0, [0.025, 1.0], [0.206543, 1.0], 1)
R02 = unclustered(0, 2, 0.0, [0.0, 0.841886], [0.0, 0.657628], 2)
R12 = unclustered(1, 2, 0.5, [0.012579, 0.987421], [0.094529, 0.905471], 2)
R03 = unclustered(0, 3, 0.0, [0.0, 0.707598], [0.0, 0.561506], 3)
R13 = unclustered(1, 3, 1 / 3, [0.008404, 0.905701], [0.06149, 0.792345], 3)

# Clustered literals: a pair cell keeps both its cases in one repository, and
# the pooled abstention rate spans all five gate inputs in three repositories.
# m-bar is 2 or 1.8, so the floor rho alone inflates the pair cells (DEFF
# 1.05), and the pooled abstention on B1 is perfectly clustered by
# repository (rho_hat 1.0, DEFF 1.8).
R02_ONE_REPO = m(0, 2, 0.0, [0.0, 0.841886], [0.0, 0.657628],
                1, [2], 0.0, 0.05, 1.05, 2 / 1.05, 0.0, [0.0, 0.855816])
R22_ONE_REPO = m(2, 2, 1.0, [0.158114, 1.0], [0.342372, 1.0],
                1, [2], 0.0, 0.05, 1.05, 2 / 1.05, 2 / 1.05, [0.144184, 1.0])
R05_CLUSTERED = m(0, 5, 0.0, [0.0, 0.521824], [0.0, 0.434491],
                 3, [1, 2, 2], 0.0, 0.05, 1.04, 5 / 1.04, 0.0, [0.0, 0.535729])
R35_CLUSTERED = m(3, 5, 0.6, [0.146633, 0.947255], [0.23072, 0.882382],
                 3, [1, 2, 2], 1.0, 1.0, 1.8, 5 / 1.8, 3 / 1.8,
                 [0.059345, 0.985923])

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
        "false_alarm": R11, "abstention": R02_ONE_REPO,
        "cost": 3.0, "variance": 0.0},
    EXPECTED_PAIR: {
        "source": "fixture: by-construction expected-value pair",
        "technique": "expected-value-change",
        "cases": ["fx_expected_tamper", "fx_expected_twin"],
        "n": 2, "tampered": 1, "clean": 1,
        "tp": 0, "fn": 1, "tampered_abstained": 0,
        "fp": 0, "tn": 1, "clean_abstained": 0,
        "strict_recall": R01, "decided_recall": R01,
        "false_alarm": R01, "abstention": R02_ONE_REPO,
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
    "false_alarm": R13, "abstention": R05_CLUSTERED,
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
        "false_alarm": R01, "abstention": R22_ONE_REPO,
        "cost": 3.0, "variance": 0.0},
    EXPECTED_PAIR: {
        "source": "fixture: by-construction expected-value pair",
        "technique": "expected-value-change",
        "cases": ["fx_expected_tamper", "fx_expected_twin"],
        "n": 2, "tampered": 1, "clean": 1,
        "tp": 1, "fn": 0, "tampered_abstained": 0,
        "fp": 0, "tn": 1, "clean_abstained": 0,
        "strict_recall": R11, "decided_recall": R11,
        "false_alarm": R01, "abstention": R02_ONE_REPO,
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
    "false_alarm": R03, "abstention": R35_CLUSTERED,
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


def incomplete_beta(x, a, b, steps=20000):
    """I_x(a, b) by Simpson quadrature of the beta density -- an independent
    check on the runner's continued fractions, so a pinned effective-count
    interval cannot drift from the defining beta tails."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    log_beta = (math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b))
    total, h = 0.0, x / steps
    for i in range(steps + 1):
        t = i * h
        density = (math.exp((a - 1) * math.log(t) + (b - 1) * math.log1p(-t)
                           - log_beta) if 0 < t < 1 else 0.0)
        total += density * (1 if i in (0, steps) else 4 if i % 2 else 2)
    return total * h / 3


def test_every_rate_aggregates_cases_by_repository():
    # 100 cases in 20 repositories of 5, four misses all inside one repository
    outcomes = [("repo-%d" % (i // 5), 0 if 20 <= i < 24 else 1) for i in range(100)]
    entry = evaluation.rate(outcomes)
    assert entry["k"] == 96 and entry["n"] == 100
    assert entry["n_repos"] == 20
    assert entry["cluster_sizes"] == [5] * 20
    assert entry["deff"] == pytest.approx(4.0)     # 1 + (m-bar 5 - 1) * rho
    assert entry["n_eff"] == pytest.approx(25.0)   # n / DEFF
    assert entry["k_eff"] == pytest.approx(24.0)   # misses scaled the same way
    assert entry["clopper_pearson_effective"] == [
        pytest.approx(x) for x in evaluation.clopper_pearson(24, 25)]
    # the case-level columns are untouched by the clustering
    assert entry["clopper_pearson"] == [
        pytest.approx(x) for x in evaluation.clopper_pearson(96, 100)]
    # every case in its own repository: nothing clusters, DEFF is 1
    apart = evaluation.rate([("repo-%d" % i, 1) for i in range(36)])
    assert apart["n_repos"] == 36 and apart["cluster_sizes"] == [1] * 36
    assert apart["deff"] == pytest.approx(1.0)
    assert apart["n_eff"] == pytest.approx(36.0)
    assert apart["clopper_pearson_effective"] == apart["clopper_pearson"]
    # an empty rate carries the columns and decides nothing
    empty = evaluation.rate([])
    assert (empty["k"], empty["n"], empty["n_repos"]) == (0, 0, 0)
    assert empty["cluster_sizes"] == [] and empty["deff"] == pytest.approx(1.0)
    assert empty["clopper_pearson_effective"] == [0.0, 1.0]


def test_the_intraclass_correlation_reads_the_repository_clustering():
    outcomes = [("repo-%d" % (i // 5), 0 if 20 <= i < 24 else 1) for i in range(100)]
    assert evaluation.rate(outcomes)["rho_hat"] == pytest.approx(0.75)
    # correctness that only varies between repositories is fully correlated
    together = [("a", 1), ("a", 1), ("b", 0), ("b", 0), ("c", 1)]
    assert evaluation.rate(together)["rho_hat"] == pytest.approx(1.0)
    # singletons and one-cluster sets estimate nothing: rho_hat 0, floor applies
    assert evaluation.rate([("a", 1), ("b", 0)])["rho_hat"] == 0.0
    assert evaluation.rate([("a", 1), ("a", 0)])["rho_hat"] == 0.0
    # alternating correctness within every repository: correlation below zero
    zig = evaluation.rate([("a", 1), ("a", 0), ("b", 1), ("b", 0)])
    assert zig["rho_hat"] < 0 and zig["rho_used"] == pytest.approx(0.05)
    assert zig["deff"] == pytest.approx(1.05)      # 1 + (m-bar 2 - 1) * 0.05


def test_the_exact_interval_is_well_defined_at_fractional_effective_counts():
    # k_eff = 0 and k_eff = n_eff have closed forms at any effective n
    n_eff = 2 / 1.05
    assert evaluation.clopper_pearson(0.0, n_eff) == (
        0.0, pytest.approx(1 - 0.025 ** (1 / n_eff)))
    assert evaluation.clopper_pearson(n_eff, n_eff) == (
        pytest.approx(0.025 ** (1 / n_eff)), 1.0)
    # fractional counts solve the defining beta tail equations exactly
    lo, hi = evaluation.clopper_pearson(3 / 1.8, 5 / 1.8)
    assert lo == pytest.approx(0.059345, abs=5e-7)
    assert hi == pytest.approx(0.985923, abs=5e-7)
    assert incomplete_beta(lo, 3 / 1.8, 5 / 1.8 - 3 / 1.8 + 1) == pytest.approx(0.025)
    assert incomplete_beta(hi, 3 / 1.8 + 1, 5 / 1.8 - 3 / 1.8) == pytest.approx(0.975)
    # integral effective counts agree with the integral arithmetic
    assert list(evaluation.clopper_pearson(24.0, 25.0)) == [
        pytest.approx(x) for x in evaluation.clopper_pearson(24, 25)]


def caught(n, counted):
    """A rate over n single-repository cases, `counted` of them in the numerator."""
    return evaluation.rate([("repo-%d" % i, 1 if i < counted else 0)
                            for i in range(n)])


def test_bounds_print_one_decimal_conservatively():
    # 11 of 11 prints a lower bound of 71.5; 0 of 11 an upper bound of 28.5
    assert evaluation.percent_down(evaluation.clopper_pearson(11, 11)[0]) == "71.5"
    assert evaluation.percent_up(evaluation.clopper_pearson(0, 11)[1]) == "28.5"
    # lower bounds never round up: 90.07% prints 90.0, 89.997% prints 89.9
    assert evaluation.percent_down(0.9007428432873219) == "90.0"
    assert evaluation.percent_down(0.8999675644278977) == "89.9"
    # ... over every small count, in both directions
    for n in range(1, 30):
        for k in range(n + 1):
            lo, hi = evaluation.clopper_pearson(k, n)
            assert float(evaluation.percent_down(lo)) <= lo * 100
            assert float(evaluation.percent_up(hi)) >= hi * 100


def test_the_pinned_boundary_values_decide_exactly_as_published():
    # the published boundary values, at the published precision
    assert round(evaluation.clopper_pearson(96, 100)[0], 4) == 0.9007
    assert round(evaluation.clopper_pearson(95, 100)[0], 4) == 0.8872
    assert round(evaluation.clopper_pearson(4, 100)[1], 4) == 0.0993
    assert round(evaluation.clopper_pearson(5, 100)[1], 4) == 0.1128
    assert round(evaluation.clopper_pearson(36, 36)[0], 4) == 0.9026
    assert round(evaluation.clopper_pearson(35, 35)[0], 5) == 0.89997
    # n = 100: 4 misses passes a >= 0.9 lower bound, 5 misses fails
    assert evaluation.bound_gate(caught(100, 96), ">=", 0.90)["pass"] is True
    assert evaluation.bound_gate(caught(100, 95), ">=", 0.90)["pass"] is False
    # 4 twin false alarms passes a <= 0.1 upper bound, 5 fails
    assert evaluation.bound_gate(caught(100, 4), "<=", 0.10)["pass"] is True
    assert evaluation.bound_gate(caught(100, 5), "<=", 0.10)["pass"] is False
    # zero errors: n = 36 reaches a 90 percent claim, n = 35 falls short
    assert evaluation.bound_gate(caught(36, 36), ">=", 0.90)["pass"] is True
    assert evaluation.bound_gate(caught(35, 35), ">=", 0.90)["pass"] is False
    # the deciding bound is the effective-n bound, printed conservatively
    verdict = evaluation.bound_gate(caught(100, 96), ">=", 0.90)
    assert verdict["measured"] == pytest.approx(0.9007, abs=5e-5)
    assert "90.0" in verdict["arithmetic"] and "90.1" not in verdict["arithmetic"]
    assert "effective-n" in verdict["arithmetic"]
    # a bound with no cases behind it decides nothing and passes on nothing
    empty = evaluation.bound_gate(evaluation.rate([]), ">=", 0.90)
    assert empty["pass"] is False and "no cases" in empty["arithmetic"]


def test_a_headline_rate_prints_its_cluster_columns_beside_both_intervals():
    out = evaluation.render(run_fixture(detectors=(baselines.PathRuleBaseline(),)))
    lines = [line for line in out.splitlines() if "| strict " in line]
    assert lines
    for line in lines:
        for column in ("CP95 [", "Wilson [", "eff CP95 [", "n_eff ", "repos ",
                       "rho_hat ", "DEFF "):
            assert column in line, line


def test_the_designed_for_table_is_generated_from_the_interval_arithmetic():
    rows = evaluation.designed_for_table()
    assert [row["effective_n"] for row in rows] == [100, 230]
    # the published table: max errors for a 90% bound, and the launch odds
    assert [row["max_errors"] for row in rows] == [4, 13]
    assert rows[0]["launch_odds"] == {
        "99%/1%": pytest.approx(0.993, abs=5e-4),
        "97%/3%": pytest.approx(0.669, abs=5e-4),
        "95%/5%": pytest.approx(0.190, abs=5e-4)}
    assert rows[1]["launch_odds"] == {
        "99%/1%": pytest.approx(1.0, abs=5e-4),
        "97%/3%": pytest.approx(0.980, abs=5e-4),
        "95%/5%": pytest.approx(0.543, abs=5e-4)}
    # generated, not typed: the max-error row is where the exact bound sits
    # against the threshold, and the odds are both classes clearing it under
    # independent binomial counts
    for row in rows:
        n, m = row["effective_n"], row["max_errors"]
        assert evaluation.clopper_pearson(n - m, n)[0] >= 0.90
        assert evaluation.clopper_pearson(n - m - 1, n)[0] < 0.90
        for label, error in (("99%/1%", 0.01), ("97%/3%", 0.03),
                             ("95%/5%", 0.05)):
            one_class = sum(
                math.comb(n, i) * error ** i * (1 - error) ** (n - i)
                for i in range(m + 1))
            assert row["launch_odds"][label] == pytest.approx(one_class ** 2)
    # printed from the same arithmetic, into the report
    out = evaluation.render(run_fixture())
    for printed in ("100 | 4 | 99.3% | 66.9% | 19.0%",
                    "230 | 13 | 100.0% | 98.0% | 54.3%"):
        assert printed in out


class ScriptedMisses:
    """A test double: misses exactly the named cases, nothing else."""

    id = "misses"

    def __init__(self, misses):
        self.misses = set(misses)

    def run(self, record):
        prediction = "clean" if record.case.id in self.misses else "tampered"
        return baselines.BaselineResult(case=record.case.id, baseline=self.id,
                                        prediction=prediction,
                                        version="misses/1")


def clustered_corpus(root, count=100, per_repo=5):
    """A frozen corpus of tampered cases, `per_repo` per repository."""
    root.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        case_id = "c%03d" % i
        record = {"id": case_id,
                  "source": "fixture: clustered repositories",
                  "technique": "assertion-weakened",
                  "label": "tampered",
                  "split": "frozen",
                  "task": case_id,
                  "repository": "https://example.org/repo-%d" % (i // per_repo),
                  "license": "MIT"}
        (root / (case_id + ".json")).write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8")
    corpus.write_manifest(root)
    return root


def test_a_case_level_pass_beside_an_effective_n_failure_reports_the_effective_n_failure(tmp_path):
    root = clustered_corpus(tmp_path / "corpus")
    # 4 misses of 100 -- all four inside one repository of five cases
    report = evaluation.evaluate(
        root, (ScriptedMisses({"c020", "c021", "c022", "c023"}),), repeats=2)
    recall = report["detectors"]["misses"]["pooled"]["strict_recall"]
    assert recall["k"] == 96 and recall["n"] == 100
    assert recall["n_repos"] == 20 and recall["cluster_sizes"] == [5] * 20
    assert recall["rho_hat"] == pytest.approx(0.75)
    assert recall["deff"] == pytest.approx(4.0)
    assert recall["n_eff"] == pytest.approx(25.0)
    # the case-level interval passes the 90 percent bound ...
    assert recall["clopper_pearson"][0] >= 0.90
    # ... the effective-n interval does not (24 of 25 effective cases)
    assert recall["clopper_pearson_effective"][0] == pytest.approx(0.7965, abs=5e-5)
    # and the reported failure is the effective-n failure, never the case-level pass
    verdict = evaluation.bound_gate(recall, ">=", 0.90)
    assert verdict["pass"] is False
    assert "case-level CP95 lower 90.0% >= 0.9 passes" in verdict["arithmetic"]
    assert "effective-n CP95 lower 79.6% >= 0.9 FAILS" in verdict["arithmetic"]
    assert verdict["arithmetic"].rstrip().endswith(
        "gate-deciding interval: effective-n -> FAIL")
    assert "eff CP95 [0.796" in evaluation.render(report)


def test_the_effective_n_interval_is_never_tighter_than_the_case_level_one():
    report = run_fixture()
    entries = []
    for entry in report["detectors"].values():
        for row in list(entry["cells"].values()) + [entry["pooled"]]:
            entries += [row[name] for name in
                        ("strict_recall", "decided_recall", "false_alarm",
                         "abstention")]
        pooled = entry["pooled"]
        entries += [pooled["twin_false_alarm"],
                    pooled["natural_clean_false_alarm"]]
    for outcomes in ([("a", 1), ("a", 1), ("a", 0), ("b", 0), ("b", 0), ("c", 1)],
                     [("a", 1), ("a", 0), ("b", 1), ("b", 0)],
                     [("a", 1)] * 5 + [("b", 0)] * 5,
                     [("a", 1)] * 5 + [("b", 1), ("b", 0), ("b", 0), ("b", 0),
                                       ("b", 0)]):
        entries.append(evaluation.rate(outcomes))
    assert len(entries) > 20
    for entry in entries:
        if not entry["n"]:
            continue
        lo, hi = entry["clopper_pearson"]
        elo, ehi = entry["clopper_pearson_effective"]
        assert entry["deff"] >= 1.0, entry
        assert elo <= lo + 1e-9, entry
        assert ehi >= hi - 1e-9, entry


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
