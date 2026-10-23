"""History mining: candidate cases read from repository history as git objects.

This is the R1/R2 collection seam. `mine_history` reads a repository's history
as git objects only -- never repository code, hooks or filters, never
repository-supplied git configuration -- and returns unadjudicated candidate
records shaped like the corpus kit's case record v2. R1 proposes commits that
change an assertion, delete a test or add a skip alongside a source change; R2
proposes edits later reverted or fixed by a linked commit and attaches that
later history as supporting evidence. Every candidate carries its route,
repository identity, license, base and head refs, a diff hash and the taxonomy
technique it looks like.

The safety contract is asserted at this seam with hostile fixture
repositories: executable sinks for hooks, filters, fsmonitor and aliases must
never fire, paths that escape the work tree are rejected by name, file sizes
and counts are bounded, and a mined candidate is written unadjudicated and
cannot enter a gate-input class.

Fixture repositories are real git repositories built in tests; mining them
never checks anything out and never runs anything from them.
"""

import hashlib
import re
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import corpus, miner  # noqa: E402
from greenwash.evidence import EvidenceError  # noqa: E402

IDENTITY = {"repository": "https://example.org/org/project", "license": "MIT"}

DIGEST = re.compile(r"[0-9a-f]{64}")


def git(cwd, *args, input=None):
    return subprocess.run(["git", *args], cwd=str(cwd), check=True,
                          capture_output=True, input=input)


def commit(repo, message, empty=False):
    git(repo, "add", "-A")
    args = ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
            "-m", message]
    if empty:
        args.insert(-2, "--allow-empty")
    git(repo, *args)
    return git(repo, "rev-parse", "HEAD").stdout.decode().strip()


def parent_of(repo, sha):
    return git(repo, "rev-parse", f"{sha}^").stdout.decode().strip()


# -- fixture history: four weakening shapes, each alongside a source change --

WIDGET_1 = "def compute(x):\n    return x + 1\n"
WIDGET_2 = WIDGET_1 + "# rounding adjusted\n"
WIDGET_3 = WIDGET_2 + "# extra suite dropped\n"
WIDGET_4 = WIDGET_3 + "# flaky check parked\n"
WIDGET_5 = WIDGET_4 + "# assertion simplified\n"
WIDGET_6 = WIDGET_5 + "# flaky check restored\n"

TEST_WIDGET_1 = (
    "from app.widget import compute\n"
    "\n"
    "def test_compute():\n"
    "    assert compute(1) == 2\n"
    "    assert compute(1) > 0\n"
    "\n"
    "def test_compute_zero():\n"
    "    assert compute(0) == 1\n"
)
TEST_WIDGET_2 = TEST_WIDGET_1.replace("assert compute(1) == 2",
                                      "assert compute(1) == 3")
TEST_WIDGET_3 = TEST_WIDGET_2.replace(
    "def test_compute_zero():",
    '@pytest.mark.skip(reason="flaky")\ndef test_compute_zero():')
TEST_WIDGET_4 = TEST_WIDGET_3.replace("    assert compute(1) > 0\n", "")
TEST_WIDGET_5 = TEST_WIDGET_4.replace('@pytest.mark.skip(reason="flaky")\n', "")

TEST_EXTRA = "from app.widget import compute\n\ndef test_extra():\n    assert compute(2) == 3\n"


