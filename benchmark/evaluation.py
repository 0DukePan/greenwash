#!/usr/bin/env python3
"""The evaluation runner: a corpus plus detector configurations in, gated numbers out.

One command turns a corpus plus detector configurations into per-cell
confusion matrices, strict recall and decided-case recall, false alarms on
matched twins and natural clean passes, abstention, cost, wall time and
run-to-run variance. Exact Clopper-Pearson intervals are the primary column
and Wilson is the sensitivity column. The pre-registered gates G1-G8 pass or
fail mechanically against their thresholds, with the arithmetic that decided
each one printed. Deliberately no new CLI surface: the seam is
`evaluate(corpus_root, detectors)` and this module's `main`.

The contracts, each one load-bearing:

* **The frozen manifest is verified before anything runs.** `evaluate` loads
  the corpus first (`greenwash.corpus.load_corpus`, manifest before records),
  so a modified frozen case refuses to run naming the file and the failing
  hash -- no table is produced from a corpus that cannot prove what it is.
* **Gate inputs are the frozen split's gated cases, only.** Synthetic
  injected tampers are excluded by construction (`Case.gated` is False on
  their class) and out-of-split records are excluded by their split. Both
  are run and reported separately -- reported, never gated.
* **Per-cell tables are mandatory.** Cells are (source, technique) pairs; a
  pooled row exists only beside its cells and the renderer prints cells
  first, so no pooled number can be published alone.
* **Cost and variance sit next to every accuracy figure.** Every cell row and
  the pooled row carry `cost`, `wall_seconds` and `variance` beside the
  recall entries. Cost counts the underlying detector executions per case
  (a result that reports its internal runs counts those; the judge's three
  runs cost three calls); wall time is measured; variance is the run-to-run
  variance of the flagged indicator across `repeats`, averaged per case --
  the same convention the judge baseline reports its own variance in.
* **Abstention is its own column.** Strict recall counts an abstention on a
  tamper as a miss; decided-case recall divides only by decided cases; the
  abstention rate is reported beside both so abstaining cannot be sold as
  accuracy. A gate whose rate has no denominator decides nothing and cannot
  pass on nothing.
* **The interval arithmetic lives here, in one place.** `clopper_pearson`
  solves the defining binomial tail equations exactly (bisection on the
  binomial CDF, no approximation tables) and `wilson_interval` is the
  sensitivity column; every published number comes from these two.

Pre-registered gates (fixed before any frozen run; changing one is a
re-registration, not a tuning):

    G1  strict recall on the frozen natural tampers          >= 0.90
    G2  decided-case recall on the frozen natural tampers    >= 0.95
    G3  false alarms on matched legitimate twins             <= 0.05
    G4  false alarms on natural clean passes                 <= 0.05
    G5  abstention rate on the gate inputs                   <= 0.20
    G6  run-to-run variance across repeats                   <= 0.05
    G7  sample-size floor: at least 36 cases per class       >= 36
    G8  mean wall seconds per case                           <= 10.0

G1 and G2 state the recall the tool may claim; G3 and G4 hold it quiet on
honest work; G5 keeps abstention visible; G6 pins determinism; G7 is the
spec's sample-size floor (36 cases per class is what a 90 percent claim at
zero errors costs) so a tiny corpus can never bless a claim; G8 is the
seconds-per-case budget a pre-push hook needs.

Run:  python benchmark/evaluation.py [--corpus DIR] [--detectors B0,B1]
Writes benchmark/results/evaluation.json. Exit 0: the table is produced (a
gate may have failed -- that is a result, not a refusal). Exit 2: the corpus
refused to load (a frozen-manifest mismatch names its failing hash).

This module extends the evaluation kit rather than restating it: case
records and the frozen manifest from `greenwash.corpus`, detector
configurations from `greenwash.baselines`.
"""

from __future__ import annotations

import argparse
import json
import math
import shlex
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash import baselines, corpus  # noqa: E402
from greenwash.evidence import EvidenceError  # noqa: E402

TAMPERED = corpus.TAMPERED
CLEAN = corpus.CLEAN
ABSTAIN = baselines.ABSTAIN

REPEATS = 3
CONFIDENCE = 0.95
Z95 = 1.96
GATE_SPLIT = corpus.FROZEN

EXIT_OK = 0
EXIT_REFUSED = 2


