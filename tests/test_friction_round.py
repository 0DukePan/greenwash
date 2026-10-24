"""The reviewed-alerts judgment file and the trial's friction round.

Two public seams. `friction_round.load_judgments(path, pr_ids)` reads the
reviewed-alerts file: one entry per reviewed alert, mapping a PR id to
`legitimate` or `illegitimate` with a reviewer and a date. The term is about
the change: a legitimate change means the alert was a false alarm and the
interruption unnecessary; an illegitimate change made the alert necessary; an
unreviewed alert is absent from the file and never counted as unnecessary.

`friction_round.run_round(pr_log, judgments, consent)` merges the collector's
PR log with the judgments and runs the existing friction harness
(benchmark/shadow_friction.py) unchanged over the merge, writing the five
measures with their explicit denominators plus the judgment coverage
(reviewed vs unreviewed alerts).

Refusals are named, never defaults: an unknown judgment value, a judgment
naming a PR absent from the log, an incomplete entry, a duplicate judgment,
and a malformed date all refuse before anything is written. The fixture log
is the collector's output shape: five merged pull requests, three alerts
(flagged), of which one is judged legitimate, one illegitimate and one stays
unreviewed.
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import friction_round  # noqa: E402
import shadow_friction  # noqa: E402

FIXTURES = HERE / "fixtures" / "friction_round"
PR_LOG = FIXTURES / "pr-log.json"
JUDGMENTS = FIXTURES / "judgments.json"
CONSENT = FIXTURES / "consent.json"

PR_IDS = ["alpha#1", "alpha#2", "alpha#3", "alpha#4", "alpha#5"]


def judgment(pr, value="legitimate", reviewer="dana", date="2024-03-05"):
    return {"pr": pr, "judgment": value, "reviewer": reviewer, "date": date}


def write_judgments(tmp_path, entries):
    path = tmp_path / "judgments.json"
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return path


# -- the judgment file: PR id to a term, with reviewer and date -------------


def test_the_judgment_file_maps_pr_ids_to_terms_with_reviewer_and_date():
    loaded = friction_round.load_judgments(JUDGMENTS, PR_IDS)

    assert loaded == {
        "alpha#1": {"judgment": "legitimate", "reviewer": "dana",
                    "date": "2024-03-05"},
        "alpha#2": {"judgment": "illegitimate", "reviewer": "kai",
                    "date": "2024-03-06"},
    }


def test_an_unreviewed_alert_is_absent_from_the_judgment_file():
    loaded = friction_round.load_judgments(JUDGMENTS, PR_IDS)

    assert "alpha#3" not in loaded


# -- refusals, each named ---------------------------------------------------


@pytest.mark.parametrize("field", ["pr", "judgment", "reviewer", "date"])
def test_an_incomplete_judgment_entry_is_refused_by_name(tmp_path, field):
    entry = judgment("alpha#1")
    del entry[field]
    path = write_judgments(tmp_path, [entry])

    with pytest.raises(friction_round.Refusal) as excinfo:
        friction_round.load_judgments(path, PR_IDS)
    message = str(excinfo.value)
    assert repr(field) in message
    assert "alpha#1" in message or field == "pr"


def test_a_judgment_value_outside_the_two_is_refused_by_name(tmp_path):
    path = write_judgments(tmp_path, [judgment("alpha#1", value="maybe")])

    with pytest.raises(friction_round.Refusal) as excinfo:
        friction_round.load_judgments(path, PR_IDS)
    message = str(excinfo.value)
    assert "alpha#1" in message
    assert "'maybe'" in message
    assert "legitimate" in message


def test_a_judgment_naming_a_pr_absent_from_the_log_is_refused_by_name(tmp_path):
    path = write_judgments(tmp_path, [judgment("alpha#99")])

    with pytest.raises(friction_round.Refusal) as excinfo:
        friction_round.load_judgments(path, PR_IDS)
    message = str(excinfo.value)
    assert "alpha#99" in message
    assert "absent from the log" in message


def test_a_duplicate_judgment_is_refused_by_name(tmp_path):
    path = write_judgments(tmp_path, [judgment("alpha#1"),
                                      judgment("alpha#1", value="illegitimate")])

    with pytest.raises(friction_round.Refusal) as excinfo:
        friction_round.load_judgments(path, PR_IDS)
    message = str(excinfo.value)
    assert "alpha#1" in message
    assert "duplicate" in message


@pytest.mark.parametrize(("field", "value"), [("reviewer", ""),
                                              ("reviewer", 5),
                                              ("date", "last Tuesday")])
def test_a_judgment_entry_with_an_empty_or_malformed_field_is_refused_by_name(
        tmp_path, field, value):
    path = write_judgments(tmp_path, [judgment("alpha#1", **{field: value})])

    with pytest.raises(friction_round.Refusal) as excinfo:
        friction_round.load_judgments(path, PR_IDS)
    message = str(excinfo.value)
    assert "alpha#1" in message
    assert repr(field) in message


def test_a_file_with_no_entry_is_the_case_where_nothing_is_reviewed(tmp_path):
    path = write_judgments(tmp_path, [])

    assert friction_round.load_judgments(path, PR_IDS) == {}


@pytest.mark.parametrize("payload", [{"alpha#1": "legitimate"}, "legitimate",
                                     [["alpha#1", "legitimate"]]])
def test_a_judgment_file_that_is_not_a_list_of_entries_is_refused_by_name(
        tmp_path, payload):
    path = tmp_path / "judgments.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(friction_round.Refusal) as excinfo:
        friction_round.load_judgments(path, PR_IDS)
    assert "judgment" in str(excinfo.value)


def test_a_judgment_file_that_cannot_be_read_is_refused_by_name(tmp_path):
    path = tmp_path / "judgments.json"
    path.write_text("not json at all\n", encoding="utf-8")

    with pytest.raises(friction_round.Refusal) as excinfo:
        friction_round.load_judgments(path, PR_IDS)
    assert "judgment" in str(excinfo.value)

    with pytest.raises(friction_round.Refusal) as excinfo:
        friction_round.load_judgments(tmp_path / "nowhere.json", PR_IDS)
    assert "judgment" in str(excinfo.value)


# -- the friction round: merge, run the harness, write the measures ---------


def test_the_round_merges_the_judgments_and_runs_the_existing_harness(tmp_path):
    out = tmp_path / "friction-round.json"
    merged = tmp_path / "pr-log-reviewed.json"

    report = friction_round.run_round(PR_LOG, JUDGMENTS, CONSENT,
                                      out=out, merged_log=merged)

    measures = report["measures"]
    interruption = measures["interruption_rate"]
    assert (interruption["k"], interruption["n"]) == (3, 4)
    assert interruption["denominator"] == \
        "merged pull requests that touched tests"

    unnecessary = measures["unnecessary_interruption_rate"]
    assert (unnecessary["k"], unnecessary["n"]) == (1, 2)
    assert unnecessary["unreviewed_alerts"] == 1
    assert unnecessary["denominator"] == \
        "flagged pull requests with a recorded human judgment"

    time_to_resolve = measures["time_to_resolve_seconds"]
    assert (time_to_resolve["n"], time_to_resolve["flagged_alerts"]) == (2, 3)
    assert (time_to_resolve["mean"], time_to_resolve["median"]) == \
        (10800.0, 10800.0)

    override = measures["override_rate"]
    assert (override["k"], override["n"]) == (1, 3)
    removal = measures["removal_optout_rate"]
    assert (removal["k"], removal["n"]) == (0, 1)

    # the five measures are the existing harness's, computed over the merge
    assert measures == shadow_friction.replay(merged, CONSENT)["measures"]

    rows = json.loads(merged.read_text(encoding="utf-8"))
    assert [row["human_judgment"] for row in rows] == \
        ["legitimate", "illegitimate", None, None, None]
    assert json.loads(out.read_text(encoding="utf-8")) == report


def test_the_round_writes_the_judgment_coverage_reviewed_versus_unreviewed(
        tmp_path):
    report = friction_round.run_round(PR_LOG, JUDGMENTS, CONSENT,
                                      out=tmp_path / "out.json",
                                      merged_log=tmp_path / "merged.json")

    assert report["judgment_coverage"] == {
        "alerts": 3, "reviewed": 2, "unreviewed": 1,
        "denominator": "flagged pull requests"}


def test_a_legitimate_change_is_an_unnecessary_interruption_and_an_illegitimate_one_is_not(
        tmp_path):
    records = [
        {"pr": "alpha#1", "repository": "alpha", "touched_tests": True,
         "checker_flagged": True, "human_judgment": None},
        {"pr": "alpha#2", "repository": "alpha", "touched_tests": True,
         "checker_flagged": True, "human_judgment": None},
    ]
    pr_log = tmp_path / "pr-log.json"
    pr_log.write_text(json.dumps(records), encoding="utf-8")
    judgments = write_judgments(tmp_path, [judgment("alpha#1"),
                                           judgment("alpha#2",
                                                    value="illegitimate")])

    report = friction_round.run_round(pr_log, judgments, CONSENT,
                                      out=tmp_path / "out.json",
                                      merged_log=tmp_path / "merged.json")

    # the legitimate change made its alert a false alarm -- 1 unnecessary of
    # the 2 reviewed; the illegitimate change made its alert necessary
    unnecessary = report["measures"]["unnecessary_interruption_rate"]
    assert (unnecessary["k"], unnecessary["n"]) == (1, 2)


def test_an_unreviewed_alert_is_excluded_and_the_denominator_states_it(tmp_path):
    report = friction_round.run_round(PR_LOG, JUDGMENTS, CONSENT,
                                      out=tmp_path / "out.json",
                                      merged_log=tmp_path / "merged.json")

    unnecessary = report["measures"]["unnecessary_interruption_rate"]
    assert (unnecessary["k"], unnecessary["n"]) == (1, 2)
    assert report["judgment_coverage"]["unreviewed"] == 1
    rendered = friction_round.render(report)
    assert "1 unreviewed alert excluded" in rendered
    assert "never counted as unnecessary" in rendered


def test_the_measures_and_coverage_are_rendered_with_their_denominators(tmp_path):
    report = friction_round.run_round(PR_LOG, JUDGMENTS, CONSENT,
                                      out=tmp_path / "out.json",
                                      merged_log=tmp_path / "merged.json")

    assert friction_round.render(report) == (
        "shadow friction: offline shadow replay over the recorded PR log and "
        "consent file; posts nothing, no network access\n"
        "consented repositories in the log (1): alpha\n"
        "merged pull requests: 5\n"
        "interruption rate: 3/4=0.750 (CP95 [0.194, 0.994]) -- denominator: "
        "merged pull requests that touched tests\n"
        "unnecessary interruptions: 1/2=0.500 (CP95 [0.013, 0.987]) -- "
        "denominator: flagged pull requests with a recorded human judgment "
        "(1 unreviewed alert excluded; an unreviewed alert is never counted "
        "as unnecessary)\n"
        "time to resolve: 2 of 3 flagged pull requests with both timestamps "
        "-- mean 10800.0s median 10800.0s min 7200.0s max 14400.0s\n"
        "override rate: 1/3=0.333 (CP95 [0.008, 0.906]) -- denominator: "
        "flagged pull requests\n"
        "removal or opt-out: 0/1=0.000 (CP95 [0.000, 0.975]) -- denominator: "
        "consented repositories appearing in the PR log\n"
        "judgment coverage: 2 of 3 alerts reviewed -- 1 unreviewed alert "
        "(denominator: flagged pull requests; an unreviewed alert is never "
        "counted as unnecessary)\n")


# -- the round's refusals leave nothing written -----------------------------


def test_the_round_refuses_a_judgment_naming_a_pr_absent_from_the_log(
        tmp_path, capsys):
    judgments = write_judgments(tmp_path, [judgment("alpha#99")])
    out = tmp_path / "friction-round.json"
    merged = tmp_path / "pr-log-reviewed.json"

    with pytest.raises(friction_round.Refusal) as excinfo:
        friction_round.run_round(PR_LOG, judgments, CONSENT,
                                 out=out, merged_log=merged)
    assert "alpha#99" in str(excinfo.value)
    assert not out.exists()
    assert not merged.exists()

    code = friction_round.main(["--pr-log", str(PR_LOG),
                                "--judgments", str(judgments),
                                "--consent", str(CONSENT),
                                "--out", str(out),
                                "--merged-log", str(merged)])
    assert code == 2
    captured = capsys.readouterr()
    assert "alpha#99" in captured.err
    assert not out.exists()
    assert not merged.exists()


def test_the_round_refuses_a_judgment_value_outside_the_two(tmp_path):
    judgments = write_judgments(tmp_path, [judgment("alpha#1", value="maybe")])

    with pytest.raises(friction_round.Refusal) as excinfo:
        friction_round.run_round(PR_LOG, judgments, CONSENT,
                                 out=tmp_path / "out.json",
                                 merged_log=tmp_path / "merged.json")
    message = str(excinfo.value)
    assert "alpha#1" in message
    assert "'maybe'" in message


def test_the_round_keeps_the_harness_consent_refusal_by_name(tmp_path, capsys):
    unconsented = HERE / "fixtures" / "shadow_friction" / "pr-log-unconsented.json"
    judgments = write_judgments(tmp_path, [])
    out = tmp_path / "friction-round.json"

    code = friction_round.main(["--pr-log", str(unconsented),
                                "--judgments", str(judgments),
                                "--consent", str(CONSENT),
                                "--out", str(out),
                                "--merged-log", str(tmp_path / "merged.json")])
    assert code == 2
    captured = capsys.readouterr()
    assert 'repository "rogue"' in captured.err
    assert "no recorded consent" in captured.err
    assert not out.exists()


def test_the_command_writes_both_artifacts(tmp_path, capsys):
    out = tmp_path / "friction-round.json"
    merged = tmp_path / "pr-log-reviewed.json"

    code = friction_round.main(["--pr-log", str(PR_LOG),
                                "--judgments", str(JUDGMENTS),
                                "--consent", str(CONSENT),
                                "--out", str(out),
                                "--merged-log", str(merged)])
    assert code == 0
    captured = capsys.readouterr()
    assert "judgment coverage: 2 of 3 alerts reviewed" in captured.out
    assert "posts nothing, no network access" in captured.out
    assert out.exists()
    assert merged.exists()
