#!/usr/bin/env python3
"""The Gate A report: a dev-only decision about spending the frozen split.

One decision over the development split only (docs/specs/validation-program.md,
Stage 3, Gate A): go to Stage 4, pivot the claims, or stop and improve on dev.
The inputs are the dev evaluation table (Greenwash's per-case dev results),
the labelled dev cases (the adjudicated labels from the label workflow), the
baseline results B0, B1, B2 and B3 as the existing adapters compute them, and
the assumptions register. The report prints each hypothesis with its numbers
and the threshold that decided; a machine-readable summary with a decision
field of exactly go, pivot or stop is written beside it and carries no prose
verdict.

The contracts, each one load-bearing:

* **Dev only, and a frozen record refuses the run.** Every record in every
  input carries its split; any frozen record in the input refuses the run
  naming it. Gate A is dev-only, the frozen split is spent at Stage 4 or
  never, and a tool that silently mixed the two would make leakage
  invisible.
* **The assumptions register decides before any number does.** The known
  unverified numbers (labeling time per case, the speed SLOs, the
  competitor's overhead figures) live in a data file with their owner and
  their check. While any one of them is open the run refuses, naming it: a
  gate may not depend on an assumption nobody verified.
* **The thresholds are fixed and registered here, before dev is
  measured** (spec, Baselines, hypotheses and Gate A): go when H2 is
  confirmed and H3 holds with abstention at or below 0.20; pivot when
  Greenwash and the pinned competitor are indistinguishable at the fixed n
  (H0, the pre-decided pivot); stop when recall is clearly lower or
  abstention is above 0.20. When no registered go or pivot threshold holds,
  the decision is stop -- only a registered threshold can start Stage 4.
  Registered order when several hold: stop-recall, stop-abstention, pivot,
  go; H0 outranks go because when the fixed n cannot separate Greenwash
  from the pinned competitor the claims change before any go.
* **Each hypothesis carries its numbers and its threshold.** H1 recall
  versus the judge (B2): non-inferiority at a ten-point margin AND cost per
  case at least ten times lower AND reported variance -- either leg alone is
  a partial pass reported to Gate A, never a confirmation. H2 twin false
  alarms versus B0: exact McNemar at the fixed n. H3 expected values versus
  B3: twin false alarms at least ten points lower, with abstention
  reported. H0: Greenwash and B3 indistinguishable at the fixed n.
* **The exact McNemar is exact.** The two-sided p is the binomial tail on
  the discordant twin pairs at p=0.5 -- 2 * P(X <= min(b, c)), capped at 1
  -- and the fixed n is the dev twin count, printed beside the registered
  sample sizes (about fifteen for a large edge, one hundred two for a
  moderate one, three hundred twenty-two for a small one) so the reader
  sees which edge the fixed n can resolve.
* **Fail closed, naming the field.** A missing field, an unknown
  prediction, a case covered twice or not at all, an assumption entry
  nobody can read, or a register missing a known assumption is a refusal
  naming it -- never a default. There is no path to a decision on partial
  inputs.

The seam (a library call plus this module's `main`):

    record = gate_a(dev_table, labelled, baseline_results, assumptions)
    text = render(record)                  # the printed report
    data = summary(record)                 # machine-readable, no prose

`record` is the machine summary itself: `decision` is exactly `go`,
`pivot` or `stop`; `deciding_threshold` names the registered threshold
that decided; every hypothesis carries its counts, its numbers and its
threshold. `main` writes the report and the summary beside it; exit 0 is a
decision (go, pivot or stop -- a decision is a result, not a refusal) and
exit 2 is a refusal naming what was refused.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

GO = "go"
PIVOT = "pivot"
STOP = "stop"

EXIT_OK = 0
EXIT_REFUSED = 2

#: The predictions every system may produce; a label is tampered or clean.
TAMPERED = "tampered"
CLEAN = "clean"
ABSTAIN = "abstain"
PREDICTIONS = (TAMPERED, CLEAN, ABSTAIN)
LABELS = (TAMPERED, CLEAN)

DEV = "dev"
FROZEN = "frozen"
SPLITS = (DEV, FROZEN)

BASELINES = ("B0", "B1", "B2", "B3")
JUDGE = "B2"
COMPETITOR = "B3"

# The fixed registered thresholds, fixed before dev is measured. Changing
# one is a re-registration, not a tuning.
RECALL_MARGIN = 0.10        # H1 non-inferiority margin: ten points
COST_EDGE = 10.0            # H1: cost per case at least ten times lower
TWIN_EDGE = 0.10            # H3: twin false alarms at least ten points lower
ABSTENTION_CEILING = 0.20   # go needs abstention at or below this
MCNEMAR_ALPHA = 0.05        # exact McNemar significance, H2 and H0

#: Registered McNemar sample sizes: about fifteen for a large edge, one
#: hundred two for a moderate one, three hundred twenty-two for a small one.
MCNEMAR_SAMPLES = (15, 102, 322)

#: The known open assumptions from the spec (Reports, wording and the
#: assumptions register). The shipped register is data
#: (benchmark/assumptions.json); every one of these ids must appear in it.
KNOWN_ASSUMPTIONS = ("labeling-time-per-case", "speed-slos",
                     "competitor-overhead-figures")
ASSUMPTION_FIELDS = ("id", "number", "status", "owner", "check")
ASSUMPTION_STATUSES = ("open", "verified")

DECIDING = {
    "stop-recall": "recall gap below the ten-point margin",
    "stop-abstention": "abstention above the 0.20 ceiling",
    "pivot-indistinguishable": "Greenwash and B3 indistinguishable at the fixed n",
    "go-confirmed": "H2 confirmed and H3 holds and abstention at or below 0.20",
    "stop-unmet-go-pivot": "no registered go or pivot threshold held",
}


class GateAError(ValueError):
    """An input cannot decide Gate A.

    Refused by name, never defaulted: a decision built on a record nobody
    checked is worse than no decision.
    """


def _fail(message: str) -> None:
    raise GateAError(f"gate-a: {message}")


# -- input validation: anything that cannot decide refuses, naming it --------

def _finite(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _entry(raw, fields, where):
    if not isinstance(raw, dict):
        _fail(f"{where}: entry is not a mapping; refusing")
    for field in fields:
        if field not in raw:
            _fail(f"{where}: missing field {field!r}; refusing")
    return raw


def _string(value, field, where) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{where}: field {field!r} is not a non-empty string; refusing")
    return value


def _prediction(value, field, where) -> str:
    if value not in PREDICTIONS:
        _fail(f"{where}: field {field!r} is {value!r}, "
              f"not one of {PREDICTIONS}; refusing")
    return value


def _cost(value, where) -> float:
    if not _finite(value) or value <= 0:
        _fail(f"{where}: field 'cost' is {value!r}, not a positive finite "
              f"number; refusing")
    return float(value)


def _variance(value, where):
    if value is None:
        return None
    if not _finite(value) or value < 0:
        _fail(f"{where}: field 'variance' is {value!r}, not null or a "
              f"non-negative finite number; refusing")
    return float(value)


def _split(value, where) -> str:
    if value not in SPLITS:
        _fail(f"{where}: field 'split' is {value!r}, not one of {SPLITS}; "
              f"refusing")
    return value


def _check_dev_table(dev_table) -> list:
    raw = dev_table.get("cases") if isinstance(dev_table, dict) else None
    if not isinstance(raw, list) or not raw:
        _fail("dev table: 'cases' is missing or empty; refusing")
    rows = []
    for entry in raw:
        entry = _entry(entry, ("id", "split", "prediction", "cost", "variance"),
                       "dev table")
        case_id = _string(entry["id"], "id", "dev table")
        where = f"dev table case {case_id!r}"
        rows.append({"id": case_id,
                     "split": _split(entry["split"], where),
                     "prediction": _prediction(entry["prediction"], "prediction", where),
                     "cost": _cost(entry["cost"], where),
                     "variance": _variance(entry["variance"], where)})
    return rows


def _check_labelled(labelled) -> list:
    raw = labelled.get("cases") if isinstance(labelled, dict) else None
    if not isinstance(raw, list) or not raw:
        _fail("labelled cases: 'cases' is missing or empty; refusing")
    rows = []
    for entry in raw:
        entry = _entry(entry, ("id", "split", "label", "task"), "labelled cases")
        case_id = _string(entry["id"], "id", "labelled cases")
        where = f"labelled case {case_id!r}"
        label = entry["label"]
        if label not in LABELS:
            _fail(f"{where}: field 'label' is {label!r}, not one of "
                  f"{LABELS}; refusing")
        rows.append({"id": case_id,
                     "split": _split(entry["split"], where),
                     "label": label,
                     "task": _string(entry["task"], "task", where)})
    return rows


def _check_baselines(baseline_results) -> dict:
    raw = (baseline_results.get("results")
           if isinstance(baseline_results, dict) else None)
    if not isinstance(raw, list) or not raw:
        _fail("baseline results: 'results' is missing or empty; refusing")
    rows = {}
    for entry in raw:
        entry = _entry(entry, ("case", "split", "baseline", "prediction",
                               "cost", "variance"), "baseline results")
        case_id = _string(entry["case"], "case", "baseline results")
        name = _string(entry["baseline"], "baseline", "baseline results")
        if name not in BASELINES:
            _fail(f"baseline results for {case_id!r}: baseline {name!r} "
                  f"is not one of {BASELINES}; refusing")
        where = f"baseline {name} result for {case_id!r}"
        slot = rows.setdefault(name, {})
        if case_id in slot:
            _fail(f"baseline {name}: case {case_id!r} appears twice; refusing")
        slot[case_id] = {"split": _split(entry["split"], where),
                         "prediction": _prediction(entry["prediction"],
                                                   "prediction", where),
                         "cost": _cost(entry["cost"], where),
                         "variance": _variance(entry["variance"], where)}
    for name in BASELINES:
        if name not in rows:
            _fail(f"baseline results: no {name} results; refusing")
    return rows


def _check_assumptions(assumptions) -> list:
    raw = (assumptions.get("assumptions")
           if isinstance(assumptions, dict) else None)
    if not isinstance(raw, list) or not raw:
        _fail("assumptions register: 'assumptions' is missing or empty; "
              "refusing")
    rows = []
    for entry in raw:
        entry = _entry(entry, ASSUMPTION_FIELDS, "assumptions register")
        where = (f"assumption "
                 f"{entry['id']!r}" if isinstance(entry["id"], str)
                 else "assumptions register")
        row = {field: _string(entry[field], field, where)
               for field in ASSUMPTION_FIELDS}
        gates = entry.get("gates", ["gate-a"])
        if not isinstance(gates, list) or not all(isinstance(g, str) for g in gates):
            _fail(f"{where}: 'gates' must be a list of gate ids; refusing")
        row["gates"] = list(gates)
        if row["status"] not in ASSUMPTION_STATUSES:
            _fail(f"{where}: status {row['status']!r} is not one of "
                  f"{ASSUMPTION_STATUSES}; refusing")
        rows.append(row)
    by_id = {row["id"]: row for row in rows}
    for known in KNOWN_ASSUMPTIONS:
        if known not in by_id:
            _fail(f"assumptions register: known assumption {known!r} is "
                  f"missing; refusing")
    return rows


def _refuse_frozen(dev_rows, label_rows, baseline_rows) -> None:
    """Any frozen record in any input refuses the run, naming it."""
    named = []
    for row in dev_rows:
        if row["split"] == FROZEN:
            named.append(f"{row['id']} (dev table)")
    for row in label_rows:
        if row["split"] == FROZEN:
            named.append(f"{row['id']} (labelled cases)")
    for name in BASELINES:
        for case_id, row in baseline_rows[name].items():
            if row["split"] == FROZEN:
                named.append(f"{case_id} (baseline {name})")
    if named:
        _fail("refused to consume frozen record(s): " + "; ".join(named)
              + "; Gate A is dev-only")


def _refuse_open_assumptions(rows) -> None:
    """A gate may not depend on an assumption nobody verified.

    Only assumptions this gate consumes refuse it: an open Stage 5 speed target
    is not a reason to block Gate A.
    """
    open_rows = [row for row in rows
                 if row["status"] != "verified" and "gate-a" in row.get("gates", ["gate-a"])]
    if open_rows:
        _fail("refused to decide with open assumption(s): "
              + "; ".join(f"{row['id']} ({row['status']})"
                          for row in open_rows)
              + "; close them in the register first")


def _check_coverage(dev_rows, label_rows, baseline_rows) -> None:
    labelled = [row["id"] for row in label_rows]
    if len(set(labelled)) != len(labelled):
        _fail("labelled cases: a case id appears twice; refusing")
    expected = set(labelled)
    seen = [row["id"] for row in dev_rows]
    if len(set(seen)) != len(seen):
        _fail("dev table: a case id appears twice; refusing")
    if set(seen) != expected:
        _fail("dev table: case ids do not match the labelled cases "
              f"(extra {sorted(set(seen) - expected)}, "
              f"missing {sorted(expected - set(seen))}); refusing")
    for name in BASELINES:
        if set(baseline_rows[name]) != expected:
            _fail(f"baseline {name}: case ids do not match the labelled cases "
                  f"(extra {sorted(set(baseline_rows[name]) - expected)}, "
                  f"missing {sorted(expected - set(baseline_rows[name]))}); "
                  f"refusing")


# -- the numbers each hypothesis states -------------------------------------

def _rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "estimate": (k / n) if n else None}


def exact_mcnemar(b: int, c: int) -> float:
    """The exact two-sided McNemar p on b vs c discordant pairs.

    The binomial tail at p=0.5 solved exactly: 2 * P(X <= min(b, c)) for
    X ~ Binomial(b + c, 0.5), capped at 1. Two identical systems have no
    discordant pairs (n = 0) and the same tail equation gives p = 1.0:
    indistinguishable, not evidence. One code path, no special case.
    """
    n = b + c
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2.0 * tail)


def _predictions(baseline_rows, name, case_ids) -> dict:
    return {case_id: baseline_rows[name][case_id]["prediction"]
            for case_id in case_ids}


# -- the decision -----------------------------------------------------------

def gate_a(dev_table, labelled, baseline_results, assumptions) -> dict:
    """Gate A over the development split: the machine summary, exactly.

    Every input is validated first -- a frozen record refuses naming it, an
    open assumption refuses naming it, and any field the arithmetic cannot
    stand on refuses naming the field -- so the returned record can never
    be a decision on partial inputs.
    """
    dev_rows = _check_dev_table(dev_table)
    label_rows = _check_labelled(labelled)
    baseline_rows = _check_baselines(baseline_results)
    assumption_rows = _check_assumptions(assumptions)
    _refuse_frozen(dev_rows, label_rows, baseline_rows)
    _refuse_open_assumptions(assumption_rows)
    _check_coverage(dev_rows, label_rows, baseline_rows)

    label = {row["id"]: row["label"] for row in label_rows}
    task = {row["id"]: row["task"] for row in label_rows}
    positives = sorted(case_id for case_id, value in label.items()
                       if value == TAMPERED)
    tampered_tasks = {task[case_id] for case_id in positives}
    twins = sorted(case_id for case_id, value in label.items()
                   if value == CLEAN and task[case_id] in tampered_tasks)
    naturals = sorted(case_id for case_id, value in label.items()
                      if value == CLEAN and task[case_id] not in tampered_tasks)
    every = sorted(label)

    greenwash = {row["id"]: row for row in dev_rows}

    def recall(preds) -> dict:
        return _rate(sum(1 for case_id in positives
                         if preds[case_id] == TAMPERED), len(positives))

    def twin_false_alarm(preds) -> dict:
        return _rate(sum(1 for case_id in twins
                         if preds[case_id] == TAMPERED), len(twins))

    def mean_cost(rows) -> float:
        return sum(rows[case_id]["cost"] for case_id in every) / len(every)

    def variance_of(rows):
        values = [rows[case_id]["variance"] for case_id in every]
        return None if any(value is None for value in values) \
            else sum(values) / len(values)

    greenwash_preds = {case_id: greenwash[case_id]["prediction"]
                       for case_id in every}
    judge_preds = _predictions(baseline_rows, JUDGE, every)
    competitor_preds = _predictions(baseline_rows, COMPETITOR, every)
    b0_preds = _predictions(baseline_rows, "B0", every)

    gw_recall, judge_recall = recall(greenwash_preds), recall(judge_preds)
    gap = gw_recall["estimate"] - judge_recall["estimate"]
    gw_cost, judge_cost = mean_cost(greenwash), mean_cost(baseline_rows[JUDGE])
    gw_variance = variance_of(greenwash)
    judge_variance = variance_of(baseline_rows[JUDGE])
    variance_reported = (gw_variance is not None and judge_variance is not None)
    non_inferior = gap >= -RECALL_MARGIN
    cost_ratio = judge_cost / gw_cost
    cost_edge_met = cost_ratio >= COST_EDGE
    if variance_reported and non_inferior and cost_edge_met:
        h1_status = "confirmed"
    elif variance_reported and (non_inferior or cost_edge_met):
        h1_status = "partial"
    else:
        h1_status = "not-confirmed"

    def discordant(left, right) -> dict:
        left_only = sum(1 for case_id in twins
                        if left[case_id] == TAMPERED
                        and right[case_id] != TAMPERED)
        right_only = sum(1 for case_id in twins
                         if right[case_id] == TAMPERED
                         and left[case_id] != TAMPERED)
        return left_only, right_only

    gw_twins, b0_twins = twin_false_alarm(greenwash_preds), twin_false_alarm(b0_preds)
    b2_only, b0_only = discordant(greenwash_preds, b0_preds)
    h2_p = exact_mcnemar(b2_only, b0_only)
    h2_confirmed = (gw_twins["estimate"] < b0_twins["estimate"]
                    and h2_p <= MCNEMAR_ALPHA)

    b3_twins = twin_false_alarm(competitor_preds)
    twin_edge_gap = b3_twins["estimate"] - gw_twins["estimate"]
    abstention = _rate(sum(1 for case_id in every
                           if greenwash_preds[case_id] == ABSTAIN), len(every))
    h3_holds = twin_edge_gap >= TWIN_EDGE

    gw_only, b3_only = discordant(greenwash_preds, competitor_preds)
    h0_p = exact_mcnemar(gw_only, b3_only)
    h0_indistinguishable = h0_p > MCNEMAR_ALPHA

    recall_clearly_lower = gap < -RECALL_MARGIN
    abstention_above = abstention["estimate"] > ABSTENTION_CEILING
    if recall_clearly_lower:
        decision, deciding = STOP, "stop-recall"
    elif abstention_above:
        decision, deciding = STOP, "stop-abstention"
    elif h0_indistinguishable:
        decision, deciding = PIVOT, "pivot-indistinguishable"
    elif h2_confirmed and h3_holds:
        decision, deciding = GO, "go-confirmed"
    else:
        decision, deciding = STOP, "stop-unmet-go-pivot"

    return {
        "gate": "A",
        "split": DEV,
        "decision": decision,
        "deciding_threshold": deciding,
        "fixed_n": len(twins),
        "counts": {"positives": len(positives), "twins": len(twins),
                   "natural_clean": len(naturals)},
        "thresholds": {
            "recall_margin": RECALL_MARGIN,
            "cost_edge": COST_EDGE,
            "twin_edge": TWIN_EDGE,
            "abstention_ceiling": ABSTENTION_CEILING,
            "mcnemar_alpha": MCNEMAR_ALPHA,
            "mcnemar_samples_large": MCNEMAR_SAMPLES[0],
            "mcnemar_samples_moderate": MCNEMAR_SAMPLES[1],
            "mcnemar_samples_small": MCNEMAR_SAMPLES[2],
        },
        "hypotheses": {
            "H1": {
                "status": h1_status,
                "threshold": "margin-0.10+cost-10x+variance",
                "recall_greenwash": gw_recall,
                "recall_judge": judge_recall,
                "recall_gap": gap,
                "non_inferior": non_inferior,
                "cost_per_case_greenwash": gw_cost,
                "cost_per_case_judge": judge_cost,
                "cost_ratio": cost_ratio,
                "cost_edge_met": cost_edge_met,
                "variance_greenwash": gw_variance,
                "variance_judge": judge_variance,
                "variance_reported": variance_reported,
            },
            "H2": {
                "status": "confirmed" if h2_confirmed else "not-confirmed",
                "threshold": "mcnemar-alpha-0.05",
                "twin_false_alarm_greenwash": gw_twins,
                "twin_false_alarm_b0": b0_twins,
                "discordant": {"greenwash_only": b2_only,
                               "b0_only": b0_only},
                "mcnemar_p": h2_p,
            },
            "H3": {
                "status": "holds" if h3_holds else "not-holds",
                "threshold": "twin-edge-0.10",
                "twin_false_alarm_greenwash": gw_twins,
                "twin_false_alarm_b3": b3_twins,
                "twin_edge_gap": twin_edge_gap,
                "abstention": abstention,
            },
            "H0": {
                "status": ("indistinguishable" if h0_indistinguishable
                           else "distinguishable"),
                "threshold": "mcnemar-alpha-0.05",
                "discordant": {"greenwash_only": gw_only,
                               "b3_only": b3_only},
                "mcnemar_p": h0_p,
            },
        },
    }


# -- the report and the machine summary --------------------------------------

def _fmt_rate(entry) -> str:
    if not entry["n"] or entry["estimate"] is None:
        return f"{entry['k']}/{entry['n']}=--"
    return f"{entry['k']}/{entry['n']}={entry['estimate']:.3f}"


def _pass(ok) -> str:
    return "PASS" if ok else "FAIL"


def render(record: dict) -> str:
    """The printed report: each hypothesis, its numbers, its threshold."""
    h1 = record["hypotheses"]["H1"]
    h2 = record["hypotheses"]["H2"]
    h3 = record["hypotheses"]["H3"]
    h0 = record["hypotheses"]["H0"]
    thresholds = record["thresholds"]
    lines = [
        "Gate A over the development split (dev only; any frozen record "
        "refuses the run)",
        f"counts: positives {record['counts']['positives']}, matched twins "
        f"{record['counts']['twins']}, natural clean "
        f"{record['counts']['natural_clean']}",
        f"fixed n (matched twins): {record['fixed_n']}; registered McNemar "
        f"sample sizes: {thresholds['mcnemar_samples_large']} large edge, "
        f"{thresholds['mcnemar_samples_moderate']} moderate, "
        f"{thresholds['mcnemar_samples_small']} small",
        f"H1 recall versus the judge ({JUDGE}): {h1['status']} -- greenwash "
        f"recall {_fmt_rate(h1['recall_greenwash'])}, judge recall "
        f"{_fmt_rate(h1['recall_judge'])}, gap {h1['recall_gap']:.3f} vs "
        f"margin -0.100 {_pass(h1['non_inferior'])}; cost per case "
        f"{h1['cost_per_case_greenwash']:.3f} vs "
        f"{h1['cost_per_case_judge']:.3f}, ratio {h1['cost_ratio']:.1f} vs "
        f"10.0 {_pass(h1['cost_edge_met'])}; variance "
        f"{h1['variance_greenwash']} / {h1['variance_judge']} "
        f"{'reported' if h1['variance_reported'] else 'NOT reported'}; "
        f"threshold: margin -0.100 and cost ratio 10.0 and reported variance",
        f"H2 twin false alarms versus B0: {h2['status']} -- greenwash "
        f"{_fmt_rate(h2['twin_false_alarm_greenwash'])}, B0 "
        f"{_fmt_rate(h2['twin_false_alarm_b0'])}, discordant greenwash-only "
        f"{h2['discordant']['greenwash_only']} b0-only "
        f"{h2['discordant']['b0_only']}, exact McNemar p "
        f"{h2['mcnemar_p']:.4f} at the fixed n {record['fixed_n']}; "
        f"threshold: exact McNemar alpha 0.05",
        f"H3 twin false alarms versus {COMPETITOR}: {h3['status']} -- "
        f"greenwash {_fmt_rate(h3['twin_false_alarm_greenwash'])}, B3 "
        f"{_fmt_rate(h3['twin_false_alarm_b3'])}, gap "
        f"{h3['twin_edge_gap']:.3f} vs twin edge 0.100; abstention "
        f"{_fmt_rate(h3['abstention'])} "
        f"{'<=' if h3['abstention']['estimate'] <= thresholds['abstention_ceiling'] else '>'} "
        f"0.200 reported; threshold: twin edge 0.100 and abstention ceiling "
        f"0.200",
        f"H0 Greenwash and the pinned competitor ({COMPETITOR}): "
        f"{h0['status']} at the fixed n {record['fixed_n']} -- discordant "
        f"greenwash-only {h0['discordant']['greenwash_only']} b3-only "
        f"{h0['discordant']['b3_only']}, exact McNemar p "
        f"{h0['mcnemar_p']:.4f}; threshold: exact McNemar alpha 0.05",
        f"decision: {record['decision']} -- deciding threshold: "
        f"{record['deciding_threshold']} "
        f"({DECIDING[record['deciding_threshold']]})",
    ]
    return "\n".join(lines) + "\n"


def summary(record: dict) -> dict:
    """The machine-readable summary: decision exactly go, pivot or stop.

    Numbers, counts and whitespace-free status tokens, and nothing else --
    no prose verdict lives in this object, so no reader can quote one from
    a machine file.
    """
    return {
        "gate": record["gate"],
        "split": record["split"],
        "decision": record["decision"],
        "deciding_threshold": record["deciding_threshold"],
        "fixed_n": record["fixed_n"],
        "counts": dict(record["counts"]),
        "thresholds": dict(record["thresholds"]),
        "hypotheses": json.loads(json.dumps(record["hypotheses"])),
    }


def summary_path(out: Path) -> Path:
    """Where the machine summary is written: beside the report."""
    return Path(out).parent / (Path(out).stem + "-summary.json")


# -- the command -------------------------------------------------------------

DEFAULT_ASSUMPTIONS = HERE / "assumptions.json"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="gate_a.py", description=__doc__)
    parser.add_argument("--dev", default=str(HERE / "results" / "gate-a" / "dev-table.json"),
                        help="the dev evaluation table (Greenwash's dev results)")
    parser.add_argument("--labelled", default=str(HERE / "results" / "gate-a" / "labelled.json"),
                        help="the labelled dev cases (adjudicated labels)")
    parser.add_argument("--baselines", default=str(HERE / "results" / "gate-a" / "baselines.json"),
                        help="the baseline results B0, B1, B2, B3")
    parser.add_argument("--assumptions", default=str(DEFAULT_ASSUMPTIONS),
                        help="the assumptions register (data file)")
    parser.add_argument("--out", default=str(HERE / "results" / "gate_a_report.txt"),
                        help="the report file")
    parser.add_argument("--summary", default=None,
                        help="the machine summary (default: beside the report)")
    args = parser.parse_args(argv)
    try:
        payloads = []
        for label, path in (("dev table", args.dev),
                            ("labelled cases", args.labelled),
                            ("baseline results", args.baselines),
                            ("assumptions register", args.assumptions)):
            try:
                payloads.append(json.loads(Path(path).read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as exc:
                _fail(f"{label}: cannot read {path}: {exc}; refusing")
        record = gate_a(*payloads)
    except GateAError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_REFUSED
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(record), encoding="utf-8")
    summary_file = Path(args.summary) if args.summary else summary_path(out)
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(json.dumps(summary(record), indent=2) + "\n",
                            encoding="utf-8")
    print(render(record), end="")
    print(f"written -> {out}")
    print(f"written -> {summary_file}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