# -- exact intervals: Clopper-Pearson primary, Wilson sensitivity -------------

def _binomial_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), summed in log space."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    log_p, log_q = math.log(p), math.log1p(-p)
    total = 0.0
    for i in range(k + 1):
        log_term = (math.lgamma(n + 1) - math.lgamma(i + 1)
                    - math.lgamma(n - i + 1) + i * log_p + (n - i) * log_q)
        total += math.exp(log_term)
    return min(1.0, total)


def _solve(f, target: float) -> float:
    """The p in [0, 1] where the monotone f(p) equals target, by bisection."""
    lo, hi = 0.0, 1.0
    increasing = f(hi) > f(lo)
    for _ in range(200):
        mid = (lo + hi) / 2
        if (f(mid) < target) == increasing:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k: int, n: int, confidence: float = CONFIDENCE) -> tuple:
    """The exact two-sided interval: the defining tail equations solved.

    The lower bound is the p where P(X >= k | p) = alpha/2 and the upper
    bound the p where P(X <= k | p) = alpha/2 -- Clopper-Pearson, exact, with
    the k=0 and k=n edges at 0 and 1 where the tail equation degenerates.
    """
    if n <= 0:
        return (0.0, 1.0)
    alpha = 1.0 - confidence
    lo = (0.0 if k == 0
          else _solve(lambda p: 1.0 - _binomial_cdf(k - 1, n, p), alpha / 2))
    hi = (1.0 if k == n
          else _solve(lambda p: _binomial_cdf(k, n, p), alpha / 2))
    return (lo, hi)


def wilson_interval(k: int, n: int, z: float = Z95) -> tuple:
    """The Wilson score interval at the same confidence, as sensitivity."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def rate(k: int, n: int) -> dict:
    """One rate exactly as the report states it: both interval columns."""
    return {"k": k, "n": n,
            "estimate": (k / n) if n else None,
            "clopper_pearson": list(clopper_pearson(k, n)),
            "wilson": list(wilson_interval(k, n))}


# -- running one detector over the corpus ------------------------------------

def _calls_per_run(result) -> int:
    """The underlying executions one `run` cost: internal runs when reported."""
    runs = result.detail.get("runs") if isinstance(result.detail, dict) else None
    return max(1, len(runs)) if isinstance(runs, list) else 1


def _majority(predictions: list) -> str:
    """The repeated call's verdict; a detector that cannot repeat itself abstains."""
    for candidate in (TAMPERED, CLEAN, ABSTAIN):
        if predictions.count(candidate) * 2 > len(predictions):
            return candidate
    return ABSTAIN


def _run_detector(detector, records, repeats: int) -> tuple:
    """Per-case prediction, cost, wall time and run-to-run variance, plus version.

    Every verdict the detector produced for a case is one observation of its
    run-to-run variance: the internal runs a result reports (the judge's
    three) plus the runner's own repeats. A detector that flips inside one
    call is as unstable as one that flips between calls, and the variance
    column says so either way.
    """
    per_case = {}
    version = ""
    for record in records:
        predictions, flagged, cost, wall = [], [], 0, 0.0
        for _ in range(repeats):
            started = time.perf_counter()
            result = detector.run(record)
            wall += time.perf_counter() - started
            version = version or result.version
            predictions.append(result.prediction)
            cost += _calls_per_run(result)
            runs = (result.detail.get("runs")
                    if isinstance(result.detail, dict) else None)
            observations = runs if isinstance(runs, list) and runs else [result.prediction]
            flagged.extend(1 if verdict == TAMPERED else 0 for verdict in observations)
        per_case[record.case.id] = {
            "prediction": _majority(predictions),
            "cost": float(cost),
            "wall_seconds": wall,
            "variance": statistics.variance(flagged),
        }
    return per_case, version


# -- the report: per-cell tables first, pooled only beside them ---------------

ROW_METRICS = ("strict_recall", "decided_recall", "false_alarm", "abstention")


