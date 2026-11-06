"""The offline PR-log collector: one consented repository's merged PR export
plus a local clone, replayed into the friction harness's PR-log format.

The seam is `collector.collect(export, clone, consent)`. Fixtures are built
here, not stored: a tiny local clone whose history carries one merged PR that
touched tests and was flagged (a bare skip added to a test), one that touched
no tests (a README note), an override marker and an opt-out marker. Refusals
are named: a repository absent from the consent record, a missing commit, a
missing field, a malformed timestamp, a path leaving the clone, and a per-PR
time bound. No test touches the network; no test runs repository code -- and
one test proves the collector does not either (a textconv filter planted in
the clone would fire on a careless `git diff`).
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import collector  # noqa: E402
import shadow_friction  # noqa: E402

SCOPE = "history replay, report-only, no comments"

FLAGGED_TEST = '''import pytest

from app import work


def test_works():
    assert work() == 2


@pytest.mark.skip
def test_later():
    assert work() == 3
'''

CLEAN_TEST = '''from app import work


def test_works():
    assert work() == 2
'''


# -- fixture construction: a small local clone, built here ------------------


def run_git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), check=True,
                          capture_output=True, text=True)


def head_of(repo):
    return run_git(repo, "rev-parse", "HEAD").stdout.strip()


def build_clone(tmp_path):
    """A three-commit clone: base, a PR that disables a test, a docs note.

    The working tree stays at the tip, like an operator's local clone.
    """
    clone = tmp_path / "clone"
    clone.mkdir()
    run_git(clone, "init")
    run_git(clone, "config", "user.name", "Trial Fixture")
    run_git(clone, "config", "user.email", "trial@example.invalid")
    (clone / "app.py").write_text("def work():\n    return 2\n", encoding="utf-8")
    (clone / "README.md").write_text("# fixture\n", encoding="utf-8")
    (clone / "tests").mkdir()
    (clone / "tests" / "test_app.py").write_text(CLEAN_TEST, encoding="utf-8")
    run_git(clone, "add", "-A")
    run_git(clone, "commit", "-m", "base")
    base = head_of(clone)
    (clone / "tests" / "test_app.py").write_text(FLAGGED_TEST, encoding="utf-8")
    run_git(clone, "add", "-A")
    run_git(clone, "commit", "-m", "disable a test")
    flagged = head_of(clone)
    (clone / "README.md").write_text("# fixture\n\nNotes for the trial.\n",
                                     encoding="utf-8")
    run_git(clone, "add", "-A")
    run_git(clone, "commit", "-m", "docs")
    docs = head_of(clone)
    return clone, base, flagged, docs


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def consent_record(**overrides):
    record = {"repositories": ["alpha"], "contact": "owner@example.invalid",
              "date": "2024-02-27", "scope": SCOPE}
    record.update(overrides)
    return record


def pr_entry(number, merge_base, head, **overrides):
    entry = {"number": number, "merge_base": merge_base, "head": head,
             "merged_at": "2024-03-01T10:00:00Z"}
    entry.update(overrides)
    return entry


def fixture_inputs(tmp_path, entries, repository="alpha", consent=None):
    """The clone is built first; `entries` may be a callable receiving its
    (base, flagged, docs) commit ids, for exports that name real commits."""
    clone, base, flagged, docs = build_clone(tmp_path)
    if callable(entries):
        entries = entries(base, flagged, docs)
    export = write_json(tmp_path / "export.json",
                        {"repository": repository, "pull_requests": entries})
    consent = write_json(tmp_path / "consent.json",
                         consent if consent is not None else consent_record())
    return clone, export, consent, base, flagged, docs


# -- the seam: the export and clone become the harness's PR log -------------


def test_the_fixture_export_and_clone_produce_the_harness_pr_log(tmp_path):
    clone, export, consent, base, flagged, docs = fixture_inputs(
        tmp_path,
        lambda base, flagged, docs: [
            pr_entry(1, base, flagged,
                     flagged_at="2024-03-01T09:00:00Z",
                     resolved_at="2024-03-01T11:00:00Z", override=True),
            pr_entry(2, flagged, docs, merged_at="2024-03-02T10:00:00Z",
                     opt_out=True),
        ])
    out = tmp_path / "pr-log.json"

    records = collector.collect(export, clone, consent, out_path=out)

    assert records == [
        {"pr": "alpha#1", "repository": "alpha", "touched_tests": True,
         "checker_flagged": True, "human_judgment": None,
         "merged_at": "2024-03-01T10:00:00Z",
         "flagged_at": "2024-03-01T09:00:00Z",
         "resolved_at": "2024-03-01T11:00:00Z",
         "override": True, "removal_or_optout": False},
        {"pr": "alpha#2", "repository": "alpha", "touched_tests": False,
         "checker_flagged": False, "human_judgment": None,
         "merged_at": "2024-03-02T10:00:00Z",
         "flagged_at": None, "resolved_at": None,
         "override": False, "removal_or_optout": True},
    ]
    assert json.loads(out.read_text(encoding="utf-8")) == records

    # what the collector writes is what the friction harness consumes
    report = shadow_friction.replay(out, consent)
    measures = report["measures"]
    assert report["merged_prs"] == 2
    assert (measures["interruption_rate"]["k"],
            measures["interruption_rate"]["n"]) == (1, 1)
    assert measures["unnecessary_interruption_rate"]["unreviewed_alerts"] == 1


# -- consent first ----------------------------------------------------------


def test_a_repository_absent_from_the_consent_record_is_refused_by_name(
        tmp_path, capsys):
    clone, export, consent, base, flagged, docs = fixture_inputs(
        tmp_path, lambda base, flagged, docs: [pr_entry(1, base, flagged)],
        repository="rogue")
    out = tmp_path / "pr-log.json"

    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, clone, consent, out_path=out)
    assert '"rogue"' in str(excinfo.value)
    assert "no recorded consent" in str(excinfo.value)
    assert not out.exists()

    code = collector.main(["--export", str(export), "--clone", str(clone),
                           "--consent", str(consent), "--out", str(out)])
    assert code == 2
    captured = capsys.readouterr()
    assert '"rogue"' in captured.err
    assert "no recorded consent" in captured.err
    assert not out.exists()


@pytest.mark.parametrize("missing", ["repositories", "contact", "date", "scope"])
def test_the_consent_record_names_repositories_contact_date_and_scope(
        tmp_path, missing):
    record = consent_record()
    del record[missing]
    clone, export, consent, base, flagged, docs = fixture_inputs(
        tmp_path, lambda base, flagged, docs: [pr_entry(1, base, flagged)],
        consent=record)

    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, clone, consent)
    assert missing in str(excinfo.value)


def test_a_consent_record_with_the_wrong_scope_or_a_malformed_date_is_refused(
        tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    clone, export, consent, base, flagged, docs = fixture_inputs(
        first, lambda base, flagged, docs: [pr_entry(1, base, flagged)],
        consent=consent_record(scope="whatever"))
    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, clone, consent)
    assert SCOPE in str(excinfo.value)

    clone, export, consent, base, flagged, docs = fixture_inputs(
        second, lambda base, flagged, docs: [pr_entry(1, base, flagged)],
        consent=consent_record(date="last Tuesday"))
    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, clone, consent)
    assert "'date'" in str(excinfo.value)
    assert "ISO 8601" in str(excinfo.value)


# -- fail-closed refusals, each named ---------------------------------------


def test_an_export_missing_a_required_field_is_refused_by_name(tmp_path):
    clone, base, flagged, docs = build_clone(tmp_path)
    consent = write_json(tmp_path / "consent.json", consent_record())

    for field in ("repository", "pull_requests"):
        payload = {"repository": "alpha", "pull_requests": [pr_entry(1, base, flagged)]}
        del payload[field]
        export = write_json(tmp_path / "export.json", payload)
        with pytest.raises(collector.Refusal) as excinfo:
            collector.collect(export, clone, consent)
        assert repr(field) in str(excinfo.value)

    export = write_json(tmp_path / "export.json",
                        {"repository": "alpha", "pull_requests": []})
    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, clone, consent)
    assert "'pull_requests'" in str(excinfo.value)


@pytest.mark.parametrize("field", ["number", "merge_base", "head", "merged_at"])
def test_a_pull_request_missing_a_required_field_is_refused_by_name(
        tmp_path, field):
    entry = pr_entry(1, "0" * 40, "0" * 40)
    del entry[field]
    clone, export, consent, base, flagged, docs = fixture_inputs(
        tmp_path, [entry])

    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, clone, consent)
    assert repr(field) in str(excinfo.value)
    assert "pull request" in str(excinfo.value)


@pytest.mark.parametrize("field", ["merge_base", "head"])
def test_a_missing_commit_is_refused_by_name(tmp_path, field):
    ghost = "0" * 40

    def entries(base, flagged, docs):
        entry = pr_entry(1, base, flagged)
        entry[field] = ghost
        return [entry]

    clone, export, consent, base, flagged, docs = fixture_inputs(
        tmp_path, entries)

    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, clone, consent)
    message = str(excinfo.value)
    assert "alpha#1" in message
    assert ghost in message
    assert "missing" in message


@pytest.mark.parametrize(("field", "value"),
                         [("merged_at", "yesterday"),
                          ("flagged_at", "2024-13-99T99:99:99Z"),
                          ("resolved_at", 5)])
def test_a_malformed_timestamp_is_refused_by_name(tmp_path, field, value):
    clone, export, consent, base, flagged, docs = fixture_inputs(
        tmp_path,
        lambda base, flagged, docs: [pr_entry(1, base, flagged,
                                              **{field: value})])

    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, clone, consent)
    message = str(excinfo.value)
    assert "alpha#1" in message
    assert repr(field) in message
    assert "ISO 8601" in message


def test_a_path_leaving_the_clone_is_refused_by_name(tmp_path):
    clone, export, consent, base, flagged, docs = fixture_inputs(
        tmp_path,
        lambda base, flagged, docs: [pr_entry(1, base, flagged,
                                              files=["../outside/evil.py"])])

    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, clone, consent)
    message = str(excinfo.value)
    assert "alpha#1" in message
    assert "../outside/evil.py" in message
    assert "leaves the clone" in message


def test_a_diff_path_leaving_the_clone_is_refused_by_name(tmp_path, monkeypatch):
    clone, export, consent, base, flagged, docs = fixture_inputs(
        tmp_path, lambda base, flagged, docs: [pr_entry(1, base, flagged)])

    def escaping_diff(clone_path, merge_base, head, timeout):
        return ("diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
                "@@ -0,0 +1 @@\n+escape\n"
                "diff --git a/../../escape.py b/../../escape.py\n"
                "--- a/../../escape.py\n+++ b/../../escape.py\n"
                "@@ -0,0 +1 @@\n+escape\n")

    monkeypatch.setattr(collector, "_pr_diff", escaping_diff)
    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, clone, consent)
    message = str(excinfo.value)
    assert "../../escape.py" in message
    assert "leaves the clone" in message


def test_a_clone_that_is_not_a_git_working_tree_is_refused_by_name(tmp_path):
    clone, export, consent, base, flagged, docs = fixture_inputs(
        tmp_path, lambda base, flagged, docs: [pr_entry(1, base, flagged)])
    plain = tmp_path / "plain"
    plain.mkdir()

    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, plain, consent)
    assert "clone" in str(excinfo.value)

    with pytest.raises(collector.Refusal) as excinfo:
        collector.collect(export, tmp_path / "nowhere", consent)
    assert "clone" in str(excinfo.value)


# -- offline, no repository code, bounded time ------------------------------


def test_the_collector_executes_no_repository_code(tmp_path):
    clone, base, flagged, docs = build_clone(tmp_path)
    (clone / ".gitattributes").write_text("*.txt diff=leak\n", encoding="utf-8")
    (clone / "leak.py").write_text(
        "open('LEAKED', 'w').write('x')\n", encoding="utf-8")
    (clone / "notes.txt").write_text("one\n", encoding="utf-8")
    run_git(clone, "add", "-A")
    run_git(clone, "commit", "-m", "plant a textconv trap")
    trap = head_of(clone)
    run_git(clone, "config", "diff.leak.textconv", "python leak.py")
    (clone / "notes.txt").write_text("two\n", encoding="utf-8")
    run_git(clone, "add", "-A")
    run_git(clone, "commit", "-m", "notes")
    notes = head_of(clone)

    # control: a plain `git diff` really does run the repository's filter
    run_git(clone, "diff", trap, notes)
    if not (clone / "LEAKED").exists():     # pragma: no cover - environment
        pytest.skip(reason="git did not run the textconv filter in this "
                           "environment, so the trap proves nothing here")
    (clone / "LEAKED").unlink()

    export = write_json(tmp_path / "export.json",
                        {"repository": "alpha",
                         "pull_requests": [pr_entry(1, trap, notes)]})
    consent = write_json(tmp_path / "consent.json", consent_record())
    records = collector.collect(export, clone, consent)

    assert records[0]["touched_tests"] is False
    assert records[0]["checker_flagged"] is False
    assert not (clone / "LEAKED").exists()


def test_the_collector_code_makes_no_network_calls():
    source = Path(collector.__file__).read_text(encoding="utf-8")
    assert not re.search(
        r"^\s*(?:import|from)\s+(?:socket|urllib|http|requests|httpx)\b",
        source, re.MULTILINE)


def test_each_pull_request_is_time_bounded(tmp_path, monkeypatch):
    clone, export, consent, base, flagged, docs = fixture_inputs(
        tmp_path, lambda base, flagged, docs: [pr_entry(1, base, flagged)])

    def slow_scan(diff_text, cwd=None, root=None):
        time.sleep(3.0)
        return []

    monkeypatch.setattr(collector, "scan_diff", slow_scan)
    with pytest.raises(collector.Refusal) as excinfo:
        # A one-second bound, not a millisecond one: the collector still runs
        # real git plumbing inside the bound, and Windows spawns git slower
        # than the 50 ms this test used to allow. A git timeout would be a
        # different refusal than the per-PR bound this test pins.
        collector.collect(export, clone, consent, per_pr_seconds=1.0)
    message = str(excinfo.value)
    assert "alpha#1" in message
    assert "time bound" in message


def test_a_future_timeout_is_a_refusal_not_an_escape():
    """The future's timeout is not the builtin one before Python 3.11.

    `concurrent.futures.TimeoutError` was a distinct class until 3.11 made it
    an alias of the builtin. Catching only the builtin let a slow pull request
    raise out of `collect()` on 3.10 -- the version this project still
    supports, and the one its CI matrix runs. Pinned here at the seam so the
    class difference cannot come back unnoticed.
    """
    def slow():
        time.sleep(0.3)
        return []

    with pytest.raises(collector.Refusal) as excinfo:
        collector._bounded(slow, 0.02, "alpha#1")
    assert "time bound" in str(excinfo.value)