def history_repo(tmp_path, revert=False):
    """A linear fixture history: c1 baseline, then four weakening commits.

    c2 changes an assertion's expected value, c3 deletes a test, c4 adds a
    skip and c5 removes an assertion -- each alongside a source change. c6
    touches docs only. With `revert`, c7 reverts c4 the way `git revert`
    writes its message.
    """
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    git(repo, "init", "-q")
    shas = {}
    (repo / "app" / "widget.py").write_text(WIDGET_1, encoding="utf-8")
    (repo / "tests" / "test_widget.py").write_text(TEST_WIDGET_1, encoding="utf-8")
    (repo / "tests" / "test_extra.py").write_text(TEST_EXTRA, encoding="utf-8")
    shas["c1"] = commit(repo, "initial release")
    (repo / "tests" / "test_widget.py").write_text(TEST_WIDGET_2, encoding="utf-8")
    (repo / "app" / "widget.py").write_text(WIDGET_2, encoding="utf-8")
    shas["c2"] = commit(repo, "adjust rounding")
    (repo / "tests" / "test_extra.py").unlink()
    (repo / "app" / "widget.py").write_text(WIDGET_3, encoding="utf-8")
    shas["c3"] = commit(repo, "drop the extra suite")
    (repo / "tests" / "test_widget.py").write_text(TEST_WIDGET_3, encoding="utf-8")
    (repo / "app" / "widget.py").write_text(WIDGET_4, encoding="utf-8")
    shas["c4"] = commit(repo, "park the flaky check")
    (repo / "tests" / "test_widget.py").write_text(TEST_WIDGET_4, encoding="utf-8")
    (repo / "app" / "widget.py").write_text(WIDGET_5, encoding="utf-8")
    shas["c5"] = commit(repo, "simplify the test")
    (repo / "README.md").write_text("docs\n", encoding="utf-8")
    shas["c6"] = commit(repo, "docs only")
    if revert:
        (repo / "tests" / "test_widget.py").write_text(TEST_WIDGET_5, encoding="utf-8")
        (repo / "app" / "widget.py").write_text(WIDGET_6, encoding="utf-8")
        shas["c7"] = commit(
            repo, 'Revert "park the flaky check"\n\nThis reverts commit '
                  f'{shas["c4"]}.')
    return repo, shas


# -- R1: assertion changes, deletions and skips alongside a source change ----

def test_mining_yields_the_expected_candidates_with_refs_and_diff_hashes(tmp_path):
    repo, shas = history_repo(tmp_path)
    candidates = miner.mine_history(repo, **IDENTITY)
    assert [(c["id"], c["route"], c["technique"]) for c in candidates] == [
        (f"R1-{shas['c2'][:12]}", "R1", "expected-value-change"),
        (f"R1-{shas['c3'][:12]}", "R1", "deleted-test"),
        (f"R1-{shas['c4'][:12]}", "R1", "skip-or-xfail"),
        (f"R1-{shas['c5'][:12]}", "R1", "assertion-weakened"),
    ]
    for candidate, key in zip(candidates, ("c2", "c3", "c4", "c5")):
        assert candidate["head_ref"] == shas[key], candidate
        assert candidate["base_ref"] == parent_of(repo, shas[key]), candidate
        assert DIGEST.fullmatch(candidate["diff_hash"]), candidate


def test_a_candidate_carries_repository_identity_license_and_task(tmp_path):
    repo, shas = history_repo(tmp_path)
    candidate = miner.mine_history(repo, **IDENTITY)[0]
    assert candidate["repository"] == IDENTITY["repository"]
    assert candidate["license"] == IDENTITY["license"]
    assert candidate["task"] == f"commit:{shas['c2']}"
    assert candidate["split"] == "dev"
    assert candidate["source"].startswith("history:")


def test_the_diff_hash_binds_the_change_and_remines_identically(tmp_path):
    repo, shas = history_repo(tmp_path)
    first = miner.mine_history(repo, **IDENTITY)
    second = miner.mine_history(repo, **IDENTITY)
    assert first == second
    hashes = [candidate["diff_hash"] for candidate in first]
    assert len(set(hashes)) == len(hashes)


def test_the_technique_is_one_the_taxonomy_knows(tmp_path):
    repo, _ = history_repo(tmp_path)
    for candidate in miner.mine_history(repo, **IDENTITY):
        assert candidate["technique"] in taxonomy_ids()


def taxonomy_ids():
    from greenwash.taxonomy import BY_ID
    return set(BY_ID)


def test_identity_the_miner_cannot_fill_is_a_rejection_naming_the_field(tmp_path):
    repo, _ = history_repo(tmp_path)
    for missing in ("repository", "license"):
        fields = dict(IDENTITY)
        fields[missing] = ""
        with pytest.raises(EvidenceError) as exc:
            miner.mine_history(repo, **fields)
        assert str(exc.value).startswith(f"{missing}:"), exc.value


