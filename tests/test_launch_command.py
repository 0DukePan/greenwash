"""The launch command: one seam, three outcomes, seven refusals.

The command is driven exactly as a user drives it: a corpus root, the
thresholds file, the pre-registered launch configuration and its detector,
and an output directory. The tests assert the decision, the exit code, the
failing criteria and the reported numbers literally.

* LAUNCH (exit 0) writes the report and the decision record; NARROW (exit 1)
  writes both and is publishable; REFUSED (exit 2) writes neither.
* The seven refusals run before any evaluation, each on its own fixture,
  each naming its cause.
* The report and the decision record are generated, never typed, and
  byte-identical across runs, locales, time zones and line-ending settings,
  with the single `generated_at` field excluded by field name; a hand-edited
  report fails the rebuild comparison.
"""

import copy
import hashlib
import json
import socket
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import claim_ledger  # noqa: E402
import launch  # noqa: E402
import preregistration  # noqa: E402
from greenwash import baselines, corpus  # noqa: E402

THRESHOLDS = ROOT / "benchmark" / "thresholds.json"
LAUNCH_ID = "B1"
DETECTOR = {"id": LAUNCH_ID, "baseline": "held-out",
            "version": baselines.HeldoutBaseline.version}

# The corpus floor the pre-registered sample floor (L8) requires: 100 cases
# per class, each its own repository (DEFF 1.0, so effective n = n).
POSITIVES = TWINS = NATURALS = 100


# -- the fixture corpus: three classes, frozen, one repository per case ------

def case_row(case_id, label, task, repository, technique="skip-or-xfail",
             **overrides):
    row = {
        "id": case_id,
        "source": "independent: published history, table 3",
        "technique": technique,
        "label": label,
        "split": "frozen",
        "task": task,
        "repository": repository,
        "license": "MIT",
    }
    row.update(overrides)
    return row


def write_case(root, row):
    (Path(root) / f"{row['id']}.json").write_text(
        json.dumps(row, indent=2) + "\n", encoding="utf-8")