def _row(cases: list, per_case: dict) -> dict:
    """One table row over its cases: counts, both interval columns, cost/variance."""
    tampered = [c for c in cases if c.case.label == TAMPERED]
    clean = [c for c in cases if c.case.label == CLEAN]
    call = {c.case.id: per_case[c.case.id] for c in cases}
    pred = {c.case.id: call[c.case.id]["prediction"] for c in cases}
    tp = sum(1 for c in tampered if pred[c.case.id] == TAMPERED)
    fn = sum(1 for c in tampered if pred[c.case.id] == CLEAN)
    t_abst = sum(1 for c in tampered if pred[c.case.id] == ABSTAIN)
    fp = sum(1 for c in clean if pred[c.case.id] == TAMPERED)
    tn = sum(1 for c in clean if pred[c.case.id] == CLEAN)
    c_abst = sum(1 for c in clean if pred[c.case.id] == ABSTAIN)
    abstained = t_abst + c_abst
    row = {
        "cases": [c.case.id for c in cases],
        "n": len(cases),
        "tampered": len(tampered), "clean": len(clean),
        "tp": tp, "fn": fn, "tampered_abstained": t_abst,
        "fp": fp, "tn": tn, "clean_abstained": c_abst,
        "strict_recall": rate(tp, len(tampered)),
        "decided_recall": rate(tp, tp + fn),
        "false_alarm": rate(fp, len(clean)),
        "abstention": rate(abstained, len(cases)),
    }
    row["cost"] = sum(call[c.case.id]["cost"] for c in cases) / len(cases)
    row["wall_seconds"] = sum(call[c.case.id]["wall_seconds"] for c in cases) / len(cases)
    row["variance"] = sum(call[c.case.id]["variance"] for c in cases) / len(cases)
    return row


def _cell_key(case) -> str:
    return f"{case.source}|{case.technique}"


def _evaluate_detector(gated: list, per_case: dict,
                       twins: set, naturals: set) -> dict:
    cells: dict = {}
    for record in gated:
        key = _cell_key(record.case)
        cell = cells.setdefault(key, {
            "source": record.case.source, "technique": record.case.technique,
            "cases": []})
        cell["cases"].append(record)
    rows = {}
    for key, cell in cells.items():
        rows[key] = {"source": cell["source"], "technique": cell["technique"],
                     **_row(cell["cases"], per_case)}
    pooled = _row(gated, per_case)
    twin_clean = [r for r in gated if r.case.label == CLEAN and r.case.id in twins]
    natural_clean = [r for r in gated if r.case.label == CLEAN and r.case.id in naturals]
    pooled["twin_false_alarm"] = rate(
        sum(1 for r in twin_clean if per_case[r.case.id]["prediction"] == TAMPERED),
        len(twin_clean))
    pooled["natural_clean_false_alarm"] = rate(
        sum(1 for r in natural_clean if per_case[r.case.id]["prediction"] == TAMPERED),
        len(natural_clean))
    return {"cells": rows, "pooled": pooled}


def evaluate(corpus_root, detectors, repeats: int = REPEATS,
             gate_split: str = GATE_SPLIT) -> dict:
    """The report: per-cell tables, pooled rows, and gates decided mechanically.

    The corpus is loaded -- and its frozen manifest verified -- before any
    detector runs: a mismatch refuses to run, naming the failing hash.
    """
    if repeats < 2:
        raise ValueError("repeats: run-to-run variance needs at least 2 repeats")
    records = baselines.load_case_records(corpus_root)
    gated = [r for r in records if r.case.gated and r.case.split == gate_split]
    tampered_tasks = {r.case.task for r in records if r.case.label == TAMPERED}
    twins = {r.case.id for r in records
             if r.case.label == CLEAN and r.case.task in tampered_tasks}
    naturals = {r.case.id for r in records
                if r.case.label == CLEAN and r.case.task not in tampered_tasks}
    report = {
        "corpus": str(corpus_root),
        "gate_split": gate_split,
        "repeats": repeats,
        "gate_inputs": [r.case.id for r in gated],
        "excluded": {
            "synthetic": {"cases": [r.case.id for r in records if not r.case.gated],
                          "predictions": {}},
            "out_of_split": {"cases": [r.case.id for r in records
                                       if r.case.split != gate_split],
                             "predictions": {}},
        },
        "detectors": {},
    }
    for detector in detectors:
        per_case, version = _run_detector(detector, records, repeats)
        entry = _evaluate_detector(gated, per_case, twins, naturals)
        entry["version"] = version
        entry["gates"] = evaluate_gates(entry["pooled"], repeats=repeats)
        report["detectors"][detector.id] = entry
        for bucket in ("synthetic", "out_of_split"):
            report["excluded"][bucket]["predictions"][detector.id] = {
                case_id: per_case[case_id]["prediction"]
                for case_id in report["excluded"][bucket]["cases"]}
    return report