# -- R2: later reverts and linked fixes attached as supporting history -------

def test_a_revert_is_attached_to_its_candidate_as_supporting_history(tmp_path):
    repo, shas = history_repo(tmp_path, revert=True)
    candidates = {c["head_ref"]: c for c in miner.mine_history(repo, **IDENTITY)}
    parked = candidates[shas["c4"]]
    # c4 weakens tests alongside a source change and is later reverted: both
    # routes reach it, and the record carries R2 -- the route whose contract
    # is that history evidence supports the label -- with the evidence on it.
    assert parked["id"] == f"R2-{shas['c4'][:12]}"
    assert parked["route"] == "R2"
    assert parked["technique"] == "skip-or-xfail"
    assert parked["supporting_history"] == [
        {"kind": "revert", "commit": shas["c7"],
         "subject": 'Revert "park the flaky check"'}]
    # c2 and c5 stay R1: nothing in later history reverts or fixes them.
    assert candidates[shas["c2"]]["route"] == "R1"
    assert candidates[shas["c2"]]["supporting_history"] == []
    assert candidates[shas["c5"]]["route"] == "R1"


def linked_repo(tmp_path):
    """d2 edits conftest.py and is reverted; d4 adds a skip with no source
    change (so R1's rule misses it) and is fixed by d5, a linked commit. d6
    only mentions d2 in passing."""
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    git(repo, "init", "-q")
    shas = {}
    (repo / "conftest.py").write_text("# fixtures\n", encoding="utf-8")
    (repo / "app" / "thing.py").write_text("def f():\n    return 1\n",
                                           encoding="utf-8")
    (repo / "tests" / "test_thing.py").write_text(
        "def test_thing():\n    assert 1 == 1\n", encoding="utf-8")
    shas["d1"] = commit(repo, "initial")
    (repo / "conftest.py").write_text("# fixtures\n# quieter\n", encoding="utf-8")
    shas["d2"] = commit(repo, "quiet the conftest")
    (repo / "conftest.py").write_text("# fixtures\n", encoding="utf-8")
    shas["d3"] = commit(
        repo, 'Revert "quiet the conftest"\n\nThis reverts commit '
              f'{shas["d2"]}.')
    (repo / "tests" / "test_thing.py").write_text(
        'import pytest\n\n@pytest.mark.skip(reason="flaky")\n'
        "def test_thing():\n    assert 1 == 1\n", encoding="utf-8")
    shas["d4"] = commit(repo, "park the flaky thing")
    (repo / "app" / "thing.py").write_text("def f():\n    return 2\n",
                                           encoding="utf-8")
    shas["d5"] = commit(repo, f'fix the real flake, see {shas["d4"][:10]}')
    shas["d6"] = commit(repo, f'see {shas["d2"][:10]} for context', empty=True)
    return repo, shas


def test_a_conftest_edit_later_reverted_is_an_r2_candidate(tmp_path):
    repo, shas = linked_repo(tmp_path)
    candidates = {c["head_ref"]: c for c in miner.mine_history(repo, **IDENTITY)}
    conftest = candidates[shas["d2"]]
    assert (conftest["route"], conftest["technique"]) == ("R2", "conftest-edit")
    assert conftest["supporting_history"] == [
        {"kind": "revert", "commit": shas["d3"],
         "subject": 'Revert "quiet the conftest"'}]


def test_a_linked_fix_is_attached_and_fills_the_r1_gap(tmp_path):
    repo, shas = linked_repo(tmp_path)
    candidates = {c["head_ref"]: c for c in miner.mine_history(repo, **IDENTITY)}
    parked = candidates[shas["d4"]]
    # d4 adds a skip with no source change, so R1's rule never sees it; the
    # linked fix is what proposes it, carrying the fix as supporting history.
    assert (parked["route"], parked["technique"]) == ("R2", "skip-or-xfail")
    assert parked["supporting_history"] == [
        {"kind": "linked-fix", "commit": shas["d5"],
         "subject": f'fix the real flake, see {shas["d4"][:10]}'}]


