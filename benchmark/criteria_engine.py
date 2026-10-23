#!/usr/bin/env python3
"""The launch criteria engine: the nine criteria decided in one place.

One library call turns the computed evaluation table, the pre-registration
record and the claim-ledger rows -- plus the two injected results whose
inputs live outside those three (the rebuild-equality flag for L6 and the
announcement-check result for L7) -- into exactly one decision: LAUNCH when
every criterion holds, NARROW otherwise, naming the first failing criterion
in fixed order (L1-L9) and every failing criterion.

The contracts, each one load-bearing:

* **The launch cell decides alone.** L1-L5 evaluate the pre-registered
  launch configuration (`record["launch_configuration"]`) only. A
  descriptive or baseline cell that passes can never rescue a launch cell
  that fails, and can never fail one.
* **L1 and L2 decide on the gate-deciding interval**: the exact
  Clopper-Pearson bound at the effective counts, via `evaluation.bound_gate`
  over the computed table's rate entries. Strict recall counts an abstention
  on a positive as a miss; the twin false-alarm bound decides over the real
  legitimate twins. A case-level bound that passes while the effective-n
  bound fails is the reported failure.
* **L3 separates the abstention ceilings**: the measured abstention rate is
  held under the ceiling on twins and on natural clean passes separately,
  so refusing to decide is visible per class and never pooled away.
* **L4 applies the pre-registered determinism rule**: zero byte differences
  over at least `runs` (5) reruns of every frozen case, or of a stratified
  sample of at least `min_sample` (100) cases covering every technique cell.
* **L5 requires the integrity suite to have run, with zero successful
  modifications.** A suite that did not run is an unevaluated criterion.
* **L6 and L7 consume injected results**, so every decision is computed in
  one place: L6 is the rebuild-equality flag (offline rebuild byte-identical
  to the committed artifacts), L7 the announcement-check result. L7 also
  consumes the claim-ledger rows: every claim the announcement names must
  map to a ledger row, or it is a claim outside the ledger.
* **L8 is the sample floor, a criterion**: effective n, distinct
  repositories and the per-repository case cap, checked per class
  (positives, twins, natural clean).
* **L9 is label quality**: the double-labeled case count and PABAK.
* **Fail closed.** A missing cell, an empty class, an interval that cannot
  be computed, or a check that did not run is a FAILED criterion with
  reason `not evaluated` -- never a skip, never LAUNCH.
* **No prose, no side inputs.** The engine reads no prose and no file
  outside its named inputs. The thresholds are gate-as-data: injected as the
  `thresholds` payload, or loaded from the file the pre-registration record
  pins (`record["thresholds_file"]`), with the repository's own
  `benchmark/thresholds.json` as the last resort. Unreadable gate data fails
  closed: every criterion is `not evaluated` and the decision is NARROW.

The seam (a library call -- the launch command is a separate ticket):

    decision = evaluate_criteria(table, record, ledger_rows,
                                 rebuild_equal, announcement)

`decision` is a dict: `decision` (LAUNCH/NARROW), `deciding_criterion` (the
first failing criterion in fixed order, or None), `failing_criteria` (all of
them, fixed order), `criteria` (one entry per L1-L9 carrying value,
threshold, interval, effective n, pass and reason), `launch_configuration`,
and `designed_for` (the sample table the report prints).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import evaluation  # noqa: E402
import preregistration  # noqa: E402
from greenwash.evidence import EvidenceError  # noqa: E402

LAUNCH = "LAUNCH"
NARROW = "NARROW"
NOT_EVALUATED = "not evaluated"
UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"

# The fixed order the decision names its failures in. Changing this order
# changes which criterion decides; it is part of the gate, not a detail.
CRITERIA = preregistration.CRITERIA


# -- input validation: anything that cannot decide fails closed --------------

def _finite(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _integer(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _rate_entry(pooled, key):
    """One pooled rate entry, or None when it cannot decide a bound.

    The entry must carry what the gate-deciding interval is computed from:
    counts, the effective-n Clopper-Pearson interval and the effective n. A
    malformed entry is not a low number; it decides nothing, which is a
    failure, not a pass.
    """
    if not isinstance(pooled, dict):
        return None
    entry = pooled.get(key)
    if not isinstance(entry, dict):
        return None
    n, k = entry.get("n"), entry.get("k")
    if not _integer(n) or n < 0 or not _integer(k) or k < 0:
        return None
    interval = entry.get("clopper_pearson_effective")
    if not (isinstance(interval, (list, tuple)) and len(interval) == 2
            and all(_finite(bound) for bound in interval)):
        return None
    if not _finite(entry.get("n_eff")):
        return None
    return entry


def _launch_cell(table, record):
    """The pre-registered launch cell, or None: no other cell is readable."""
    if not isinstance(table, dict) or not isinstance(record, dict):
        return None
    detectors = table.get("detectors")
    if not isinstance(detectors, dict):
        return None
    launch = str(record.get("launch_configuration") or "").strip()
    if not launch:
        return None
    cell = detectors.get(launch)
    return cell if isinstance(cell, dict) else None


def _pooled(ctx):
    cell = ctx["cell"]
    if not isinstance(cell, dict):
        return None
    pooled = cell.get("pooled")
    return pooled if isinstance(pooled, dict) else None


def _thresholds_payload(record, thresholds):
    """The gate as data: injected, pinned by the record, or the repository's."""
    if isinstance(thresholds, dict) and isinstance(thresholds.get("criteria"),
                                                   dict):
        return thresholds
    path = str((record or {}).get("thresholds_file") or "").strip() \
        if isinstance(record, dict) else ""
    source = path or str(ROOT / preregistration.THRESHOLDS)
    try:
        return preregistration.load_thresholds(source)
    except EvidenceError:
        return None


