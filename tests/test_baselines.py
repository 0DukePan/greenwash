"""Baseline adapters over the same corpus records: record in, result out.

Four detector baselines consume identical `CaseRecord`s -- the ticket-07
corpus record plus the fixed material a detector judges -- and emit one
comparable `BaselineResult` per case, stated in the corpus label vocabulary
("tampered", "clean") plus "abstain". Every result records the version that
produced it. B0 (path rule) and B1 (held-out tests) run in process; B2 (the
LLM judge) and B3 (the close competitor) are exercised through stub
executables, so the adapter contract -- the invocation, the parse, the frozen
prompt and model, the pinned version, the three judge runs and their variance
-- is tested without the external tools or any network.

The fixture corpus in tests/fixtures/corpus is the tiny in-repo corpus with
known outcomes: a tamper and its matched legitimate twin per technique, one
source-only tamper no path rule can see, and a held-out pair whose hidden
suites are the source's evidence. The expected table below is literal: a
baseline is scored against the gold labels later, by the evaluation runner;
here every baseline is held to what it honestly does, including the path
rule's false alarms on legitimate test edits and its miss on a source-only
tamper.
"""

import dataclasses
import hashlib
import json
import sys
from pathlib import Path
from string import Template

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import baselines, corpus  # noqa: E402

FIXTURE_CORPUS = HERE / "fixtures" / "corpus"


def corpus_records():
    return baselines.load_case_records(FIXTURE_CORPUS)


def record_with(diff, heldout=""):
    case = corpus.case_from_record({
        "id": "unit-case", "source": "fixture: unit", "technique": "assertion-weakened",
        "label": "clean", "split": "dev", "task": "unit-task",
        "repository": "https://example.org/fixture/unit", "license": "MIT"})
    return baselines.CaseRecord(case=case, diff=diff, heldout=heldout)


