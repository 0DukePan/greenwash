#!/usr/bin/env python3
"""The reproduction command: the headline table, rebuilt from pinned artifacts.

One command rebuilds the published headline table -- benchmark/results/
headline.md -- from the four artifacts a release freezes beside it:

    corpus manifest          tests/fixtures/evaluation/FROZEN.json
    frozen annotations       benchmark/reproduction/annotations.json
    detector configurations  benchmark/reproduction/detectors.json
    seeds                    benchmark/reproduction/seeds.json

The contracts, each one load-bearing:

* **Every pinned artifact is hash-verified before any number is computed.**
  Each artifact's bytes are checked against its sha256 in
  benchmark/reproduction/pins.json first; a mismatch aborts (exit 2) naming
  the artifact, its file and both hashes, so no table is ever rebuilt from
  inputs that are not the ones the release froze.
* **The rebuild runs no model.** The pinned detector configurations name
  model-free detectors only (B0 the path rule, B1 the held-out tests), run in
  process; a configuration that would need a model or an external tool is
  refused by name -- a reader verifies the release's numbers without rerunning
  any model. The version each detector reports must be the version the
  configuration pins, or the rebuild refuses and names the configuration.
* **A second run is byte-identical.** The table carries no wall-clock values:
  no generation timestamp, no measured wall time. Wall seconds are a run-time
  measurement -- `benchmark/evaluation.py` measures them and gates them (G8)
  when the evaluation runs -- and are deliberately not pinned.
* **Seeds fix whatever randomness exists.** Every detector call draws from a
  generator seeded by the pinned seeds (one seed per repeat), and the seed list
  is printed in the table header, so a rebuilt number is tied to the run that
  produced it.
* **The corpus and the frozen annotations must agree.** The corpus loads
  through the corpus kit (its frozen manifest verified first), and every gold
  field of every case is cross-checked against the frozen annotations; a
  disagreement names the frozen annotations and the case.

Run:  python benchmark/reproduce.py [--root DIR] [--out FILE]
Writes benchmark/results/headline.md and prints it. Exit 0: rebuilt, byte-
identical to the published table. Exit 2: a pinned artifact refused to load
(mismatch named).

This module extends the evaluation runner rather than restating it: the rows,
the exact intervals and the mechanical gates come from benchmark/evaluation.py;
this command decides what may enter them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import evaluation  # noqa: E402
from greenwash import baselines, corpus  # noqa: E402
from greenwash.evidence import EvidenceError  # noqa: E402

EXIT_OK = 0
EXIT_REFUSED = 2

PINS = "benchmark/reproduction/pins.json"
DEFAULT_OUT = "benchmark/results/headline.md"

# The pinned artifacts, verified in this order. The name is what an abort
# prints; a release is only as pinned as these four.
ARTIFACTS = ("corpus manifest", "frozen annotations", "detector configurations",
             "seeds")

# The gold fields a frozen annotation pins, per corpus.GOLD_FIELDS minus the id
# (the key) -- the fields a blind annotator must not see.
GOLD = ("label", "technique", "origin", "split")

# What a detector configuration may pin: detectors that run in process and
# involve no model. The judge (B2) is a model and the competitor (B3) is an
# external tool; neither can take part in a rebuild a reader runs offline.
MODEL_FREE = {"path-rule": baselines.PathRuleBaseline,
              "held-out": baselines.HeldoutBaseline}


class _Seeded:
    """A detector whose draws come from the pinned seeds, never from the clock.

    The runner calls each detector `repeats` times per case, repeat after
    repeat; the i-th call on any case draws from the i-th pinned seed, so one
    seed fixes one repeat exactly as the pinned run had it. The draw is
    seeded on a string (never a tuple): string seeds hash deterministically,
    while the hash of a tuple is randomised per process.
    """

    def __init__(self, detector, seeds):
        self.id = detector.id
        self._detector, self._seeds = detector, tuple(seeds)
        self._calls = 0

    def run(self, record):
        seed = self._seeds[self._calls % len(self._seeds)]
        random.seed(f"greenwash-reproduce/{seed}/{record.case.id}/{self._calls}")
        self._calls += 1
        return self._detector.run(record)


# -- the pin records: hash-verified before anything is trusted ---------------

def _read_pin_records(root: Path) -> dict:
    path = root / PINS
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvidenceError(f"{PINS}: could not be read: {exc}") from exc
    except ValueError as exc:
        raise EvidenceError(f"{PINS}: not JSON: {exc}") from exc
    artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
    if not isinstance(artifacts, dict):
        raise EvidenceError(f"{PINS}: no artifact pin records; the table cannot "
                            "be rebuilt from artifacts nobody pinned")
    return artifacts


def verify_pins(root: str | Path) -> dict:
    """Every pinned artifact's bytes against its recorded sha256, in order.

    The bytes are hashed before any of them is parsed as JSON, so a tampered
    artifact aborts naming the artifact -- never a parse error from a file
    this command has not yet established it may trust.
    """
    root = Path(root)
    artifacts = _read_pin_records(root)
    verified = {}
    for name in ARTIFACTS:
        entry = artifacts.get(name)
        if not isinstance(entry, dict) or not str(entry.get("path", "")).strip():
            raise EvidenceError(f"{PINS}: no pin record for the {name} artifact")
        relative = str(entry["path"])
        try:
            raw = (root / relative).read_bytes()
        except OSError as exc:
            raise EvidenceError(f"pinned artifact {name} ({relative}): could "
                                f"not be read: {exc}") from exc
        found = hashlib.sha256(raw).hexdigest()
        recorded = str(entry.get("sha256", ""))
        if found != recorded:
            raise EvidenceError(f"pinned artifact {name} ({relative}): hash "
                                f"mismatch: recorded {recorded}, found {found}")
        verified[name] = {"path": relative, "sha256": found}
    return verified


def _read_artifact(root: Path, verified: dict, name: str) -> dict:
    """One pinned artifact's JSON, parsed only now that its hash is proven."""
    relative = verified[name]["path"]
    try:
        payload = json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"pinned artifact {name} ({relative}): could not "
                            f"be parsed: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvidenceError(f"pinned artifact {name} ({relative}): not a JSON "
                            "object")
    return payload