def _spec(criteria, cid):
    if not isinstance(criteria, dict):
        return None
    entry = criteria.get(cid)
    if not isinstance(entry, dict):
        return None
    return {"criterion": entry.get("criterion"), "relation": entry.get("relation"),
            "value": entry.get("value")}


def _holds(measured, relation: str, threshold: float) -> bool:
    return measured >= threshold if relation == ">=" else measured <= threshold


# -- the criterion results ---------------------------------------------------

def _result(cid, spec, passed, value=None, interval=None, n_eff=None,
            reason=None, detail=""):
    spec = spec or {}
    return {"id": cid, "criterion": spec.get("criterion"),
            "relation": spec.get("relation"), "threshold": spec.get("value"),
            "value": value, "interval": interval, "n_eff": n_eff,
            "pass": bool(passed), "reason": reason, "detail": detail,
            "state": MEASURED}


def _unevaluated(cid, spec, detail):
    """A criterion that cannot be evaluated is a failed, UNMEASURED criterion."""
    row = _result(cid, spec, False, reason=NOT_EVALUATED, detail=detail)
    row["state"] = UNMEASURED
    return row


def _bound_criterion(ctx, cid, spec, key):
    """L1/L2: a bound of a launch-cell rate, decided on the effective-n interval."""
    if spec is None:
        return _unevaluated(cid, None,
                            "the gate data does not name this criterion")
    relation, threshold = spec.get("relation"), spec.get("value")
    if not _finite(threshold):
        return _unevaluated(cid, spec, "the threshold is not a number")
    entry = _rate_entry(_pooled(ctx), key)
    if entry is None:
        return _unevaluated(
            cid, spec, f"the computed table has no {key} rate for the launch "
                       f"cell; the criterion cannot be evaluated")
    if not entry["n"]:
        return _unevaluated(
            cid, spec, f"{key} {entry['k']}/0: the class is empty; a bound "
                       f"cannot pass on nothing")
    gate = evaluation.bound_gate(entry, relation, float(threshold))
    return _result(cid, spec, gate["pass"], value=gate["measured"],
                   interval=list(entry["clopper_pearson_effective"]),
                   n_eff=entry["n_eff"], detail=gate["arithmetic"])


