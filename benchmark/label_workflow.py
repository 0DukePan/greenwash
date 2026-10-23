"""The label workflow: calibration, blind packets, two label files, one
adjudication per case, and the L9 result.

Stage 1's labeling loop as tooling (docs/specs/validation-program.md,
Labeling). The corpus records arrive from the corpus kit
(`greenwash.corpus`, case record v2); this module turns them into the human
workflow around those records: a calibration round that measures labeling
time per case and produces the guide stub, blind packets for two independent
labelers, the ingestion of their two label files, the disagreement list an
adjudicator works from, one adjudication per case recorded once, and the
raw agreement, kappa and PABAK result shaped for the launch criteria engine.

The contracts, each one load-bearing:

* **A blind packet reveals nothing.** A packet shows only what the labeler
  needs as evidence -- the refs, the diff hash and path, the case files and
  the replay record (grade relevance is judged on replay evidence, never on
  inference) -- and nothing else. In particular it hides the gold fields
  (id, label, technique, origin, split), the `labels` and `axes` blocks (a
  field that reveals another labeler's answer), the `route` (where it would
  bias a label: R3 is labeled by construction), the twin pairing, and any
  detector output a record happens to carry. Everything hidden travels to
  the orchestrator's key instead.
* **Both label files cover every packet.** Two fixture label files name two
  labelers and label every packet exactly once with a `tampered` or `clean`
  vote and a written reason. An unknown packet, a duplicate, a missing one
  or a vote nobody can read is a refusal naming the field, never a default.
* **Disagreements carry both sides.** A disagreement is listed with both
  labelers' labels and both reasons, so an adjudicator sees the whole
  argument before deciding.
* **An adjudication is recorded once.** `record_adjudication` writes one
  decision per case and refuses a second one naming the case; there is no
  overwrite path.
* **An unadjudicated case blocks L9, never defaults.** `l9_result` refuses
  to emit the L9 numbers while any case in the round lacks an adjudicated
  label, naming each such case id. The adjudicated label is never invented
  from a labeler's vote or the record's own gold label.
* **Calibration measures, it does not assume.** The calibration round is
  exactly twenty cases with recorded seconds per case; the measured time
  replaces the fifteen-minute assumption and lands in the guide stub.

Fixture label files only in this repository: every labeler name under
`tests/fixtures/labels/` starts with `fixture-`. The real labeling program is
human work under the operator's control and lives outside this repository.

The runner's seam, all callable without a CLI:

    packets, key = blind_packets(records)            # what the labelers see
    session = ingest_labels(key, first, second)      # two label files in
    record_adjudication(path, case_id, label, reason)  # once per case
    result = l9_result(session, read_adjudications(path))
    round = calibration_round(path)                  # time per case + guide

This module rides on the corpus kit rather than restating it: label votes
are `greenwash.corpus.LABELS`, record validation is `validate_case`, and the
L9 numbers are shaped exactly as `benchmark.launch.labels_result` and the
criteria engine's L9 cell expect them.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from greenwash.corpus import EXTENDED, FIELDS, LABELS, validate_case

#: The calibration round is twenty cases (docs/specs/validation-program.md,
#: Labeling): small enough to be cheap, large enough to measure with.
CALIBRATION_CASES = 20

#: What a blind packet may show: the evidence a labeler judges, and nothing
#: else. Anything not named here -- gold fields, labels, axes, route, twin
#: pairing, detector output -- travels to the key instead.
PACKET_FIELDS = ("base_ref", "head_ref", "diff_hash", "diff_path",
                 "files", "replay")

#: What the launch criteria engine's L9 cell and `labels_result` read.
L9_RESULT_FIELDS = ("double_labeled_cases", "pabak", "kappa", "raw_agreement")


class LabelError(ValueError):
    """A label file, an adjudication or a round cannot be read.

    Rejected by name, never defaulted: an agreement number built on a label
    nobody wrote is worse than no number.
    """


def _record_items(record) -> list:
    """One record as (field, value) pairs, whether a mapping or a Case."""
    if isinstance(record, Mapping):
        return list(record.items())
    return [(field, getattr(record, field, None)) for field in FIELDS + EXTENDED]


# -- blind packets: what the labelers see, and the key they never see --------

def blind_packets(records: Iterable) -> tuple:
    """Blind annotation packets, and the key that stays with the orchestrator.

    A packet carries `packet` (a stable id, P1 upward in record order) plus
    exactly `PACKET_FIELDS` -- the refs, the diff identity and path, the case
    files and the replay record the labeler judges as evidence. Everything
    else is hidden by whitelist, so no detector output, no gold field, no
    `labels` or `axes` block (another labeler's answer) and no `route` (which
    would bias a label) can leak into a packet however a record spells it.

    The key maps each packet id to the hidden fields of its record, so the
    orchestrator can score the round afterwards and nothing else. Generation
    is deterministic: the same records produce the same packets.
    """
    packets: list = []
    key: dict = {}
    for number, record in enumerate(records, start=1):
        fields = dict(_record_items(record))
        issues = validate_case(fields)
        if issues:
            raise LabelError("; ".join(issues))
        packet_id = f"P{number}"
        packet = {"packet": packet_id}
        for field in PACKET_FIELDS:
            if fields.get(field) is not None:
                packet[field] = fields[field]
        packets.append(packet)
        key[packet_id] = {field: value for field, value in fields.items()
                          if field not in PACKET_FIELDS}
    return packets, key


# -- ingesting the two label files -------------------------------------------

def load_label_file(path) -> dict:
    """One label file, validated: a labeler, and one vote per entry.

    A vote is `packet`, `label` (one of `greenwash.corpus.LABELS`) and a
    written `reason`; anything else is refused naming the field.
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LabelError(f"label file {path}: could not be read: {exc}") from exc
    labeler = payload.get("labeler") if isinstance(payload, Mapping) else None
    if not str(labeler or "").strip():
        raise LabelError("labeler: missing; a label file names its labeler")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise LabelError("entries: missing; a label file carries its votes")
    seen: set = set()
    votes: dict = {}
    for index, entry in enumerate(entries):
        where = f"entries[{index}]"
        if not isinstance(entry, Mapping):
            raise LabelError(f"{where}: must be a vote of packet, label, reason")
        packet = str(entry.get("packet") or "").strip()
        if not packet:
            raise LabelError(f"{where}: packet: missing; a vote names its packet")
        if packet in seen:
            raise LabelError(f"{where}: packet: {packet} is voted twice; a "
                             "labeler labels each packet once")
        seen.add(packet)
        label = entry.get("label")
        if label not in LABELS:
            raise LabelError(f"{where}: label: {label!r} is not one of "
                             f"{', '.join(LABELS)}")
        reason = entry.get("reason")
        if not str(reason or "").strip():
            raise LabelError(f"{where}: reason: missing; a vote carries the "
                             "labeler's reason")
        votes[packet] = {"label": label, "reason": reason}
    return {"labeler": labeler, "votes": votes}