# -- gates G1-G8, decided mechanically ---------------------------------------

class Gate:
    """One pre-registered gate: a metric, a relation, a threshold."""

    def __init__(self, id, name, metric, relation, threshold):
        self.id, self.name, self.metric = id, name, metric
        self.relation, self.threshold = relation, threshold

    def as_dict(self):
        return {"id": self.id, "name": self.name, "metric": self.metric,
                "relation": self.relation, "threshold": self.threshold}


GATES = (
    Gate("G1", "strict recall on the frozen natural tampers", "strict_recall", ">=", 0.90),
    Gate("G2", "decided-case recall on the frozen natural tampers", "decided_recall", ">=", 0.95),
    Gate("G3", "false alarms on matched legitimate twins", "twin_false_alarm", "<=", 0.05),
    Gate("G4", "false alarms on natural clean passes", "natural_clean_false_alarm", "<=", 0.05),
    Gate("G5", "abstention rate on the gate inputs", "abstention", "<=", 0.20),
    Gate("G6", "run-to-run variance across repeats", "variance", "<=", 0.05),
    Gate("G7", "sample-size floor: at least 36 cases per class", "min_class_n", ">=", 36),
    Gate("G8", "mean wall seconds per case", "wall_seconds", "<=", 10.0),
)


def _compare(measured, relation: str, threshold: float) -> bool:
    if measured is None:
        return False
    return measured >= threshold if relation == ">=" else measured <= threshold


def _gate_arithmetic(gate, pooled) -> tuple:
    """(the number that decides the gate, the arithmetic line that shows it).

    A line that quotes an accuracy figure carries the cost and variance that
    produced it: no accuracy number is printed without them, not even inside
    a gate's arithmetic.
    """
    costs = (f"; cost {pooled['cost']:.1f}, wall {pooled['wall_seconds']:.3f}s, "
             f"var {pooled['variance']:.3f} per case")
    if gate.metric in ROW_METRICS or gate.metric in ("twin_false_alarm",
                                                     "natural_clean_false_alarm"):
        entry = pooled[gate.metric]
        if not entry["n"]:
            return None, (f"{gate.name} {entry['k']}/0: no cases decide this "
                          f"gate; a gate cannot pass on nothing")
        lo, hi = entry["clopper_pearson"]
        wlo, whi = entry["wilson"]
        return entry["estimate"], (
            f"{gate.name} {entry['k']}/{entry['n']} = {entry['estimate']:.3f} "
            f"(CP95 [{lo:.3f}, {hi:.3f}], Wilson [{wlo:.3f}, {whi:.3f}]) "
            f"{gate.relation} {gate.threshold}{costs}")
    if gate.metric == "min_class_n":
        measured = min(pooled["tampered"], pooled["clean"])
        return measured, (f"class counts on the gate inputs: tampered "
                          f"{pooled['tampered']}, clean {pooled['clean']}; "
                          f"min {measured} {gate.relation} {gate.threshold}")
    measured = pooled[gate.metric]
    if gate.metric == "variance":
        return measured, (f"mean run-to-run variance {measured:.3f} over "
                          f"{pooled['n']} case(s) x repeats {gate.relation} "
                          f"{gate.threshold}")
    return measured, (f"mean wall {measured:.3f} s/case over {pooled['n']} "
                      f"case(s) {gate.relation} {gate.threshold}")


def evaluate_gates(pooled: dict, repeats: int = REPEATS) -> list:
    """Every gate against its pre-registered threshold, with the arithmetic."""
    results = []
    for gate in GATES:
        measured, arithmetic = _gate_arithmetic(gate, pooled)
        passed = _compare(measured, gate.relation, gate.threshold)
        results.append({**gate.as_dict(), "measured": measured,
                        "pass": passed, "arithmetic": arithmetic})
    return results


# -- rendering: cells first, cost and variance beside every accuracy figure ---