# -- the four artifacts, each one read as what it pins -----------------------

def _annotations(root: Path, verified: dict) -> dict:
    payload = _read_artifact(root, verified, "frozen annotations")
    annotations = payload.get("annotations")
    if not isinstance(annotations, dict) or not annotations:
        raise EvidenceError("frozen annotations: no annotations pinned")
    for case_id, entry in annotations.items():
        if not isinstance(entry, dict):
            raise EvidenceError(f"frozen annotations: {case_id} is not a "
                                "record of gold fields")
    return annotations


def _check_annotations(records, annotations: dict) -> None:
    """The corpus and the frozen annotations must agree, case by case."""
    cases = {record.case.id: record.case for record in records}
    for case_id in sorted(set(annotations) - set(cases)):
        raise EvidenceError(f"frozen annotations: {case_id} is not among the "
                            "corpus cases")
    for case_id in sorted(cases):
        pinned = annotations.get(case_id)
        if pinned is None:
            raise EvidenceError(f"frozen annotations: no annotation pinned for "
                                f"corpus case {case_id}")
        case = cases[case_id]
        for field in GOLD:
            if pinned.get(field) != getattr(case, field):
                raise EvidenceError(
                    f"frozen annotations: {case_id} pins {field} "
                    f"{pinned.get(field)!r} but the corpus case says "
                    f"{getattr(case, field)!r}")


def _detector_config(root: Path, verified: dict) -> list:
    payload = _read_artifact(root, verified, "detector configurations")
    entries = payload.get("detectors")
    if not isinstance(entries, list) or not entries:
        raise EvidenceError("detector configurations: no detectors pinned; the "
                            "headline table has no columns to rebuild")
    return entries


def _build_detectors(entries: list, seeds: tuple) -> tuple:
    """The pinned detectors, seeded. A model in the configuration is refused."""
    detectors = []
    seen = set()
    for entry in entries:
        name = str(entry.get("id", "")).strip()
        baseline = str(entry.get("baseline", "")).strip()
        if not name or not baseline:
            raise EvidenceError("detector configurations: every entry needs an "
                                "id and a baseline")
        if name in seen:
            raise EvidenceError(f"detector configurations: {name} is pinned "
                                "twice")
        seen.add(name)
        if baseline not in MODEL_FREE:
            raise EvidenceError(
                f"detector configurations: detector {name} names {baseline!r}, "
                "which is not model-free; the reproduction command rebuilds the "
                "headline table without any model, so only "
                f"{', '.join(sorted(MODEL_FREE))} can be pinned")
        detectors.append(_Seeded(MODEL_FREE[baseline](), seeds))
    return tuple(detectors)


def _check_versions(report: dict, entries: list) -> None:
    """A detector that does not report its pinned version is not the pinned one."""
    for entry in entries:
        name = str(entry.get("id", "")).strip()
        pinned, reported = entry.get("version"), report["detectors"][name]["version"]
        if pinned != reported:
            raise EvidenceError(f"detector configurations: {name} pins version "
                                f"{pinned!r} but the run reports {reported!r}")


def _seeds(root: Path, verified: dict) -> tuple:
    payload = _read_artifact(root, verified, "seeds")
    seeds = payload.get("seeds")
    if (not isinstance(seeds, list) or not seeds
            or not all(isinstance(seed, int) for seed in seeds)):
        raise EvidenceError("seeds: the pinned seeds must be a non-empty list "
                            "of integers; one seed fixes one repeat")
    return tuple(seeds)


# -- the table: no wall-clock value may enter it -----------------------------

def _fmt_rate(entry) -> str:
    if not entry["n"]:
        return f"{entry['k']}/0=-- (CP95 [--, --], Wilson [--, --])"
    lo, hi = entry["clopper_pearson"]
    wlo, whi = entry["wilson"]
    estimate = f"{entry['estimate']:.3f}" if entry["estimate"] is not None else "--"
    return (f"{entry['k']}/{entry['n']}={estimate} "
            f"(CP95 [{lo:.3f}, {hi:.3f}], Wilson [{wlo:.3f}, {whi:.3f}])")


