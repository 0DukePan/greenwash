"""The usability kit: eight representative checker outputs and a small scorer.

Stage 5's usability gate (docs/specs/validation-program.md) measures whether a
developer reads the checker's message correctly and quickly. This module is
the tooling for that scripted session: the kit data
(`benchmark/usability-kit.json`) and the scorer over recorded response rows.
It is data plus arithmetic: no network, no telemetry, no user data. The only
respondent labels in this repository are the fixture rows the tests invent,
and those say so.

The kit's message content matches what the tool actually prints:
`tests/test_usability.py` renders each sample through
`greenwash.report.terminal.render` and asserts that the verdict line, the
reason and the evidence survive there unchanged.

Contracts, each one load-bearing:

* Every output shows the verdict first, one sentence of reason, the evidence,
  and the next step. A sample missing a part is a rejection naming the field,
  never a default.
* The answer key decides each interpretation as correct or not without
  ambiguity: the reader picks one of three actions and exactly one is right.
* The scorer computes the share correct and the median seconds per output from
  response rows (the answer chosen plus the seconds it took) and refuses any
  row it cannot read, naming `response.<field>`.
* The 80 percent target is checked on the round after the one recorded
  wording-fix round, and never before it.

Usage:

    from benchmark.usability import check_target, load_kit, message, score
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash.report.terminal import VERDICT_BLURB  # noqa: E402

DEFAULT_KIT = HERE / "usability-kit.json"

TARGET_SHARE = 0.80

#: The three interpretations a reader may choose; the answer key names
#: exactly one of them per output.
INTERPRETATIONS = ("restore-tests", "supply-evidence", "proceed")

SPLIT = {"TAMPERED": 4, "INCONCLUSIVE": 2, "CLEAN": 2}


class KitError(ValueError):
    """A kit field or a response row cannot be read.

    Rejected by name, never defaulted: a usability number built on a row
    nobody could read is worse than no number.
    """


def load_kit(path=DEFAULT_KIT) -> dict:
    """The kit, validated: samples, answer key and the wording-round record."""
    kit = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_kit(kit)
    return kit


def validate_kit(kit: dict) -> None:
    """Fail closed on anything the session or the scorer would need."""
    samples = kit.get("samples")
    if not isinstance(samples, list) or not samples:
        raise KitError("kit.samples")
    seen: set = set()
    split: dict = {}
    for sample in samples:
        sid = sample.get("id") or "?"
        for field in ("id", "verdict", "reason", "evidence", "next_step"):
            if not sample.get(field):
                raise KitError(f"sample {sid}: {field}")
        verdict = sample["verdict"]
        if verdict not in SPLIT:
            raise KitError(f"sample {sid}: verdict {verdict!r} is not one of {sorted(SPLIT)}")
        evidence = sample["evidence"]
        if not isinstance(evidence, list) or not all(
                isinstance(line, str) and line.strip() for line in evidence):
            raise KitError(f"sample {sid}: evidence")
        if sid in seen:
            raise KitError(f"sample {sid}: duplicated")
        seen.add(sid)
        split[verdict] = split.get(verdict, 0) + 1
    if split != SPLIT:
        raise KitError(f"kit.samples: split {split} is not the four-two-two split")
    key = kit.get("answer_key")
    if not isinstance(key, dict) or set(key) != seen:
        raise KitError("kit.answer_key: must cover every sample exactly")
    for sid, entry in key.items():
        if entry.get("interpretation") not in INTERPRETATIONS:
            raise KitError(f"answer_key {sid}: interpretation")
        for field in ("what_happened", "reader_action"):
            if not entry.get(field):
                raise KitError(f"answer_key {sid}: {field}")
    wording = kit.get("wording_round")
    if not isinstance(wording, dict) or not wording.get("changes"):
        raise KitError("kit.wording_round")
    for change in wording["changes"]:
        for field in ("sample", "was", "now"):
            if not change.get(field):
                raise KitError(f"wording_round change: {field}")


def message(sample: dict) -> str:
    """The four-part message: verdict first, reason, evidence, next step.

    The verdict line is the tool's own line (`greenwash.report.terminal`
    prints `Verdict: X -- blurb` verbatim); the evidence lines carry the
    renderer's own prefixes. The message moves the verdict to the top and adds
    the next step -- what a reader should do -- and invents no other wording.
    """
    verdict = sample["verdict"]
    lines = [f"Verdict: {verdict} -- {VERDICT_BLURB[verdict]}",
             f"Reason: {sample['reason']}",
             "Evidence:"]
    lines.extend("  " + line for line in sample["evidence"])
    if sample.get("note"):
        lines.append(f"note: {sample['note']}")
    lines.append(f"Next step: {sample['next_step']}")
    return "\n".join(lines)


def score(responses, kit=None) -> dict:
    """The scoring sheet: share correct and median seconds per output.

    Each response row carries the answer chosen and the seconds it took:
    `{"respondent": ..., "sample": ..., "answer": ..., "seconds": ...,
    "round": ...}`. A row that cannot be read -- a field missing, a sample the
    kit does not carry, seconds that are not positive, a round that does not
    exist -- is rejected naming `response.<field>`. Nothing is defaulted.
    """
    kit = kit if kit is not None else load_kit()
    validate_kit(kit)
    key = kit["answer_key"]
    ids = {sample["id"] for sample in kit["samples"]}
    seen: set = set()
    correct = 0
    seconds: list = []
    by_sample: dict = {}
    for row in responses or []:
        if not isinstance(row, dict):
            raise KitError("response: not a row")
        for field in ("respondent", "sample", "answer", "seconds", "round"):
            if field not in row:
                raise KitError(f"response.{field}")
        if not str(row["respondent"]).strip():
            raise KitError("response.respondent")
        sid = row["sample"]
        if sid not in ids:
            raise KitError(f"response.sample: {sid!r} is not in the kit")
        if row["answer"] not in INTERPRETATIONS:
            raise KitError(f"response.answer: {row['answer']!r} is not one of "
                           f"{sorted(INTERPRETATIONS)}")
        spent = row["seconds"]
        if isinstance(spent, bool) or not isinstance(spent, (int, float)) or spent <= 0:
            raise KitError("response.seconds")
        if row["round"] not in (1, 2):
            raise KitError("response.round")
        dupe = (row["respondent"], sid, row["round"])
        if dupe in seen:
            raise KitError(f"response: {dupe[0]} answered {sid} twice in "
                           f"round {row['round']}")
        seen.add(dupe)
        hit = row["answer"] == key[sid]["interpretation"]
        correct += int(hit)
        seconds.append(float(spent))
        cell = by_sample.setdefault(sid, {"n": 0, "correct": 0})
        cell["n"] += 1
        cell["correct"] += int(hit)
    if not seconds:
        raise KitError("responses: empty")
    return {
        "responses": len(seconds),
        "correct": correct,
        "share_correct": correct / len(seconds),
        "median_seconds": float(statistics.median(seconds)),
        "by_sample": by_sample,
    }


def check_target(responses, kit=None) -> dict:
    """The 80 percent target, checked on the round after the wording fix.

    The kit must record its wording round (one round; the record is data), and
    every row must come from the round after it. Before the fix there is
    nothing to check: `score` still reports the numbers, but the target is not
    consulted until the wording a reader saw has had its one revision.
    """
    result = score(responses, kit)
    rows = responses or []
    if any(row["round"] != 2 for row in rows):
        raise KitError("response.round: the target is checked on the round "
                       "after the wording fix")
    result["target"] = TARGET_SHARE
    result["met"] = result["share_correct"] >= TARGET_SHARE
    return result