def build_corpus(root, positives=POSITIVES, twins=TWINS, naturals=NATURALS,
                 crowded=0, positive_per_repo=1):
    """positives + their legitimate twins + natural clean passes.

    `crowded` adds that many positives from one repository, to put a class
    over the per-repository case cap; `positive_per_repo` clusters the
    positives so a repository-clustered interval can be exercised.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    techniques = ("skip-or-xfail", "harness-exit")
    for i in range(positives):
        write_case(root, case_row(f"pos-{i:03d}", "tampered", f"pos-task-{i:03d}",
                                  f"repo-pos-{i // positive_per_repo:03d}",
                                  techniques[i % 2]))
        if i < twins:
            write_case(root, case_row(f"twin-{i:03d}", "clean",
                                      f"pos-task-{i:03d}",
                                      f"repo-twin-{i:03d}", techniques[i % 2]))
    for i in range(naturals):
        write_case(root, case_row(f"nat-{i:03d}", "clean", f"nat-task-{i:03d}",
                                  f"repo-nat-{i:03d}", techniques[i % 2]))
    for i in range(crowded):
        write_case(root, case_row(f"crowded-{i:03d}", "tampered",
                                  f"crowded-task-{i:03d}", "repo-crowded"))
    corpus.write_manifest(root)
    return root


# -- the scripted launch detector -------------------------------------------

class Scripted:
    """The pre-registered launch detector, scripted per case id.

    Prediction knobs force one criterion at a time; `flaky` varies only the
    result's detail bytes (L4 alone); `drift_after` flips every prediction
    after that many calls, which lands in the rebuild pass and breaks L6
    alone; `network` attempts a connection, which is refusal 6.
    """

    id = LAUNCH_ID
    version = "scripted/1"

    def __init__(self, misses=(), false_alarms=(), abstains=(), flaky=False,
                 drift_after=None, network=False, blocked_probe=False,
                 id=LAUNCH_ID):
        self.id = id
        self.misses = set(misses)
        self.false_alarms = set(false_alarms)
        self.abstains = set(abstains)
        self.flaky = flaky
        self.drift_after = drift_after
        self.network = network
        self.blocked_probe = blocked_probe
        self.calls = 0
        self.blocked = None

    def run(self, record):
        self.calls += 1
        if self.network or self.blocked_probe:
            try:
                socket.create_connection(("127.0.0.1", 9), timeout=0.1)
                self.blocked = False
                if self.network:
                    raise AssertionError("network access was not blocked")
            except launch.NetworkAccessError:
                self.blocked = True
                if self.network:
                    raise
        case_id = record.case.id
        if self.drift_after is not None and self.calls > self.drift_after:
            prediction = baselines.ABSTAIN
        elif case_id in self.abstains:
            prediction = baselines.ABSTAIN
        elif record.case.label == corpus.TAMPERED:
            prediction = (corpus.CLEAN if case_id in self.misses
                          else corpus.TAMPERED)
        else:
            prediction = (corpus.TAMPERED if case_id in self.false_alarms
                          else corpus.CLEAN)
        detail = {"drifted": self.drift_after is not None
                  and self.calls > self.drift_after}
        if self.flaky:
            detail["run"] = self.calls
        return baselines.BaselineResult(
            case=case_id, baseline=self.id, prediction=prediction,
            version=self.version, detail=detail)


# -- labels, integrity pins and the announcement draft ----------------------

def labels_payload(count=120, pabak_target=1.0):
    """A double-labeled sample: two blind votes per case plus adjudication."""
    annotations = {}
    for i in range(count):
        first = "tampered" if i % 2 == 0 else "clean"
        second = first
        if i >= int(count * (pabak_target + 1) / 2):
            second = "clean" if first == "tampered" else "tampered"
        annotations[f"case-{i:03d}"] = {
            "labelers": [first, second],
            "adjudicated": first,
        }
    return {"annotations": annotations}


def write_labels(root, payload=None, **overrides):
    payload = copy.deepcopy(payload if payload is not None
                             else labels_payload())
    payload.update(overrides)
    path = Path(root) / "labels.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def write_integrity(root, modify=None):
    """A pin record naming one checker, one config and one pinned test."""
    root = Path(root)
    files = {
        "checker": ("checker/guard.py", "# the checker's guard\n"),
        "config": ("checker/config.json", '{"mode": "report"}\n'),
        "pinned test": ("tests/test_pinned.py", "def test_pinned():\n    pass\n"),
    }
    pinned = {}
    for kind, (rel, content) in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        pinned[kind] = {"path": rel,
                        "sha256": hashlib.sha256(
                            path.read_bytes()).hexdigest()}
    if modify is not None:
        (root / files[modify][0]).write_text("# modified\n", encoding="utf-8")
    path = root / "integrity-pins.json"
    path.write_text(json.dumps({"pinned": pinned}, indent=2) + "\n",
                    encoding="utf-8")
    return path


CLEAN_DRAFT = ("This announcement summarizes the launch benchmark run.\n"
               "claims: false-alarms\n")
OVERCLAIM_DRAFT = "Greenwash catches every cheat.\n"
PARAPHRASE_DRAFT = "It catches every planted cheat.\n"


def write_draft(root, text=CLEAN_DRAFT, name="announcement.md"):
    path = Path(root) / name
    path.write_text(text, encoding="utf-8")
    return path


# -- running the command ----------------------------------------------------

def register(root, thresholds, detector=DETECTOR, launch_configuration=LAUNCH_ID):
    return preregistration.preregister(
        root, thresholds, launch_configuration, detector, tool_commit="c0ffee")


def thresholds_copy(tmp_path, crlf=False, name="thresholds.json"):
    path = Path(tmp_path) / name
    data = THRESHOLDS.read_bytes()
    if crlf:
        data = data.replace(b"\n", b"\r\n")
    path.write_bytes(data)
    return path


without_generated_at = launch.without_generated_at


def run_launch(root, thresholds, out_dir, detector_config=DETECTOR,
               detectors=None, launch_configuration=LAUNCH_ID, **kwargs):
    detectors = (Scripted(),) if detectors is None else detectors
    return launch.launch(
        root, thresholds, launch_configuration, detector_config, detectors,
        out_dir=out_dir,
        ledger_path=Path(out_dir) / "ledger.jsonl",
        retired_path=Path(out_dir) / "retired.json",
        **kwargs)


def prepared(tmp_path, corpus_builder=build_corpus, **corpus_kwargs):
    """A pre-registered corpus with its thresholds file, ready to launch."""
    root = corpus_builder(tmp_path / "corpus", **corpus_kwargs)
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    return root, thresholds


def artifacts(out_dir):
    return (Path(out_dir) / launch.REPORT_NAME,
            Path(out_dir) / launch.RECORD_NAME)


def read_record(out_dir):
    return json.loads((Path(out_dir) / launch.RECORD_NAME)
                      .read_text(encoding="utf-8"))


def crit(record, cid):
    return next(row for row in record["criteria"] if row["id"] == cid)


# ---------------------------------------------------------------------------
# T1: every criterion passing is LAUNCH (exit 0), both artifacts written.
# ---------------------------------------------------------------------------

def test_all_criteria_passing_launches_writing_both_artifacts(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    outcome = run_launch(root, thresholds, out,
                         announcement=write_draft(tmp_path),
                         labels=write_labels(tmp_path),
                         integrity=write_integrity(tmp_path))

    assert outcome.exit_code == 0
    assert outcome.decision["decision"] == "LAUNCH"
    report_path, record_path = artifacts(out)
    assert report_path.read_bytes() == outcome.report
    assert record_path.read_bytes() == outcome.record
    assert outcome.refusal is None
    assert b"Decision: LAUNCH" in outcome.report


def test_the_decision_record_lists_every_field_the_spec_names(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    outcome = run_launch(root, thresholds, out,
                         announcement=write_draft(tmp_path),
                         labels=write_labels(tmp_path),
                         integrity=write_integrity(tmp_path))

    record = read_record(out)
    assert record["decision"] == "LAUNCH"
    assert record["deciding_criterion"] is None
    assert record["failing_criteria"] == []
    assert [row["id"] for row in record["criteria"]] == [
        f"L{n}" for n in range(1, 10)]
    l1 = crit(record, "L1")
    assert l1["threshold"] == 0.9
    # the criterion's value is the gate-deciding bound: the exact lower
    # bound of 100 of 100 at the effective counts
    assert l1["value"] == pytest.approx(0.025 ** (1 / 100), abs=1e-6)
    assert l1["interval"][0] == pytest.approx(0.025 ** (1 / 100), abs=1e-6)
    assert l1["interval"][1] == pytest.approx(1.0)
    assert l1["n_eff"] == pytest.approx(100.0)
    assert l1["pass"] is True
    assert record["launch_configuration"] == LAUNCH_ID
    assert record["configuration"]["detector_sha256"] == \
        preregistration.detector_sha256(DETECTOR)
    assert record["configuration"]["detector_version"] == DETECTOR["version"]
    assert record["configuration"]["baseline_pins"]["B3"] == \
        baselines.COMPETITOR_VERSION
    assert record["hashes"]["corpus_manifest"] == corpus.manifest_sha256(root)
    assert record["hashes"]["thresholds_file"] == \
        preregistration.thresholds_sha256(thresholds)
    registered = corpus.read_preregistration(root)
    canonical = json.dumps(registered, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    assert record["preregistration_sha256"] == \
        hashlib.sha256(canonical).hexdigest()


# ---------------------------------------------------------------------------
# T2: each criterion failing alone is NARROW (exit 1), naming only it.
# ---------------------------------------------------------------------------

def fail_l1(detectors):
    detectors[0].misses = {f"pos-{i:03d}" for i in range(5)}


def fail_l2(detectors):
    detectors[0].false_alarms = {f"twin-{i:03d}" for i in range(5)}


def fail_l3(detectors):
    detectors[0].abstains = {f"twin-{i:03d}" for i in range(21)}


def fail_l4(detectors):
    detectors[0].flaky = True


def fail_l5(tmp_path, options):
    options["integrity"] = write_integrity(tmp_path, modify="checker")


def fail_l6(detectors):
    # Deterministic through the evaluation and determinism passes (2400
    # calls over the 300-case corpus), then every prediction drifts: only
    # the offline rebuild differs, so L6 alone fails.
    detectors[0].drift_after = 3000


def fail_l7(tmp_path, options):
    options["announcement"] = write_draft(tmp_path, OVERCLAIM_DRAFT)


def fail_l9(tmp_path, options):
    options["labels"] = write_labels(tmp_path, labels_payload(
        count=120, pabak_target=0.5))


@pytest.mark.parametrize("criterion, breakers", [
    ("L1", ("detectors", fail_l1)),
    ("L2", ("detectors", fail_l2)),
    ("L3", ("detectors", fail_l3)),
    ("L4", ("detectors", fail_l4)),
    ("L5", ("options", fail_l5)),
    ("L6", ("detectors", fail_l6)),
    ("L7", ("options", fail_l7)),
    ("L9", ("options", fail_l9)),
])
def test_each_criterion_failing_alone_yields_narrow_naming_only_it(
        tmp_path, criterion, breakers):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    detectors = [Scripted()]
    options = {"announcement": write_draft(tmp_path),
               "labels": write_labels(tmp_path),
               "integrity": write_integrity(tmp_path)}
    mode, breaker = breakers
    if mode == "detectors":
        breaker(detectors)
    else:
        breaker(tmp_path, options)

    outcome = run_launch(root, thresholds, out, detectors=detectors, **options)

    assert outcome.exit_code == 1
    record = read_record(out)
    assert record["decision"] == "NARROW"
    assert record["failing_criteria"] == [criterion]
    assert record["deciding_criterion"] == criterion
    assert crit(record, criterion)["pass"] is False
    assert crit(record, criterion)["reason"] != "not evaluated"


def test_a_class_over_the_per_repository_cap_fails_l8_alone(tmp_path):
    root, thresholds = prepared(tmp_path, build_corpus, crowded=6)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out,
                         announcement=write_draft(tmp_path),
                         labels=write_labels(tmp_path),
                         integrity=write_integrity(tmp_path))

    assert outcome.exit_code == 1
    record = read_record(out)
    assert record["failing_criteria"] == ["L8"]
    assert crit(record, "L8")["value"]["positives"][
        "max_cases_per_repository"] == 6


def options(tmp_path, **overrides):
    """Every artifact the checks need, overridable per fixture.

    Defaults are only filled in for keys the fixture did not override, so an
    override's file is never clobbered by a default written afterwards.
    """
    base = {}
    if "announcement" not in overrides:
        base["announcement"] = write_draft(tmp_path)
    if "labels" not in overrides:
        base["labels"] = write_labels(tmp_path)
    if "integrity" not in overrides:
        base["integrity"] = write_integrity(tmp_path)
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# T3: several failing criteria list all of them, the first in fixed order.
# ---------------------------------------------------------------------------

def test_several_failing_criteria_list_all_and_decide_the_first(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    detectors = [Scripted(misses={f"pos-{i:03d}" for i in range(5)})]

    outcome = run_launch(root, thresholds, out, detectors=detectors,
                         **options(tmp_path,
                                   announcement=write_draft(tmp_path,
                                                            OVERCLAIM_DRAFT)))

    assert outcome.exit_code == 1
    record = read_record(out)
    assert record["failing_criteria"] == ["L1", "L7"]
    assert record["deciding_criterion"] == "L1"


# ---------------------------------------------------------------------------
# T4: boundary pins, decided exactly as published.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("misses, expected, passes", [
    (4, 0.9007, True),
    (5, 0.8872, False),
])
def test_the_recall_boundary_pins_decide_at_four_and_five_misses(
        tmp_path, misses, expected, passes):
    root, thresholds = prepared(tmp_path)
    detectors = [Scripted(misses={f"pos-{i:03d}" for i in range(misses)})]

    outcome = run_launch(root, thresholds, tmp_path / "out", detectors=detectors,
                         **options(tmp_path))

    record = read_record(tmp_path / "out")
    l1 = crit(record, "L1")
    assert l1["value"] == pytest.approx(expected, abs=1e-4)
    assert l1["pass"] is passes
    assert record["decision"] == ("LAUNCH" if passes else "NARROW")
    assert outcome.exit_code == (0 if passes else 1)


@pytest.mark.parametrize("alarms, expected, passes", [
    (4, 0.0993, True),
    (5, 0.1128, False),
])
def test_the_twin_false_alarm_boundary_pins_decide_at_four_and_five(
        tmp_path, alarms, expected, passes):
    root, thresholds = prepared(tmp_path)
    detectors = [Scripted(false_alarms={f"twin-{i:03d}" for i in range(alarms)})]

    outcome = run_launch(root, thresholds, tmp_path / "out", detectors=detectors,
                         **options(tmp_path))

    record = read_record(tmp_path / "out")
    l2 = crit(record, "L2")
    assert l2["value"] == pytest.approx(expected, abs=1e-4)
    assert l2["pass"] is passes
    assert record["decision"] == ("LAUNCH" if passes else "NARROW")
    assert outcome.exit_code == (0 if passes else 1)


@pytest.mark.parametrize("n, expected, passes", [
    (36, 0.9026, True),
    (35, 0.89997, False),
])
def test_zero_errors_reach_the_bound_at_36_and_fall_short_at_35(
        tmp_path, n, expected, passes):
    root, thresholds = prepared(tmp_path, build_corpus, positives=n, twins=n,
                                naturals=n)

    outcome = run_launch(root, thresholds, tmp_path / "out",
                         **options(tmp_path))

    record = read_record(tmp_path / "out")
    l1 = crit(record, "L1")
    assert l1["value"] == pytest.approx(expected, abs=1e-4)
    assert l1["pass"] is passes
    assert outcome.exit_code in (0, 1)   # the sample floor may still fail


# ---------------------------------------------------------------------------
# T5: an input the checks need, removed in turn: `not evaluated`, never LAUNCH.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("removed", ["announcement", "labels", "integrity",
                                     "cell", "twins"])
def test_a_missing_input_is_not_evaluated_and_never_launch(tmp_path, removed):
    kwargs = options(tmp_path)
    detectors = [Scripted()]
    corpus_kwargs = {}
    if removed in kwargs:
        kwargs[removed] = None
    elif removed == "cell":
        detectors = [Scripted(id="B0")]
    elif removed == "twins":
        corpus_kwargs = {"twins": 0}
    root, thresholds = prepared(tmp_path, build_corpus, **corpus_kwargs)

    outcome = run_launch(root, thresholds, tmp_path / "out",
                         detectors=detectors, **kwargs)

    assert outcome.exit_code == 1
    record = read_record(tmp_path / "out")
    assert record["decision"] == "NARROW"
    assert outcome.decision["decision"] != "LAUNCH"
    failing = {row["id"]: row for row in record["criteria"] if not row["pass"]}
    assert any(row["reason"] == "not evaluated" for row in failing.values())


# ---------------------------------------------------------------------------
# T6: the seven refusals, each on its own fixture, each naming its cause.
# A refusal writes neither artifact and appends no ledger entry.
# ---------------------------------------------------------------------------

def snapshot(out):
    """The artifacts and ledger as they stand, for a no-write assertion."""
    out = Path(out)
    return {name: ((out / name).read_bytes() if (out / name).exists() else None)
            for name in (launch.REPORT_NAME, launch.RECORD_NAME, "ledger.jsonl")}


def assert_refused(outcome, out, *causes, before=None):
    assert outcome.exit_code == 2, outcome.refusal
    for cause in causes:
        assert cause in outcome.refusal, outcome.refusal
    after = snapshot(out)
    if before is None:
        assert after[launch.REPORT_NAME] is None
        assert after[launch.RECORD_NAME] is None
        assert not after["ledger.jsonl"]
    else:
        # a refusal writes nothing: whatever stood before the run still stands
        assert after == before
    return outcome.refusal


def frozen_json(root, names):
    """FROZEN.json recording exactly these case files, without validation."""
    root = Path(root)
    manifest = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in names}
    (root / corpus.MANIFEST).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def test_refusal_1_a_drifted_frozen_artifact_names_the_file(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    case = root / "pos-000.json"
    case.write_text(case.read_text(encoding="utf-8").replace("MIT", "Apache-2.0"),
                    encoding="utf-8")

    outcome = run_launch(root, thresholds, out, **options(tmp_path))

    assert_refused(outcome, out, "pos-000.json", "hash mismatch")


def test_refusal_2_a_drifted_thresholds_file_names_the_file(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    thresholds.write_text(
        thresholds.read_text(encoding="utf-8").replace('"value": 0.9',
                                                       '"value": 0.95'),
        encoding="utf-8")

    outcome = run_launch(root, thresholds, out, **options(tmp_path))

    assert_refused(outcome, out, "thresholds file", "hash mismatch")


def test_refusal_3_a_drifted_detector_names_the_hash(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out,
                         detector_config={**DETECTOR, "version": "held-out/99"},
                         **options(tmp_path))

    assert_refused(outcome, out, "detector hash mismatch")


def test_refusal_3_a_drifted_launch_configuration_names_the_field(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out, launch_configuration="B0",
                         **options(tmp_path))

    assert_refused(outcome, out, "launch configuration", "differs")


def test_refusal_4_a_reused_manifest_with_a_changed_detector_needs_a_fresh_split(
        tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    assert run_launch(root, thresholds, out, **options(tmp_path)).exit_code == 0
    before = snapshot(out)

    changed = run_launch(root, thresholds, out,
                         detector_config={**DETECTOR, "version": "held-out/99"},
                         **options(tmp_path))

    assert_refused(changed, out, "already evaluated with detector",
                   "fresh split is required", before=before)


def test_refusal_5_a_planted_gate_input_names_the_record_and_field(tmp_path):
    root = build_corpus(tmp_path / "corpus")
    write_case(root, case_row("planted-000", "tampered", "planted-task",
                              "repo-planted", source="planted: fixtures"))
    corpus.write_manifest(root)
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out, **options(tmp_path))

    assert_refused(outcome, out, "planted-000", "planted")


def test_refusal_5_a_synthetic_gate_input_names_the_record_and_field(tmp_path):
    root = build_corpus(tmp_path / "corpus")
    write_case(root, case_row("synth-000", "tampered", "synth-task",
                              "repo-synth", source="synthetic: injected"))
    corpus.write_manifest(root)
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out, **options(tmp_path))

    assert_refused(outcome, out, "synth-000", "synthetic")


def test_refusal_5_a_dev_record_presented_as_gate_material_names_the_split(
        tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    write_case(root, case_row("dev-000", "tampered", "dev-task", "repo-dev",
                              split="dev"))
    frozen_json(root, ["dev-000.json"])
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out, **options(tmp_path))

    assert_refused(outcome, out, "dev-000.json", "split is not frozen")


def test_refusal_5_an_incomplete_gate_input_names_the_missing_field(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    row = case_row("bare-000", "tampered", "bare-task", "repo-bare")
    row.pop("license")
    write_case(root, row)
    frozen_json(root, ["bare-000.json"])
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out, **options(tmp_path))

    assert_refused(outcome, out, "license")


def test_refusal_6_an_attempted_connection_refuses_the_run(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out,
                         detectors=[Scripted(network=True)],
                         **options(tmp_path))

    assert_refused(outcome, out, "network access")


def test_refusal_7_a_missing_baseline_pin_names_the_pin(tmp_path):
    root = build_corpus(tmp_path / "corpus")
    thresholds = thresholds_copy(tmp_path)
    record = preregistration.preregistration_record(
        root, thresholds, LAUNCH_ID, DETECTOR, tool_commit="c0ffee")
    record["baseline_pins"] = {k: v for k, v in
                               record["baseline_pins"].items() if k != "B3"}
    corpus.write_preregistration(root, record)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out, **options(tmp_path))

    assert_refused(outcome, out, "B3", "baseline pin")


# ---------------------------------------------------------------------------
# T7: two launches on one manifest reproduce identical bytes; a changed
# detector hash is refusal 4. (A new split reusing a retired repository is
# rejected by the corpus kit -- test_preregistration covers that seam.)
# ---------------------------------------------------------------------------

def test_a_rerun_reproduces_identical_bytes_and_a_changed_detector_is_refused(
        tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    first = run_launch(root, thresholds, out, **options(tmp_path))
    second = run_launch(root, thresholds, out, **options(tmp_path))

    assert first.exit_code == second.exit_code == 0
    assert second.report == first.report
    assert without_generated_at(json.loads(second.record)) == \
        without_generated_at(json.loads(first.record))

    before = snapshot(out)
    changed = run_launch(root, thresholds, out,
                         detector_config={**DETECTOR, "version": "held-out/99"},
                         **options(tmp_path))
    assert_refused(changed, out, "already evaluated with detector",
                   "fresh split is required", before=before)


# ---------------------------------------------------------------------------
# T8: a threshold changed after pre-registration is refusal 2.
# ---------------------------------------------------------------------------

def test_a_threshold_changed_after_pre_registration_is_refusal_2(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    thresholds.write_text(
        thresholds.read_text(encoding="utf-8").replace('"value": 0.1',
                                                       '"value": 0.2'),
        encoding="utf-8")

    outcome = run_launch(root, thresholds, out, **options(tmp_path))

    assert_refused(outcome, out, "thresholds file", "hash mismatch")


# ---------------------------------------------------------------------------
# T9: a descriptive cell passing cannot rescue a failing launch cell.
# ---------------------------------------------------------------------------

def test_a_non_launch_cell_passing_cannot_rescue_the_launch_cell(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    detectors = [Scripted(misses={f"pos-{i:03d}" for i in range(5)}),
                 Scripted(id="B0")]

    outcome = run_launch(root, thresholds, out, detectors=detectors,
                         **options(tmp_path))

    assert outcome.exit_code == 1
    record = read_record(out)
    assert record["decision"] == "NARROW"
    assert record["failing_criteria"] == ["L1"]
    assert record["launch_configuration"] == LAUNCH_ID


# ---------------------------------------------------------------------------
# T10: the case-level interval passes while the effective-n interval fails.
# ---------------------------------------------------------------------------

def test_a_case_level_pass_beside_an_effective_n_failure_reports_the_effective_one(
        tmp_path):
    root, thresholds = prepared(tmp_path, build_corpus, positives=140,
                                positive_per_repo=4)
    out = tmp_path / "out"
    detectors = [Scripted(misses={f"pos-{i:03d}" for i in range(4)})]

    outcome = run_launch(root, thresholds, out, detectors=detectors,
                         **options(tmp_path))

    assert outcome.exit_code == 1
    record = read_record(out)
    assert "L1" in record["failing_criteria"]
    l1 = crit(record, "L1")
    assert l1["pass"] is False
    assert "case-level CP95 lower" in l1["detail"]
    assert "passes; effective-n CP95 lower" in l1["detail"]
    assert "FAILS" in l1["detail"]


# ---------------------------------------------------------------------------
# T12: planted or synthetic records: refused in gate inputs, identical gate
# numbers when kept out.
# ---------------------------------------------------------------------------

def test_a_synthetic_record_kept_out_of_the_gate_inputs_changes_no_number(
        tmp_path):
    root, thresholds = prepared(tmp_path)
    clean = run_launch(root, thresholds, tmp_path / "clean", **options(tmp_path))

    root2 = build_corpus(tmp_path / "corpus2")
    write_case(root2, case_row("synth-000", "tampered", "synth-task",
                               "repo-synth", origin="synthetic"))
    corpus.write_manifest(root2)
    thresholds2 = thresholds_copy(tmp_path, name="thresholds2.json")
    register(root2, thresholds2)
    with_synth = run_launch(root2, thresholds2, tmp_path / "synth",
                            **options(tmp_path))

    assert clean.exit_code == with_synth.exit_code == 0
    clean_record = json.loads(clean.record)
    synth_record = json.loads(with_synth.record)
    for cid in ("L1", "L2", "L3"):
        assert crit(synth_record, cid)["value"] == \
            crit(clean_record, cid)["value"]
        assert crit(synth_record, cid)["interval"] == \
            crit(clean_record, cid)["interval"]


# ---------------------------------------------------------------------------
# T13: abstention above its ceiling on twins, then on natural clean passes.
# ---------------------------------------------------------------------------

def test_abstention_above_the_ceiling_on_natural_clean_fails_l3(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    detectors = [Scripted(abstains={f"nat-{i:03d}" for i in range(21)})]

    outcome = run_launch(root, thresholds, out, detectors=detectors,
                         **options(tmp_path))

    assert outcome.exit_code == 1
    record = read_record(out)
    assert record["failing_criteria"] == ["L3"]
    assert crit(record, "L3")["value"]["natural_clean"] == pytest.approx(0.21)


# ---------------------------------------------------------------------------
# T14: the double-labeled count and PABAK are criteria, not only a report.
# ---------------------------------------------------------------------------

def test_a_double_labeled_sample_below_the_floor_fails_l9(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out,
                         **options(tmp_path, labels=write_labels(
                             tmp_path, labels_payload(count=80))))

    assert outcome.exit_code == 1
    record = read_record(out)
    assert record["failing_criteria"] == ["L9"]
    assert crit(record, "L9")["value"]["double_labeled_cases"] == 80


def test_pabak_below_its_floor_fails_l9(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out,
                         **options(tmp_path, labels=write_labels(
                             tmp_path, labels_payload(count=120,
                                                       pabak_target=0.5))))

    assert outcome.exit_code == 1
    record = read_record(out)
    assert record["failing_criteria"] == ["L9"]
    assert crit(record, "L9")["value"]["pabak"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# T15: byte stability across runs, locales, time zones and line endings; the
# rebuild comparison fails on a hand-edited report.
# ---------------------------------------------------------------------------

def test_the_artifacts_are_byte_identical_across_runs_locales_and_line_endings(
        tmp_path, monkeypatch):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    first = run_launch(root, thresholds, out, **options(tmp_path))

    monkeypatch.setenv("TZ", "Etc/GMT+8")
    monkeypatch.setenv("LANG", "tr_TR.UTF-8")
    monkeypatch.setenv("LC_ALL", "C")
    crlf_draft = write_draft(tmp_path, CLEAN_DRAFT.replace("\n", "\r\n"),
                             name="announcement-crlf.md")
    second = run_launch(root, thresholds, out,
                        **options(tmp_path, announcement=crlf_draft))

    assert second.report == first.report
    assert without_generated_at(json.loads(second.record)) == \
        without_generated_at(json.loads(first.record))
    assert b"\r" not in first.report
    assert b"\r" not in first.record


def test_a_hand_edited_report_fails_the_rebuild_comparison(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    run_launch(root, thresholds, out, **options(tmp_path))
    report_path, _ = artifacts(out)
    report_path.write_bytes(report_path.read_bytes().replace(
        b"Decision: LAUNCH", b"Decision: NARROW"))

    code = launch.check(root, thresholds, LAUNCH_ID, DETECTOR, (Scripted(),),
                        out_dir=out, **options(tmp_path))

    assert code == 3


def test_the_rebuild_comparison_excludes_only_generated_at_by_field_name(
        tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    run_launch(root, thresholds, out, **options(tmp_path))
    _, record_path = artifacts(out)
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    payload[launch.GENERATED_AT] = "1999-01-01T00:00:00Z"
    record_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")

    code = launch.check(root, thresholds, LAUNCH_ID, DETECTOR, (Scripted(),),
                        out_dir=out, **options(tmp_path))
    assert code == 0

    payload["decision"] = "REFUSED"
    record_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    code = launch.check(root, thresholds, LAUNCH_ID, DETECTOR, (Scripted(),),
                        out_dir=out, **options(tmp_path))
    assert code == 3


# ---------------------------------------------------------------------------
# T16: a planted over-claim and a registered paraphrase both fail L7.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("draft", [OVERCLAIM_DRAFT, PARAPHRASE_DRAFT])
def test_an_over_claim_in_the_announcement_draft_fails_l7(tmp_path, draft):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out,
                         **options(tmp_path,
                                   announcement=write_draft(tmp_path, draft)))

    assert outcome.exit_code == 1
    record = read_record(out)
    assert record["failing_criteria"] == ["L7"]
    assert crit(record, "L7")["value"]["claims_outside_ledger"] >= 1


# One registered paraphrase per ledger row: the phrasing that row's triggers
# register, planted as a claim beyond the row's allowed wording. The keys are
# checked against the ledger below, so a new row cannot ship without one.
REGISTERED_PARAPHRASES = {
    "detector-recall": "The scanner has 100% recall.",
    "false-alarms": "It has 0% false positives.",
    "behavioural-effect": "greenwash reduces reward hacking.",
    "fp-survey": "The false-positive rate is 5.",
    "first-party-corpus": "This is an independent corpus.",
    "rate-claims": "Detection accuracy is 99.",
    "strength-advisory": "greenwash detects weak tests.",
    "verdict-vocabulary": "This proves the code is correct.",
    "scope-exclusions": "It covers retrieval.",
}


def test_the_registered_paraphrases_cover_every_ledger_row():
    assert set(REGISTERED_PARAPHRASES) == \
        {row.claim for row in claim_ledger.rows()}


@pytest.mark.parametrize("claim", sorted(REGISTERED_PARAPHRASES))
def test_a_registered_paraphrase_beyond_the_allowed_wording_fails_l7(
        tmp_path, claim):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"

    outcome = run_launch(
        root, thresholds, out,
        **options(tmp_path, announcement=write_draft(
            tmp_path, REGISTERED_PARAPHRASES[claim])))

    assert outcome.exit_code == 1
    record = read_record(out)
    assert record["failing_criteria"] == ["L7"]
    assert crit(record, "L7")["value"]["claims_outside_ledger"] >= 1


# ---------------------------------------------------------------------------
# Claim coverage: the announcement-wording section and the narrowed-scope
# statement render from ledger data, not from prose.
# ---------------------------------------------------------------------------

def report_section(report, heading):
    return report.split(heading, 1)[1].split("\n## ", 1)[0]


def test_the_announcement_wording_section_renders_from_the_ledger(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out, **options(tmp_path))
    report = outcome.report.decode("utf-8")
    section = report_section(report, "## Claim wording")

    assert "| claim | status | strongest wording allowed today " \
           "| may not say |" in section
    for row in claim_ledger.rows():
        assert f"| {row.claim} | {row.status} | {row.allowed} |" in section
        assert f"{'; '.join(row.forbidden) or '--'} |" in section


def test_the_narrowed_scope_statement_renders_the_ledger_wording_and_names_its_failures(
        tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    detectors = [Scripted(misses={f"pos-{i:03d}" for i in range(5)})]

    outcome = run_launch(
        root, thresholds, out, detectors=detectors,
        **options(tmp_path, announcement=write_draft(tmp_path, OVERCLAIM_DRAFT)))

    # publishable, not an error: NARROW writes both artifacts and exits 1
    assert outcome.exit_code == 1
    report = outcome.report.decode("utf-8")
    assert b"Decision: NARROW" in outcome.report
    assert "Failing criteria: L1, L7" in report
    section = report_section(report, "## Narrowed scope")
    for label in ("positives", "twins", "natural_clean"):
        line = next(line for line in section.splitlines()
                    if line.startswith(f"- coverage {label}:"))
        assert "n_eff" in line
    record = read_record(out)
    for cid, label in (("L2", "measured twin false-alarm rate"),
                       ("L3", "measured abstention rate")):
        row = crit(record, cid)
        line = next(line for line in section.splitlines() if label in line)
        for field in ("value", "interval", "n_eff"):
            expected = (f"{row[field]:.6f}" if isinstance(row[field], float)
                        else json.dumps(row[field], sort_keys=True,
                                        default=str))
            assert expected in line, (
                f"{cid} {field} {expected} is not in the narrowed-scope "
                f"statement: {line!r}")
    for row in claim_ledger.rows():
        assert f"{row.claim}: {row.allowed}" in section, (
            f"the narrowed-scope statement does not carry the ledger's "
            f"allowed wording for {row.claim}")


# ---------------------------------------------------------------------------
# T20: the README launch status line, generated from the decision record:
# UNMEASURED with no record, NARROWED naming the failing criteria, and
# LAUNCH-READY otherwise. CI fails when the committed line differs.
# ---------------------------------------------------------------------------

def test_the_status_line_is_unmeasured_without_a_decision_record():
    assert launch.status_line(None) == "Launch status: UNMEASURED"


def test_the_status_line_is_narrowed_naming_the_failing_criteria(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    detectors = [Scripted(misses={f"pos-{i:03d}" for i in range(5)})]

    outcome = run_launch(
        root, thresholds, out, detectors=detectors,
        **options(tmp_path, announcement=write_draft(tmp_path, OVERCLAIM_DRAFT)))

    assert outcome.decision["decision"] == "NARROW"
    assert launch.status_line(read_record(out)) == \
        "Launch status: NARROWED (failing criteria: L1, L7)"


def test_the_status_line_is_launch_ready_after_a_launch_fixture(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"

    outcome = run_launch(root, thresholds, out, **options(tmp_path))

    assert outcome.decision["decision"] == "LAUNCH"
    assert launch.status_line(read_record(out)) == "Launch status: LAUNCH-READY"


def test_a_hand_edited_status_line_is_a_mismatch_the_check_reports():
    record = {"decision": "NARROW", "failing_criteria": ["L1", "L7"]}
    line = launch.status_line(record)

    assert launch.readme_status_problems(f"intro\n{line}\n", record) == []
    edited = launch.readme_status_problems(
        "intro\nLaunch status: LAUNCH-READY\n", record)
    assert edited and "LAUNCH-READY" in edited[0]
    missing = launch.readme_status_problems("intro\n", record)
    assert missing and "UNMEASURED" not in missing[0]
    assert "Launch status: NARROWED" in missing[0]


# ---------------------------------------------------------------------------
# T17: the run completes with network access blocked; any connection attempt
# fails the run (refusal 6 above).
# ---------------------------------------------------------------------------

def test_the_run_completes_with_network_access_blocked(tmp_path):
    root, thresholds = prepared(tmp_path)
    out = tmp_path / "out"
    detector = Scripted(blocked_probe=True)

    outcome = run_launch(root, thresholds, out, detectors=[detector],
                         **options(tmp_path))

    assert outcome.exit_code == 0
    assert detector.blocked is True


# ---------------------------------------------------------------------------
# The CLI seam: the same three outcomes by exit code, usage errors elsewhere.
# ---------------------------------------------------------------------------

def test_the_cli_reports_a_refusal_with_exit_2_and_writes_nothing(tmp_path):
    root = build_corpus(tmp_path / "corpus")
    write_case(root, case_row("planted-000", "tampered", "planted-task",
                              "repo-planted", source="planted: fixtures"))
    corpus.write_manifest(root)
    thresholds = thresholds_copy(tmp_path)
    register(root, thresholds)
    out = tmp_path / "out"

    code = launch.main(["--corpus", str(root), "--thresholds", str(thresholds),
                        "--out", str(out)])

    assert code == 2
    assert not (out / launch.REPORT_NAME).exists()
    assert not (out / launch.RECORD_NAME).exists()


def test_a_usage_error_exits_outside_the_decision_range():
    with pytest.raises(SystemExit) as excinfo:
        launch.main(["--nope"])
    assert excinfo.value.code == 64