def _evaluate_l1(ctx, spec):
    return _bound_criterion(ctx, "L1", spec, "strict_recall")


def _evaluate_l2(ctx, spec):
    return _bound_criterion(ctx, "L2", spec, "twin_false_alarm")


L3_CLASSES = (("twins", "twin_abstention"),
              ("natural_clean", "natural_clean_abstention"))


def _evaluate_l3(ctx, spec):
    """L3: the abstention ceiling, held separately on twins and natural clean."""
    if spec is None:
        return _unevaluated("L3", None, "the gate data does not name this criterion")
    relation, ceiling = spec.get("relation"), spec.get("value")
    if not _finite(ceiling):
        return _unevaluated("L3", spec, "the ceiling is not a number")
    pooled = _pooled(ctx)
    value, interval, n_eff, parts = {}, {}, {}, []
    unevaluable, failed = [], []
    for label, key in L3_CLASSES:
        entry = _rate_entry(pooled, key)
        if entry is None or not entry["n"] or not _finite(entry.get("estimate")):
            value[label] = None
            unevaluable.append(label)
            parts.append(f"{label}: not evaluated (no {key} rate, or empty)")
            continue
        estimate = entry["estimate"]
        value[label] = estimate
        interval[label] = list(entry["clopper_pearson_effective"])
        n_eff[label] = entry["n_eff"]
        holds = _holds(estimate, relation, float(ceiling))
        failed += [] if holds else [label]
        parts.append(f"{label} {entry['k']}/{entry['n']} = {estimate:.3f} "
                     f"{relation} {ceiling} -> {'PASS' if holds else 'FAIL'} "
                     f"(eff CP95 [{interval[label][0]:.3f}, "
                     f"{interval[label][1]:.3f}], n_eff {entry['n_eff']:.2f})")
    passed = not unevaluable and not failed
    return _result("L3", spec, passed, value=value, interval=interval or None,
                   n_eff=n_eff or None,
                   reason=NOT_EVALUATED if unevaluable else None,
                   detail="; ".join(parts))


def _cell_techniques(ctx):
    """Every technique cell of the launch configuration, or None if unknown."""
    cell = ctx["cell"]
    if not isinstance(cell, dict):
        return None
    cells = cell.get("cells")
    if not isinstance(cells, dict) or not cells:
        return None
    techniques = {row.get("technique") for row in cells.values()
                  if isinstance(row, dict) and row.get("technique")}
    return techniques or None


def _evaluate_l4(ctx, spec):
    """L4: the pre-registered determinism rule, applied mechanically."""
    if spec is None:
        return _unevaluated("L4", None, "the gate data does not name this criterion")
    rule = spec.get("value")
    if not isinstance(rule, dict):
        return _unevaluated("L4", spec, "the determinism rule is missing")
    max_differences, runs_needed = rule.get("byte_differences"), rule.get("runs")
    min_sample = rule.get("min_sample")
    if not (_integer(max_differences) and _integer(runs_needed)
            and _integer(min_sample)):
        return _unevaluated("L4", spec, "the determinism rule is malformed")
    result = ctx["table"].get("determinism")
    if not isinstance(result, dict):
        return _unevaluated("L4", spec,
                            "the computed table carries no determinism result; "
                            "the check did not run")
    differences, runs = result.get("byte_differences"), result.get("runs")
    cases, techniques = result.get("cases"), result.get("techniques")
    if (not _integer(differences) or differences < 0 or not _integer(runs)
            or not isinstance(cases, (list, tuple)) or not cases
            or not isinstance(techniques, (list, tuple))):
        return _unevaluated("L4", spec,
                            "the determinism result is incomplete; the rule "
                            "was not applied to any case")
    frozen = ctx["table"].get("gate_inputs")
    if not isinstance(frozen, (list, tuple)) or not frozen:
        pooled = _pooled(ctx)
        frozen = pooled.get("cases") if isinstance(pooled, dict) else None
    every_case = bool(isinstance(frozen, (list, tuple)) and frozen
                      and set(frozen) <= set(cases))
    required = _cell_techniques(ctx)
    covering = bool(required is not None and required <= set(techniques))
    stratified = len(cases) >= min_sample and covering
    if not every_case and not stratified and required is None \
            and not (isinstance(frozen, (list, tuple)) and frozen):
        return _unevaluated("L4", spec,
                            "neither the frozen case list nor the technique "
                            "cells can be established; the sample cannot be "
                            "checked against the rule")
    zero = differences <= max_differences
    enough_runs = runs >= runs_needed
    passed = zero and enough_runs and (every_case or stratified)
    detail = (f"{differences} byte difference(s) over {runs} run(s) of "
              f"{len(cases)} case(s): {'zero' if zero else 'NOT ZERO'}; "
              f"runs {runs} >= {runs_needed}: "
              f"{'PASS' if enough_runs else 'FAIL'}; sample covers every "
              f"frozen case: {every_case}; stratified sample >= {min_sample} "
              f"covering every technique cell: {stratified}")
    return _result("L4", spec, passed,
                   value={"byte_differences": differences, "runs": runs,
                          "cases_sampled": len(cases),
                          "every_frozen_case": every_case,
                          "covers_every_technique_cell": covering},
                   detail=detail)