def test_a_bare_reference_is_not_history_evidence(tmp_path):
    repo, shas = linked_repo(tmp_path)
    candidates = {c["head_ref"]: c for c in miner.mine_history(repo, **IDENTITY)}
    assert [entry["commit"] for entry in
            candidates[shas["d2"]]["supporting_history"]] == [shas["d3"]], \
        "a message that only mentions the edit must not count as a fix"


def reverse_repo(tmp_path):
    """e2 weakens a test alongside a source change; e3 exactly reverses the
    edit with a message that never says revert or fix."""
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    git(repo, "init", "-q")
    shas = {}
    (repo / "app" / "m.py").write_text("def m():\n    return 2\n", encoding="utf-8")
    (repo / "tests" / "test_m.py").write_text("def test_m():\n    assert m() == 2\n",
                                              encoding="utf-8")
    shas["e1"] = commit(repo, "initial")
    (repo / "app" / "m.py").write_text("def m():\n    return 3\n", encoding="utf-8")
    (repo / "tests" / "test_m.py").write_text("def test_m():\n    pass\n",
                                              encoding="utf-8")
    shas["e2"] = commit(repo, "quiet the assert")
    (repo / "app" / "m.py").write_text("def m():\n    return 2\n", encoding="utf-8")
    (repo / "tests" / "test_m.py").write_text("def test_m():\n    assert m() == 2\n",
                                              encoding="utf-8")
    shas["e3"] = commit(repo, "tidy up")
    return repo, shas


def test_a_reverse_patch_is_attached_even_without_a_revert_message(tmp_path):
    repo, shas = reverse_repo(tmp_path)
    candidates = {c["head_ref"]: c for c in miner.mine_history(repo, **IDENTITY)}
    quieted = candidates[shas["e2"]]
    assert (quieted["route"], quieted["technique"]) == ("R2", "assertion-weakened")
    assert quieted["supporting_history"] == [
        {"kind": "revert", "commit": shas["e3"], "subject": "tidy up"}]
    assert shas["e3"] not in candidates, "a commit that restores tests is not a candidate"


# -- hostile repository content can neither execute nor escape --------------
#
# T18's contract, one level deeper: the miner must run git to read history,
# so the canary must prove that no repository-supplied hook, filter, alias,
# fsmonitor or git configuration is ever honored while it does.

CANARY = "CANARY.txt"
SENTINEL = "outside content that must never change"
PLUMBING = {"rev-list", "ls-tree", "cat-file"}


def weak_repo(tmp_path):
    """A fixture repository beside an `outside` directory, with one commit
    that weakens a test alongside a source change."""
    outside = tmp_path / "outside"
    outside.mkdir(exist_ok=True)
    (outside / "sentinel.txt").write_text(SENTINEL, encoding="utf-8")
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    git(repo, "init", "-q")
    (repo / "app" / "w.py").write_text("def w():\n    return 1\n", encoding="utf-8")
    (repo / "tests" / "test_w.py").write_text("def test_w():\n    assert w() == 1\n",
                                              encoding="utf-8")
    commit(repo, "initial")
    (repo / "app" / "w.py").write_text("def w():\n    return 2\n", encoding="utf-8")
    (repo / "tests" / "test_w.py").write_text("def test_w():\n    pass\n",
                                              encoding="utf-8")
    commit(repo, "quiet the assert")
    return repo


def assert_untouched_outside(tmp_path):
    assert not (tmp_path / CANARY).exists(), "a hook, filter or config ran"
    outside = tmp_path / "outside"
    assert (outside / "sentinel.txt").read_text(encoding="utf-8") == SENTINEL
    assert sorted(path.name for path in outside.iterdir()) == \
        ["secret.txt", "sentinel.txt"], "something outside the work tree changed"