def diff_touching(path, deleted=False):
    if deleted:
        return (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ /dev/null\n"
                "@@ -1,1 +0,0 @@\n-x = 1\n")
    return (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n")


# -- stub executables: canned tools standing in for the judge and the competitor

JUDGE_STUB = Template("""\
import json
import os
import sys
from string import Template  # noqa: F401

state_path = $state
log_path = $log
verdicts = $script

case_path = sys.argv[sys.argv.index("--case") + 1]
payload = json.load(open(case_path, encoding="utf-8"))
with open(log_path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"argv": sys.argv[1:], "payload": payload}) + "\\n")

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


def judge_stub(tmp_path, verdicts):
    path = tmp_path / "judge_stub.py"
    path.write_text(JUDGE_STUB.substitute(
        state=json.dumps(str(tmp_path / "judge_state.json")),
        log=json.dumps(str(tmp_path / "judge_log.jsonl")),
        script=json.dumps(verdicts)), encoding="utf-8")
    return (sys.executable, str(path))


def competitor_stub(tmp_path, exits, version=baselines.COMPETITOR_VERSION):
    path = tmp_path / "competitor_stub.py"
    path.write_text(COMPETITOR_STUB.substitute(
        version=json.dumps(version), script=json.dumps(exits)),
        encoding="utf-8")
    return (sys.executable, str(path))


def judge_log(tmp_path):
    path = tmp_path / "judge_log.jsonl"
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


# The honest expected table. The path rule earns two false alarms on clean
# twins and one miss on a source-only tamper; the judge's first case is
# deliberately disputed across its three runs.
JUDGE_VERDICTS = {
    "assertion_update_tamper": ["tampered", "clean", "tampered"],
    "assertion_update_twin": ["clean", "clean", "clean"],
    "special_case_tamper": ["tampered", "tampered", "tampered"],
    "heldout_expected_value_tamper": ["tampered", "tampered", "tampered"],
    "heldout_expected_value_twin": ["clean", "clean", "clean"],
}
COMPETITOR_EXITS = {
    "assertion_update_tamper": 1,
    "assertion_update_twin": 0,
    "special_case_tamper": 1,
    "heldout_expected_value_tamper": 1,
    "heldout_expected_value_twin": 0,
}
EXPECTED = {
    "B0": {"assertion_update_tamper": "tampered",
           "assertion_update_twin": "tampered",
           "special_case_tamper": "clean",
           "heldout_expected_value_tamper": "tampered",
           "heldout_expected_value_twin": "tampered"},
    "B1": {"assertion_update_tamper": "abstain",
           "assertion_update_twin": "abstain",
           "special_case_tamper": "abstain",
           "heldout_expected_value_tamper": "tampered",
           "heldout_expected_value_twin": "clean"},
    "B2": {case: (verdicts[0] if len(set(verdicts)) == 1 else
                  max(set(verdicts), key=verdicts.count))
           for case, verdicts in JUDGE_VERDICTS.items()},
    "B3": {case: ("clean" if code == 0 else "tampered")
           for case, code in COMPETITOR_EXITS.items()},
}


def all_baselines(tmp_path):
    return (baselines.PathRuleBaseline(), baselines.HeldoutBaseline(),
            baselines.JudgeBaseline(executable=judge_stub(tmp_path, JUDGE_VERDICTS)),
            baselines.CompetitorBaseline(
                executable=competitor_stub(tmp_path, COMPETITOR_EXITS)))


# -- the adapter contract: one comparable result per case, version recorded ---

def test_every_baseline_emits_one_comparable_result_per_case(tmp_path):
    records = corpus_records()
    for baseline in all_baselines(tmp_path):
        results = baseline.run_all(records)
        assert [result.case for result in results] == [record.case.id
                                                      for record in records]
        for result in results:
            assert result.baseline == baseline.id, result
            assert result.prediction in ("tampered", "clean", "abstain"), result
            assert result.version, result


def test_each_baseline_matches_its_known_outcomes_on_the_fixture_corpus(tmp_path):
    for baseline in all_baselines(tmp_path):
        results = {result.case: result.prediction
                   for result in baseline.run_all(corpus_records())}
        assert results == EXPECTED[baseline.id], baseline.id


# -- B0: a path rule flagging any test-file edit ------------------------------

@pytest.mark.parametrize("path", ["tests/test_calc.py", "src/tests/test_calc.py",
                                 "test_calc.py", "calc_test.js", "calc.spec.js",
                                 "spec/calc.js"])
def test_the_path_rule_flags_any_test_file_edit(path):
    result = baselines.PathRuleBaseline().run(record_with(diff_touching(path)))
    assert result.prediction == "tampered"
    assert result.detail["test_edits"] == [path]


@pytest.mark.parametrize("path", ["src/calc.py", "docs/calc.md"])
def test_the_path_rule_passes_a_change_that_touches_no_test_file(path):
    result = baselines.PathRuleBaseline().run(record_with(diff_touching(path)))
    assert result.prediction == "clean"
    assert result.detail["test_edits"] == []


def test_the_path_rule_flags_a_deleted_test_file():
    result = baselines.PathRuleBaseline().run(
        record_with(diff_touching("tests/test_old.py", deleted=True)))
    assert result.prediction == "tampered"


# -- B1: held-out tests where the source provides them ------------------------

def test_the_heldout_baseline_judges_by_the_suite_the_source_provides():
    results = {result.case: result
               for result in baselines.HeldoutBaseline().run_all(corpus_records())}
    assert results["heldout_expected_value_tamper"].prediction == "tampered"
    assert results["heldout_expected_value_twin"].prediction == "clean"


def test_the_heldout_baseline_abstains_where_the_source_provides_no_suite():
    results = {result.case: result
               for result in baselines.HeldoutBaseline().run_all(corpus_records())}
    assert results["assertion_update_tamper"].prediction == "abstain"
    assert "no held-out suite" in results["assertion_update_tamper"].detail["reason"]


# -- B2: the judge harness, frozen prompt and model, three runs per case ------

def test_the_judge_runs_three_times_per_case_and_reports_its_variance(tmp_path):
    results = {result.case: result for result in baselines.JudgeBaseline(
        executable=judge_stub(tmp_path, JUDGE_VERDICTS)).run_all(corpus_records())}
    assert len(judge_log(tmp_path)) == 3 * len(results)   # three runs per case

    disputed = results["assertion_update_tamper"]
    assert disputed.detail["runs"] == ["tampered", "clean", "tampered"]
    assert disputed.prediction == "tampered"              # the majority of its runs
    assert disputed.variance == pytest.approx(1 / 3)      # variance of [1, 0, 1]

    agreed = results["special_case_tamper"]
    assert agreed.detail["runs"] == ["tampered", "tampered", "tampered"]
    assert agreed.variance == 0.0


def test_the_judge_uses_the_frozen_prompt_and_model_and_never_reads_the_gold_label(tmp_path):
    results = baselines.JudgeBaseline(
        executable=judge_stub(tmp_path, JUDGE_VERDICTS)).run_all(corpus_records())
    for entry in judge_log(tmp_path):
        argv = entry["argv"]
        assert argv[argv.index("--model") + 1] == baselines.JUDGE_MODEL
        assert argv[argv.index("--prompt") + 1] == baselines.JUDGE_PROMPT
        for hidden in ("label", "technique", "origin", "split"):
            assert hidden not in entry["payload"], entry["payload"]
    for result in results:
        assert baselines.JUDGE_MODEL in result.version
        assert result.detail["prompt_sha256"] == hashlib.sha256(
            baselines.JUDGE_PROMPT.encode("utf-8")).hexdigest()


# -- B3: the competitor at a pinned version, default configuration ------------

def test_the_competitor_records_its_pinned_version_in_every_result(tmp_path):
    results = baselines.CompetitorBaseline(
        executable=competitor_stub(tmp_path, COMPETITOR_EXITS)).run_all(corpus_records())
    for result in results:
        assert result.version == baselines.COMPETITOR_VERSION
        assert result.detail["pinned"] == baselines.COMPETITOR_VERSION
    assert {result.case: result.prediction for result in results} == EXPECTED["B3"]


def test_the_competitor_refuses_an_unpinned_version(tmp_path):
    stub = competitor_stub(tmp_path, COMPETITOR_EXITS, version="9.9.9-drift")
    results = baselines.CompetitorBaseline(executable=stub).run_all(corpus_records())
    for result in results:
        assert result.prediction == "abstain"
        assert baselines.COMPETITOR_VERSION in result.detail["reason"]
        assert "9.9.9-drift" in result.detail["reason"]


# -- no evaluation-time knob tunes a baseline per case ------------------------

def test_no_evaluation_time_knob_tunes_a_baseline_per_case(tmp_path):
    record = corpus_records()[0]
    for baseline in all_baselines(tmp_path):
        with pytest.raises(TypeError):
            baseline.run(record, threshold=0.9)
        with pytest.raises(TypeError):
            baseline.run(record, record)
    with pytest.raises(dataclasses.FrozenInstanceError):
        baselines.JudgeBaseline().executable = ("some-other-judge",)
    with pytest.raises(dataclasses.FrozenInstanceError):
        baselines.CompetitorBaseline().executable = ("some-other-competitor",)