def _evaluate_l5(ctx, spec):
    """L5: the integrity suite ran, and zero successful modifications."""
    if spec is None:
        return _unevaluated("L5", None, "the gate data does not name this criterion")
    rule = spec.get("value")
    if not isinstance(rule, dict):
        return _unevaluated("L5", spec, "the integrity rule is missing")
    allowed = rule.get("successful_modifications")
    if not isinstance(rule.get("suite_ran"), bool) or not _integer(allowed):
        return _unevaluated("L5", spec, "the integrity rule is malformed")
    result = ctx["table"].get("integrity")
    if not isinstance(result, dict):
        return _unevaluated("L5", spec,
                            "the computed table carries no integrity result; "
                            "the check did not run")
    ran, successes = result.get("suite_ran"), result.get("successful_modifications")
    if not isinstance(ran, bool) or not _integer(successes) or successes < 0:
        return _unevaluated("L5", spec,
                            "the integrity result is incomplete; the check "
                            "did not run")
    if not ran:
        return _unevaluated("L5", spec,
                            "the integrity suite did not run; L5 requires it "
                            "ran with zero successful modifications")
    passed = successes <= allowed
    return _result("L5", spec, passed,
                   value={"suite_ran": True, "successful_modifications": successes},
                   detail=f"integrity suite ran; successful modifications "
                          f"{successes} <= {allowed} -> "
                          f"{'PASS' if passed else 'FAIL'}")


def _evaluate_l6(ctx, spec):
    """L6: the injected rebuild-equality flag, decided here."""
    if spec is None:
        return _unevaluated("L6", None, "the gate data does not name this criterion")
    rule = spec.get("value")
    expected = rule.get("byte_identical_rebuild") if isinstance(rule, dict) else None
    if not isinstance(expected, bool):
        return _unevaluated("L6", spec, "the reproducibility rule is malformed")
    rebuild = ctx["rebuild"]
    if rebuild is None:
        return _unevaluated("L6", spec,
                            "no rebuild-equality result was injected; the "
                            "check cannot be evaluated")
    if not isinstance(rebuild, bool):
        return _unevaluated("L6", spec,
                            "the injected rebuild-equality result is not a flag")
    passed = rebuild == expected
    return _result("L6", spec, passed,
                   value={"byte_identical_rebuild": rebuild},
                   detail=f"byte-identical rebuild: {rebuild} == {expected} -> "
                          f"{'PASS' if passed else 'FAIL'}")


def _claim_id(row):
    if isinstance(row, dict):
        return row.get("claim")
    return getattr(row, "claim", None)