def plant_execution_sink(tmp_path, repo):
    """Executable hooks, hostile repository git configuration and a filter
    driver -- each one writes the canary the moment it is honored -- plus a
    hostile global configuration in HOME."""
    canary = tmp_path / CANARY
    sink = repo / "sink.bat"
    sink.write_text(f'@echo off\ntype nul > "{canary}"\n', encoding="utf-8")
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    for name in ("pre-commit", "post-checkout", "pre-applypatch"):
        hook = hooks / name
        hook.write_text(f'#!/bin/sh\ntouch "{canary}"\n', encoding="utf-8")
        hook.chmod(0o755)
    # git config values read backslashes as escapes, so the hostile values
    # are written the way a hostile repository would write them.
    sink_value = sink.as_posix()
    hooks_value = hooks.as_posix()
    config = repo / ".git" / "config"
    config.write_text(config.read_text(encoding="utf-8") + (
        "[core]\n"
        f"\thooksPath = {hooks_value}\n"
        f"\tfsmonitor = {sink_value}\n"
        "[filter \"evil\"]\n"
        f"\tsmudge = {sink_value}\n"
        f"\tclean = {sink_value}\n"
        "[alias]\n"
        f"\tstatus = {sink_value}\n"
        "[diff]\n"
        f"\texternal = {sink_value}\n"
        "[diff \"evil\"]\n"
        f"\ttextconv = {sink_value}\n"), encoding="utf-8")
    (repo / ".gitattributes").write_text("* filter=evil\n", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    (home / ".gitconfig").write_text(
        "[core]\n"
        f"\tfsmonitor = {sink_value}\n"
        "[alias]\n"
        f"\tstatus = {sink_value}\n"
        "[diff]\n"
        f"\texternal = {sink_value}\n", encoding="utf-8")


def test_hostile_repository_content_cannot_execute_or_move_the_output(tmp_path,
                                                                     monkeypatch):
    repo = weak_repo(tmp_path)
    before = miner.mine_history(repo, **IDENTITY)
    assert before, "the fixture must propose its weakening commit"
    plant_execution_sink(tmp_path, repo)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))

    real_run = subprocess.run
    seen = []

    def guarded(cmd, *args, **kwargs):
        assert cmd[0] == "git", f"non-git execution attempted: {cmd!r}"
        i = 1
        while i < len(cmd) and cmd[i] == "-c":
            i += 2
        seen.append(cmd[i])
        assert cmd[i] in PLUMBING, f"non-plumbing git command: {cmd!r}"
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", guarded)
    after = miner.mine_history(repo, **IDENTITY)
    assert after == before, "repository-supplied configuration moved the output"
    assert seen, "the miner reads history through git object reads"
    assert_untouched_outside(tmp_path)