def _agreement(votes: list) -> tuple:
    """Raw agreement, kappa and PABAK over paired votes.

    Cohen's kappa over the two labelers' marginals, PABAK as 2 * po - 1 --
    the same arithmetic `benchmark.launch.labels_result` performs, so the
    workflow's numbers and the launch input's numbers cannot drift apart.
    """
    n = len(votes)
    po = sum(1 for first, second in votes if first == second) / n
    labels = sorted({vote for pair in votes for vote in pair})
    pe = sum((sum(1 for first, _ in votes if first == label) / n)
             * (sum(1 for _, second in votes if second == label) / n)
             for label in labels)
    kappa = 1.0 if pe == 1.0 else (po - pe) / (1.0 - pe)
    return po, kappa, 2 * po - 1


def ingest_labels(key: Mapping, first, second) -> dict:
    """Two label files in: the double-labeled round, scored.

    Both files must cover every packet exactly once -- an unknown packet, a
    duplicate or a missing one is a refusal naming the packet -- and each
    entry carries its label and its written reason. Out comes the round:
    `double_labeled_cases`, `raw_agreement`, `kappa` and `pabak` over the
    paired votes, `annotations` in the shape the launch criteria engine
    reads, and `cases` with both labelers' votes per packet.
    """
    files = [load_label_file(first), load_label_file(second)]
    packets = sorted(key)
    for label_file in files:
        for unknown in sorted(set(label_file["votes"]) - set(packets)):
            raise LabelError(f"{unknown}: unknown packet; a label file votes "
                             "on the round's packets")
    cases: list = []
    votes: list = []
    annotations: dict = {}
    for packet_id in packets:
        pair = []
        for label_file in files:
            if packet_id not in label_file["votes"]:
                raise LabelError(f"{packet_id}: not labeled by "
                                 f"{label_file['labeler']}; both labelers "
                                 "label every packet")
            pair.append(label_file["votes"][packet_id])
        votes.append((pair[0]["label"], pair[1]["label"]))
        case_id = key[packet_id].get("id", packet_id)
        cases.append({"packet": packet_id, "case": case_id,
                      "labeler1": dict(pair[0]), "labeler2": dict(pair[1]),
                      "disagreement": pair[0]["label"] != pair[1]["label"]})
        annotations[case_id] = {"labelers": [pair[0]["label"], pair[1]["label"]]}
    po, kappa, pabak = _agreement(votes)
    disagreements = [dict(case) for case in cases if case["disagreement"]]
    return {"double_labeled_cases": len(cases), "raw_agreement": po,
            "kappa": kappa, "pabak": pabak, "cases": cases,
            "disagreements": disagreements, "annotations": annotations}