def _fmt_row(label: str, row: dict) -> str:
    return (f"| {label} | {row['n']} | {row['tampered']} | {row['clean']} | "
            f"{_fmt_rate(row['strict_recall'])} | "
            f"{_fmt_rate(row['decided_recall'])} | "
            f"{_fmt_rate(row['false_alarm'])} | "
            f"{_fmt_rate(row['abstention'])} | "
            f"{row['cost']:.1f} | {row['variance']:.3f} |")


def _fmt_gate(gate: dict) -> str:
    if gate["metric"] == "wall_seconds":
        return (f"{gate['id']} {gate['name']}: run-time measurement "
                f"({gate['relation']} {gate['threshold']}) -- measured when the "
                "evaluation runs, never pinned")
    verdict = "PASS" if gate["pass"] else "FAIL"
    arithmetic = re.sub(r", wall [0-9.]+s", "", gate["arithmetic"])
    return f"{gate['id']} {gate['name']}: {verdict} -- {arithmetic}"


def render_headline(verified: dict, seeds: tuple, report: dict) -> str:
    """The published table: cells first, cost and variance beside every rate.

    Wall seconds appear nowhere -- not in a row, not in a gate's arithmetic --
    because a measured wall-clock value would make a second run differ from the
    first, and this table is the one a reader byte-compares against.
    """
    lines = [
        "# Headline table -- rebuilt from pinned artifacts",
        "",
        "`python benchmark/reproduce.py` rebuilds this file. No model runs in "
        "the rebuild. The table carries no timestamp and no measured wall time,",
        "so a second run is byte-identical to the first. Wall seconds are a "
        "run-time measurement: `benchmark/evaluation.py` measures and gates",
        "them (G8) when the evaluation runs; they are deliberately not pinned.",
        "",
        "## Pinned artifacts (sha256)",
        "",
        "| artifact | file | sha256 |",
        "|---|---|---|",
    ]
    for name in ARTIFACTS:
        entry = verified[name]
        lines.append(f"| {name} | {entry['path']} | {entry['sha256']} |")
    lines += [
        "",
        f"Gate split: {report['gate_split']}. Repeats: {report['repeats']} "
        f"(seeds {', '.join(str(seed) for seed in seeds)}).",
        f"Gate inputs ({len(report['gate_inputs'])}): "
        + " ".join(report["gate_inputs"]),
        "Excluded (reported, never gated): synthetic="
        + ", ".join(report["excluded"]["synthetic"]["cases"]) + "; out_of_split="
        + ", ".join(report["excluded"]["out_of_split"]["cases"]),
    ]
    for name, entry in report["detectors"].items():
        lines += ["", f"## {name} ({entry['version']})", "",
                  "Per-cell table (cells are source|technique; CP95 primary, "
                  "Wilson sensitivity):", "",
                  "| cell | n | t | c | strict recall | decided recall "
                  "| false alarm | abstention | cost | variance |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for key, row in entry["cells"].items():
            lines.append(_fmt_row(key, row))
        lines.append(_fmt_row("pooled (gate inputs only)", entry["pooled"]))
        pooled = entry["pooled"]
        lines += ["",
                  f"Twin false alarms: {_fmt_rate(pooled['twin_false_alarm'])}",
                  "Natural clean false alarms: "
                  f"{_fmt_rate(pooled['natural_clean_false_alarm'])}", "",
                  "Gates (pre-registered thresholds, decided mechanically):"]
        for gate in entry["gates"]:
            lines.append("  " + _fmt_gate(gate))
    return "\n".join(lines) + "\n"


# -- the rebuild -------------------------------------------------------------

def rebuild(root: str | Path) -> str:
    """The headline table, rebuilt from the pinned artifacts under `root`."""
    root = Path(root)
    verified = verify_pins(root)
    annotations = _annotations(root, verified)
    entries = _detector_config(root, verified)
    seeds = _seeds(root, verified)
    corpus_root = (root / verified["corpus manifest"]["path"]).parent
    records = baselines.load_case_records(corpus_root)
    _check_annotations(records, annotations)
    report = evaluation.evaluate(corpus_root, _build_detectors(entries, seeds),
                                repeats=len(seeds))
    _check_versions(report, entries)
    return render_headline(verified, seeds, report)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="reproduce.py", description=__doc__)
    parser.add_argument("--root", default=str(ROOT),
                        help="the repository root the pin records are read from")
    parser.add_argument("--out", default=None,
                        help=f"where the table is written (default: "
                             f"<root>/{DEFAULT_OUT})")
    args = parser.parse_args(argv)
    root = Path(args.root)
    out = Path(args.out) if args.out else root / DEFAULT_OUT
    try:
        table = rebuild(root)
    except EvidenceError as exc:
        print(f"reproduce: refused to rebuild: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(table.encode("utf-8"))
    print(table, end="")
    print(f"written -> {out}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