def write_loose_object(repo, kind, data):
    """A loose git object written behind git's back.

    `hash-object` runs fsck and refuses hostile tree names, but objects
    fetched from a hostile remote can carry any name, so the fixture writes
    one directly -- exactly what the miner must survive.
    """
    body = kind.encode("ascii") + b" %d\x00" % len(data) + data
    sha = hashlib.sha1(body).hexdigest()
    path = repo / ".git" / "objects" / sha[:2] / sha[2:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(zlib.compress(body))
    return sha


def hostile_commit(repo, parent, name):
    """One commit whose tree names `name` -- any bytes git may store."""
    blob = git(repo, "hash-object", "-w", "--stdin",
               input=b"evil\n").stdout.strip()
    entries = b""
    for entry in git(repo, "ls-tree", parent).stdout.split(b"\0"):
        if not entry:
            continue
        meta, existing = entry.split(b"\t", 1)
        mode, _kind, oid = meta.split(b" ")
        entries += mode + b" " + existing + b"\x00" + bytes.fromhex(oid.decode())
    entries += b"100644 " + name + b"\x00" + bytes.fromhex(blob.decode())
    tree = write_loose_object(repo, "tree", entries)
    body = (b"tree " + tree.encode("ascii") + b"\nparent "
            + parent.encode("ascii")
            + b"\nauthor t <t@t> 1 +0000\ncommitter t <t@t> 1 +0000\n\n"
              b"hostile paths\n")
    return write_loose_object(repo, "commit", body)


@pytest.mark.parametrize("name,phrase", [
    (b"../evil.txt", "escapes the work tree"),
    (b"/etc/passwd", "is absolute"),
    (b"a\nb.txt", "contains control characters"),
    (b".git/hooks/pre-commit", ".git internals"),
])
def test_paths_escaping_the_work_tree_are_rejected_by_name(tmp_path, name, phrase):
    repo = weak_repo(tmp_path)
    parent = git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    hostile = hostile_commit(repo, parent, name)
    with pytest.raises(EvidenceError) as exc:
        miner.mine_history(repo, end=hostile, **IDENTITY)
    assert str(exc.value).startswith("files:"), exc.value
    assert phrase in str(exc.value), exc.value
    assert_untouched_outside(tmp_path)


def test_a_blob_above_the_size_bound_is_rejected_naming_the_bound(tmp_path):
    repo = weak_repo(tmp_path)
    padding = "# padding\n" * 200_000
    (repo / "tests" / "test_big.py").write_text(
        "def test_big():\n    assert 1 == 1\n" + padding, encoding="utf-8")
    commit(repo, "huge test")
    with pytest.raises(EvidenceError) as exc:
        miner.mine_history(repo, **IDENTITY)
    assert str(exc.value).startswith("files:"), exc.value
    assert "above the" in str(exc.value), exc.value


def test_the_commit_count_is_bounded_naming_the_field(tmp_path, monkeypatch):
    repo, _ = history_repo(tmp_path)
    monkeypatch.setattr(miner, "MAX_COMMITS", 2)
    with pytest.raises(EvidenceError) as exc:
        miner.mine_history(repo, **IDENTITY)
    assert str(exc.value).startswith("commits:"), exc.value


def test_the_changed_path_count_is_bounded_naming_the_field(tmp_path, monkeypatch):
    repo, _ = history_repo(tmp_path)
    monkeypatch.setattr(miner, "MAX_FILES", 1)
    with pytest.raises(EvidenceError) as exc:
        miner.mine_history(repo, **IDENTITY)
    assert str(exc.value).startswith("files:"), exc.value


# -- candidates are written unadjudicated and never gate inputs --------------

def test_candidates_are_written_unadjudicated_and_load_as_cases(tmp_path):
    repo, shas = history_repo(tmp_path)
    root = tmp_path / "corpus"
    root.mkdir()
    names = miner.write_candidates(root, miner.mine_history(repo, **IDENTITY))
    assert list(names) == [f"R1-{shas[key][:12]}.json"
                           for key in ("c2", "c3", "c4", "c5")]
    cases = corpus.load_corpus(root)
    assert {case.id for case in cases} == set(name[:-5] for name in names)
    for case in cases:
        assert case.adjudicated is None, \
            "a mined candidate is a proposal; adjudication is human work"
        assert case.labels is None


def test_a_mined_candidate_cannot_enter_a_gate_input(tmp_path):
    repo, _ = history_repo(tmp_path)
    candidate = miner.mine_history(repo, split="frozen", **IDENTITY)[0]
    with pytest.raises(EvidenceError) as exc:
        corpus.GateInputClass("positives", [candidate])
    assert "labels: unadjudicated" in str(exc.value), exc.value
    assert "labels" in str(exc.value), exc.value


def test_the_writer_refuses_a_record_carrying_a_labels_or_axes_block(tmp_path):
    repo, _ = history_repo(tmp_path)
    candidate = miner.mine_history(repo, **IDENTITY)[0]
    for field, block in (
            ("labels", {"labeler1": "tampered", "labeler2": "tampered",
                        "adjudicated": "tampered", "disagreement": False}),
            ("axes", {"a_mechanism": "skip added", "b_grade_relevance": "yes",
                      "c_pinned_evidence": "yes", "d_harm": "low"})):
        record = dict(candidate)
        record[field] = block
        with pytest.raises(EvidenceError) as exc:
            miner.write_candidates(tmp_path, [record])
        assert str(exc.value).startswith(field + ":") \
            or f"{field}:" in str(exc.value), exc.value
