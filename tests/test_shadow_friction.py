"""The offline shadow-replay friction harness: the five measures, pinned.

One module under benchmark/ turns a recorded PR log (one record per merged
pull request) plus a consent file into the Stage 5 friction numbers, each with
its explicit denominator: interruption rate over PRs that touched tests,
unnecessary interruptions from the recorded human judgments, time to resolve
where timestamps exist, override rate, and removal or opt-out where recorded.
The harness is offline -- it reads the two recorded inputs and posts nothing
anywhere -- and it refuses by name any repository whose consent is not
recorded.

The fixture PR log in tests/fixtures/shadow_friction is twelve merged pull
requests with known outcomes: eight touched tests and four of those were
flagged; five alerts in all; two judged illegitimate, two judged legitimate,
one unreviewed (never counted as unnecessary, and never in the reviewed
denominator); three alerts carry both timestamps (2h, 4h, 6h); two overrides;
one recorded removal. The report is pinned literally below -- denominators,
interval columns and the offline statement included.
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import shadow_friction  # noqa: E402

FIXTURES = HERE / "fixtures" / "shadow_friction"
PR_LOG = FIXTURES / "pr-log.json"
CONSENT = FIXTURES / "consent.json"
PR_LOG_UNCONSENTED = FIXTURES / "pr-log-unconsented.json"


def test_the_fixture_pr_log_produces_the_five_friction_measures():
    report = shadow_friction.replay(PR_LOG, CONSENT)
    measures = report["measures"]

    interruption = measures["interruption_rate"]
    assert (interruption["k"], interruption["n"],
            interruption["estimate"]) == (4, 8, 0.5)
    assert interruption["denominator"] == \
        "merged pull requests that touched tests"

    unnecessary = measures["unnecessary_interruption_rate"]
    assert (unnecessary["k"], unnecessary["n"],
            unnecessary["estimate"]) == (2, 4, 0.5)
    assert unnecessary["denominator"] == \
        "flagged pull requests with a recorded human judgment"
    assert unnecessary["unreviewed_alerts"] == 1

    time_to_resolve = measures["time_to_resolve_seconds"]
    assert time_to_resolve["n"] == 3
    assert time_to_resolve["flagged_alerts"] == 5
    assert (time_to_resolve["mean"], time_to_resolve["median"],
            time_to_resolve["min"],
            time_to_resolve["max"]) == (14400.0, 14400.0, 7200.0, 21600.0)
    assert time_to_resolve["denominator"] == \
        "flagged pull requests with both flagged_at and resolved_at"

    override = measures["override_rate"]
    assert (override["k"], override["n"],
            override["estimate"]) == (2, 5, 0.4)
    assert override["denominator"] == "flagged pull requests"

    removal = measures["removal_optout_rate"]
    assert (removal["k"], removal["n"],
            removal["estimate"]) == (1, 2, 0.5)
    assert removal["denominator"] == \
        "consented repositories appearing in the PR log"


def test_the_report_is_literal_denominators_intervals_and_offline_statement():
    report = shadow_friction.replay(PR_LOG, CONSENT)
    assert shadow_friction.render(report) == (
        "shadow friction: offline shadow replay over the recorded PR log and "
        "consent file; posts nothing, no network access\n"
        "consented repositories in the log (2): alpha beta\n"
        "merged pull requests: 12\n"
        "interruption rate: 4/8=0.500 (CP95 [0.157, 0.843]) -- denominator: "
        "merged pull requests that touched tests\n"
        "unnecessary interruptions: 2/4=0.500 (CP95 [0.068, 0.932]) -- "
        "denominator: flagged pull requests with a recorded human judgment "
        "(1 unreviewed alert excluded; an unreviewed alert is never counted "
        "as unnecessary)\n"
        "time to resolve: 3 of 5 flagged pull requests with both timestamps "
        "-- mean 14400.0s median 14400.0s min 7200.0s max 21600.0s\n"
        "override rate: 2/5=0.400 (CP95 [0.053, 0.853]) -- denominator: "
        "flagged pull requests\n"
        "removal or opt-out: 1/2=0.500 (CP95 [0.013, 0.987]) -- denominator: "
        "consented repositories appearing in the PR log\n")


def test_a_legitimate_alert_is_not_unnecessary_and_an_unreviewed_alert_is_not(
        tmp_path):
    records = [
        {"pr": "a#1", "repository": "alpha", "touched_tests": True,
         "checker_flagged": True, "human_judgment": "illegitimate"},
        {"pr": "a#2", "repository": "alpha", "touched_tests": True,
         "checker_flagged": True, "human_judgment": "legitimate"},
        {"pr": "a#3", "repository": "alpha", "touched_tests": True,
         "checker_flagged": True, "human_judgment": None},
    ]
    pr_log = tmp_path / "pr-log.json"
    pr_log.write_text(json.dumps(records), encoding="utf-8")
    consent = tmp_path / "consent.json"
    consent.write_text(json.dumps({"repositories": ["alpha"]}),
                       encoding="utf-8")

    measures = shadow_friction.replay(pr_log, consent)["measures"]
    unnecessary = measures["unnecessary_interruption_rate"]
    # Only the judged-illegitimate alert is unnecessary; the legitimate one is
    # not, and the unreviewed one is in neither column: 1 of the 2 reviewed.
    assert (unnecessary["k"], unnecessary["n"]) == (1, 2)
    assert unnecessary["unreviewed_alerts"] == 1


def test_a_repository_without_recorded_consent_is_refused_by_name(
        tmp_path, capsys):
    with pytest.raises(shadow_friction.Refusal) as excinfo:
        shadow_friction.replay(PR_LOG_UNCONSENTED, CONSENT)
    assert 'repository "rogue"' in str(excinfo.value)
    assert "no recorded consent" in str(excinfo.value)

    out = tmp_path / "friction.json"
    code = shadow_friction.main([
        "--pr-log", str(PR_LOG_UNCONSENTED),
        "--consent", str(CONSENT),
        "--out", str(out)])
    assert code == 2
    captured = capsys.readouterr()
    assert 'repository "rogue"' in captured.err
    assert "no recorded consent" in captured.err
    assert not out.exists()


def test_the_report_states_it_is_offline_and_posts_nothing():
    report = shadow_friction.replay(PR_LOG, CONSENT)
    assert report["offline"] is True
    assert ("offline shadow replay over the recorded PR log and consent file; "
            "posts nothing, no network access") in shadow_friction.render(report)