def _evaluate_l7(ctx, spec):
    """L7: the injected announcement check, cross-checked against the ledger rows."""
    if spec is None:
        return _unevaluated("L7", None, "the gate data does not name this criterion")
    rule = spec.get("value")
    allowed = rule.get("claims_outside_ledger") if isinstance(rule, dict) else None
    if not _integer(allowed):
        return _unevaluated("L7", spec, "the ledger-coverage rule is malformed")
    result = ctx["announcement"]
    if not isinstance(result, dict):
        return _unevaluated("L7", spec,
                            "no announcement-check result was injected; the "
                            "check cannot be evaluated")
    outside = result.get("claims_outside_ledger")
    claims = result.get("claims") or []
    if not _integer(outside) or outside < 0 or not isinstance(claims, (list, tuple)):
        return _unevaluated("L7", spec,
                            "the announcement-check result is incomplete")
    registered = {_claim_id(row) for row in (ctx["rows"] or [])} - {None}
    unmapped = [claim for claim in claims if claim not in registered]
    total = outside + len(unmapped)
    passed = total <= allowed
    return _result("L7", spec, passed,
                   value={"claims_outside_ledger": total,
                          "unmapped_claims": len(unmapped)},
                   detail=f"claims outside their row's allowed wording: "
                          f"{outside}; claim sentences mapping to no ledger "
                          f"row: {len(unmapped)}; total {total} <= {allowed} "
                          f"-> {'PASS' if passed else 'FAIL'}")


L8_CLASSES = (("positives", "strict_recall"),
              ("twins", "twin_false_alarm"),
              ("natural_clean", "natural_clean_false_alarm"))


def _evaluate_l8(ctx, spec):
    """L8: the sample floor per class -- effective n, repositories, case cap."""
    if spec is None:
        return _unevaluated("L8", None, "the gate data does not name this criterion")
    rule = spec.get("value")
    if not isinstance(rule, dict):
        return _unevaluated("L8", spec, "the sample-floor rule is missing")
    n_floor = rule.get("effective_n_per_class")
    repos_floor = rule.get("distinct_repositories_per_class")
    cap = rule.get("max_cases_per_repository")
    if not (_finite(n_floor) and _integer(repos_floor) and _integer(cap)):
        return _unevaluated("L8", spec, "the sample-floor rule is malformed")
    pooled = _pooled(ctx)
    value, n_eff, parts, unevaluable, failed = {}, {}, [], [], []
    for label, key in L8_CLASSES:
        entry = _rate_entry(pooled, key)
        sizes = entry.get("cluster_sizes") if entry is not None else None
        if (entry is None or not entry["n"]
                or not _integer(entry.get("n_repos"))
                or not isinstance(sizes, (list, tuple)) or not sizes
                or not all(_integer(size) and size > 0 for size in sizes)):
            value[label] = None
            unevaluable.append(label)
            parts.append(f"{label}: not evaluated (no {key} rate, empty class, "
                         f"or no repository clusters)")
            continue
        per_repository = max(sizes)
        measured = {"n_eff": entry["n_eff"], "n_repos": entry["n_repos"],
                    "max_cases_per_repository": per_repository}
        value[label] = measured
        n_eff[label] = entry["n_eff"]
        holds = (entry["n_eff"] >= n_floor
                 and entry["n_repos"] >= repos_floor
                 and per_repository <= cap)
        failed += [] if holds else [label]
        parts.append(f"{label}: n_eff {entry['n_eff']:.2f} >= {n_floor}: "
                     f"{entry['n_eff'] >= n_floor}; repos {entry['n_repos']} "
                     f">= {repos_floor}: {entry['n_repos'] >= repos_floor}; "
                     f"max {per_repository} <= {cap}: {per_repository <= cap}"
                     f" -> {'PASS' if holds else 'FAIL'}")
    passed = not unevaluable and not failed
    return _result("L8", spec, passed, value=value, n_eff=n_eff or None,
                   reason=NOT_EVALUATED if unevaluable else None,
                   detail="; ".join(parts))