# -- the adjudication, recorded once per case --------------------------------

def record_adjudication(path, case_id: str, label: str, reason: str) -> dict:
    """One adjudicated decision for one case -- exactly once.

    The decision is appended to the adjudications file under the case id; a
    case that is already adjudicated is refused naming the case, with no
    overwrite path, so the third judgment cannot be quietly replaced after
    the fact. The adjudicated label is one of `greenwash.corpus.LABELS` and
    the adjudicator writes a reason.
    """
    if not str(case_id or "").strip():
        raise LabelError("case: missing; an adjudication names its case")
    if label not in LABELS:
        raise LabelError(f"label: {label!r} is not one of {', '.join(LABELS)}")
    if not str(reason or "").strip():
        raise LabelError("reason: missing; an adjudication carries the "
                         "adjudicator's reason")
    adjudications = read_adjudications(path)
    if case_id in adjudications:
        raise LabelError(f"{case_id}: already adjudicated; a case is "
                         "adjudicated once and the record is never rewritten")
    adjudications[case_id] = {"label": label, "reason": reason}
    Path(path).write_text(json.dumps(adjudications, indent=2) + "\n",
                          encoding="utf-8")
    return dict(adjudications[case_id])


def read_adjudications(path) -> dict:
    """The adjudications file as written, {} before the first decision."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LabelError(f"adjudications {path}: could not be read: {exc}"
                         ) from exc
    if not isinstance(payload, Mapping):
        raise LabelError("adjudications: must be a mapping of case id to "
                         "decision")
    for case_id, entry in payload.items():
        if not isinstance(entry, Mapping) or entry.get("label") not in LABELS:
            raise LabelError(f"adjudications: {case_id}: label: "
                             f"{entry.get('label')!r} is not one of "
                             f"{', '.join(LABELS)}")
        if not str(entry.get("reason") or "").strip():
            raise LabelError(f"adjudications: {case_id}: reason: missing")
    return dict(payload)


# -- the L9 result, blocked by any unadjudicated case ------------------------

def l9_result(session: Mapping, adjudications: Mapping) -> dict:
    """The L9 numbers, only for a round whose every case is adjudicated.

    Raw agreement, kappa and PABAK are the two labelers' own votes, so they
    are computable before any adjudication -- but the L9 output is the label
    program's claim about a corpus whose labels are final, so a case without
    an adjudicated label blocks it with its id named and never a default:
    the adjudicated label is never invented from a labeler's vote or the
    record's own gold label.

    The result is shaped exactly as `benchmark.launch.labels_result` and the
    launch criteria engine's L9 cell read it: `double_labeled_cases`, `pabak`,
    `kappa` and `raw_agreement`.
    """
    missing = sorted({str(case.get("case") or case.get("packet") or "?")
                      for case in session.get("cases", ())
                      if case.get("case") not in adjudications})
    if missing:
        raise LabelError(
            f"{', '.join(missing)}: adjudication missing; a case without "
            "adjudication blocks the L9 output and is never defaulted to a "
            "labeler's vote or the record's own gold label")
    return {"double_labeled_cases": session["double_labeled_cases"],
            "pabak": session["pabak"], "kappa": session["kappa"],
            "raw_agreement": session["raw_agreement"]}


# -- the calibration round: measurement, then the guide stub -----------------

def guide_stub(seconds_per_case: float) -> dict:
    """The label guide's stub, on the calibration round's measurement.

    The stub fixes what the full round may assume: the four axes and how each
    is judged, and that the reference verdict is derived mechanically from
    axes A to C rather than from a labeler's feeling. `time_per_case_seconds`
    is the measured number, so the fifteen-minute assumption is replaced by a
    measurement instead of repeated.
    """
    return {
        "title": "label guide",
        "status": "stub; frozen once the operator reviews the calibration round",
        "axes": {
            "a_mechanism": "how the suite was weakened, read off the diff",
            "b_grade_relevance": "whether the change alters what the suite "
                                 "grades, judged on the replay record and "
                                 "never inferred",
            "c_pinned_evidence": "evidence from before the run, and never "
                                 "from a file the diff changed",
            "d_harm": "an independent oracle: reference or upstream first, "
                      "a pinned spec second, a later fix as supporting "
                      "evidence only",
        },
        "reference_verdict": "derived mechanically from axes a, b and c; a "
                             "labeler's gut-feel verdict is recorded "
                             "separately and compared, never used",
        "time_per_case_seconds": seconds_per_case,
    }


def calibration_round(path) -> dict:
    """The twenty-case calibration round: measured time per case + guide stub.

    The calibration label file carries exactly `CALIBRATION_CASES` readings,
    one per case, each with the seconds it took. The measurement is the
    deliverable: `seconds_per_case` replaces the fifteen-minute assumption,
    and it lands inside the guide stub the full round is labeled under. A
    round that is not twenty cases, or a reading without a case or a usable
    `seconds` value, is refused naming the field -- never averaged over.
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LabelError(f"calibration file {path}: could not be read: {exc}"
                         ) from exc
    if not str((payload.get("labeler") if isinstance(payload, Mapping) else None)
               or "").strip():
        raise LabelError("labeler: missing; a calibration file names its labeler")
    readings = payload.get("readings")
    if not isinstance(readings, list):
        raise LabelError("readings: missing; a calibration file carries its "
                         "time readings")
    if len(readings) != CALIBRATION_CASES:
        raise LabelError(f"readings: {len(readings)} cases; a calibration "
                         f"round is exactly {CALIBRATION_CASES} cases")
    seen: set = set()
    total = 0.0
    for index, reading in enumerate(readings):
        where = f"readings[{index}]"
        if not isinstance(reading, Mapping):
            raise LabelError(f"{where}: must be a reading of case, seconds")
        case_id = str(reading.get("case") or "").strip()
        if not case_id:
            raise LabelError(f"{where}: case: missing; a reading names its case")
        if case_id in seen:
            raise LabelError(f"{where}: case: {case_id} is read twice; a "
                             "calibration round measures each case once")
        seen.add(case_id)
        seconds = reading.get("seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) \
                or seconds <= 0:
            raise LabelError(f"{where}: seconds: {seconds!r} is not the "
                             "measured time for the case; calibration "
                             "measures time per case")
        total += seconds
    seconds_per_case = total / CALIBRATION_CASES
    return {"cases": CALIBRATION_CASES, "total_seconds": total,
            "seconds_per_case": seconds_per_case,
            "guide": guide_stub(seconds_per_case)}