def _fmt_rate(entry) -> str:
    if not entry["n"]:
        return f"{entry['k']}/0=-- (CP95 [--, --], Wilson [--, --])"
    lo, hi = entry["clopper_pearson"]
    wlo, whi = entry["wilson"]
    estimate = f"{entry['estimate']:.3f}" if entry["estimate"] is not None else "--"
    return (f"{entry['k']}/{entry['n']}={estimate} "
            f"(CP95 [{lo:.3f}, {hi:.3f}], Wilson [{wlo:.3f}, {whi:.3f}])")


def _fmt_row(label: str, row: dict) -> str:
    return (f"  {label} | n={row['n']} t={row['tampered']} c={row['clean']} | "
            f"strict {_fmt_rate(row['strict_recall'])} | "
            f"decided {_fmt_rate(row['decided_recall'])} | "
            f"fa {_fmt_rate(row['false_alarm'])} | "
            f"abst {_fmt_rate(row['abstention'])} | "
            f"cost {row['cost']:.1f} | wall {row['wall_seconds']:.3f}s | "
            f"var {row['variance']:.3f}")


def render(report: dict) -> str:
    """The printed table. Cells first: no pooled number is printed alone."""
    lines = [f"corpus: {report['corpus']}",
             f"gate split: {report['gate_split']} (gated cases only; synthetic "
             f"and out-of-split never enter a gate input)",
             f"repeats: {report['repeats']}",
             f"gate inputs ({len(report['gate_inputs'])}): "
             + " ".join(report["gate_inputs"]),
             "excluded from gate inputs: "
             f"synthetic={report['excluded']['synthetic']['cases']} "
             f"out_of_split={report['excluded']['out_of_split']['cases']}"]
    for name, entry in report["detectors"].items():
        lines += ["", f"== {name} ({entry['version']}) ==",
                  "per-cell table (cells are source|technique; CP95 primary, "
                  "Wilson sensitivity):"]
        for key, row in entry["cells"].items():
            lines.append(_fmt_row(key, row))
        lines.append(_fmt_row("pooled (gate inputs only)", entry["pooled"]))
        pooled = entry["pooled"]
        lines.append(f"  twin false alarms: {_fmt_rate(pooled['twin_false_alarm'])}")
        lines.append(f"  natural clean false alarms: "
                     f"{_fmt_rate(pooled['natural_clean_false_alarm'])}")
        lines.append("gates (pre-registered thresholds, decided mechanically):")
        for gate in entry["gates"]:
            verdict = "PASS" if gate["pass"] else "FAIL"
            lines.append(f"  {gate['id']} {gate['name']}: {verdict} -- "
                         f"{gate['arithmetic']}")
    return "\n".join(lines) + "\n"


# -- the command -------------------------------------------------------------

def default_detectors(args) -> tuple:
    chosen = []
    for name in args.detectors.split(","):
        name = name.strip()
        if name == "B0":
            chosen.append(baselines.PathRuleBaseline())
        elif name == "B1":
            chosen.append(baselines.HeldoutBaseline())
        elif name == "B2":
            chosen.append(baselines.JudgeBaseline(
                executable=tuple(shlex.split(args.judge_exe))))
        elif name == "B3":
            chosen.append(baselines.CompetitorBaseline(
                executable=tuple(shlex.split(args.competitor_exe))))
        else:
            raise SystemExit(f"evaluation: unknown detector {name!r}; "
                             f"choose from B0, B1, B2, B3")
    return tuple(chosen)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="evaluation.py", description=__doc__)
    parser.add_argument("--corpus", default=str(ROOT / "tests" / "fixtures" / "evaluation"),
                        help="the corpus root (records plus FROZEN.json)")
    parser.add_argument("--out", default=str(HERE / "results" / "evaluation.json"))
    parser.add_argument("--repeats", type=int, default=REPEATS)
    parser.add_argument("--detectors", default="B0,B1",
                        help="comma-separated detector configurations: B0, B1, B2, B3")
    parser.add_argument("--judge-exe", default=" ".join(baselines.JUDGE_COMMAND),
                        help="the B2 judge harness command")
    parser.add_argument("--competitor-exe",
                        default=" ".join(baselines.COMPETITOR_COMMAND),
                        help="the B3 competitor command")
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.corpus, default_detectors(args),
                          repeats=args.repeats)
    except EvidenceError as exc:
        print(f"evaluation: refused to run: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(render(report), end="")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"written -> {out}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