def _evaluate_l9(ctx, spec):
    """L9: label quality -- the double-labeled count and PABAK."""
    if spec is None:
        return _unevaluated("L9", None, "the gate data does not name this criterion")
    rule = spec.get("value")
    if not isinstance(rule, dict):
        return _unevaluated("L9", spec, "the label-quality rule is missing")
    count_floor = rule.get("double_labeled_cases")
    pabak_floor = rule.get("pabak")
    if not (_integer(count_floor) and _finite(pabak_floor)):
        return _unevaluated("L9", spec, "the label-quality rule is malformed")
    result = ctx["table"].get("labels")
    if not isinstance(result, dict):
        return _unevaluated("L9", spec,
                            "the computed table carries no double-labeled "
                            "sample; the check cannot be evaluated")
    count, pabak = result.get("double_labeled_cases"), result.get("pabak")
    if not _integer(count) or count < 0 or not _finite(pabak):
        return _unevaluated("L9", spec,
                            "the double-labeled sample is incomplete (count or "
                            "PABAK missing or not a number)")
    passed = count >= count_floor and pabak >= pabak_floor
    return _result("L9", spec, passed,
                   value={"double_labeled_cases": count, "pabak": pabak},
                   detail=f"double-labeled {count} >= {count_floor}: "
                          f"{count >= count_floor}; PABAK {pabak} >= "
                          f"{pabak_floor}: {pabak >= pabak_floor} -> "
                          f"{'PASS' if passed else 'FAIL'}")


_EVALUATORS = {"L1": _evaluate_l1, "L2": _evaluate_l2, "L3": _evaluate_l3,
               "L4": _evaluate_l4, "L5": _evaluate_l5, "L6": _evaluate_l6,
               "L7": _evaluate_l7, "L8": _evaluate_l8, "L9": _evaluate_l9}


# -- the engine --------------------------------------------------------------

_DESIGNED_FOR_CACHE = None


def _designed_for():
    """The designed-for table, computed once and copied per decision.

    The arithmetic is deterministic, so the rows are cached; each decision
    gets its own copy so no caller can mutate what a later run decides on.
    """
    global _DESIGNED_FOR_CACHE
    if _DESIGNED_FOR_CACHE is None:
        _DESIGNED_FOR_CACHE = json.loads(json.dumps(evaluation.designed_for_table()))
    return json.loads(json.dumps(_DESIGNED_FOR_CACHE))


def evaluate_criteria(table, record, ledger_rows, rebuild_equal, announcement,
                      thresholds=None) -> dict:
    """L1-L9 in fixed order, one decision out: LAUNCH or NARROW.

    `table` is the computed evaluation table (the evaluation runner's report,
    with its `determinism`, `integrity` and `labels` results beside the
    detector cells); `record` is the pre-registration record; `ledger_rows`
    are the claim-ledger rows; `rebuild_equal` and `announcement` are the two
    injected results (L6's rebuild-equality flag, L7's announcement-check
    result). `thresholds` optionally injects the gate-as-data payload;
    otherwise the file the record pins is loaded.
    """
    payload = _thresholds_payload(record, thresholds)
    criteria = payload.get("criteria") if isinstance(payload, dict) else None
    ctx = {"table": table if isinstance(table, dict) else {},
           "cell": _launch_cell(table, record), "rows": ledger_rows,
           "rebuild": rebuild_equal, "announcement": announcement}
    results = [_EVALUATORS[cid](ctx, _spec(criteria, cid)) for cid in CRITERIA]
    failing = [row for row in results if not row["pass"]]
    unmeasured = [row["id"] for row in results if row.get("state") == UNMEASURED]
    return {
        "decision": LAUNCH if not failing and not unmeasured else NARROW,
        "deciding_criterion": failing[0]["id"] if failing else None,
        "failing_criteria": [row["id"] for row in failing],
        "unmeasured_criteria": unmeasured,
        "criteria": results,
        "launch_configuration": str(
            (record or {}).get("launch_configuration", "")) or None,
        "designed_for": _designed_for(),
    }
