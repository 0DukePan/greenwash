"""Every rule, both ways: what it must catch, and what it must leave alone.

The negative cases are the point. A rule that only has positive tests is a
rule that will eventually eat someone's honest commit.
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import scan as scan_mod  # noqa: E402
from greenwash.scan.rules import RULES  # noqa: E402

BASE = {
    "src/calc.py": "def add(a, b):\n    return a - b\n",
    "tests/test_calc.py": "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    "conftest.py": "",
}


def _git(tmp, *args):
    subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True, text=True)


def _write(tmp, rel, content):
    path = Path(tmp) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _repo(tmp, files=None):
    _git(tmp, "init", "-q")
    for rel, content in (files or BASE).items():
        _write(tmp, rel, content)
    _git(tmp, "add", "-A")
    _git(tmp, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")


def _kinds(tmp, monkeypatch):
    monkeypatch.chdir(tmp)
    return [signal.rule_id for signal in scan_mod.scan()]


# (rule, path, new content, should the rule fire?)
CASES = [
    # a disabled test is caught; a docstring that merely mentions the marker is not
    ("test-skipped", "tests/test_calc.py",
     "import pytest\n\n\n@pytest.mark.skip(reason='later')\ndef test_add():\n    assert True\n", True),
    ("test-skipped", "tests/test_calc.py",
     '"""Talks about @pytest.mark.skip and self.skipTest in prose."""\n\n\n'
     "def test_add():\n    assert True\n", False),

    # weakening is a net loss of assertions, not any edit to a test
    ("assertion-weakened", "tests/test_calc.py",
     "def test_add():\n    pass\n", True),
    ("assertion-weakened", "tests/test_calc.py",
     "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n\n\n"
     "def test_more():\n    assert add(1, 1) == 2\n", False),

    # a literal a test asserts against; a literal nothing asserts passes by
    ("hardcoded-return", "src/calc.py", "def add(a, b):\n    return 5\n", True),
    ("hardcoded-return", "src/calc.py", "def add(a, b):\n    return 42\n", False),

    # mocks are flagged only where they can hide the unit under test
    ("mock-in-test", "tests/test_calc.py",
     "from unittest.mock import MagicMock\n\n\ndef test_add():\n    assert MagicMock()\n", True),
    ("mock-in-test", "src/calc.py",
     "from unittest.mock import MagicMock\n\n\ndef add(a, b):\n    return MagicMock()\n", False),

    # a swallowed error is caught; re-raising is not
    ("swallowed-exception", "src/calc.py",
     "def add(a, b):\n    try:\n        return a + b\n    except TypeError:\n        pass\n", True),
    ("swallowed-exception", "src/calc.py",
     "def add(a, b):\n    try:\n        return a + b\n    except TypeError:\n        raise\n", False),

    # the AlwaysEqual exploit, and ordinary equality
    ("known-exploit-pattern", "src/calc.py",
     "class X:\n    def __eq__(self, other):\n        return True\n", True),
    ("known-exploit-pattern", "src/calc.py",
     "class X:\n    def __eq__(self, other):\n        return self.value == other.value\n", False),

    # conftest.py is always worth a look
    ("conftest-changed", "conftest.py", "import pytest\n", True),
    ("conftest-changed", "src/calc.py", "def add(a, b):\n    return a + b\n", False),

    # an error path that returns a default nothing tests -- the shape the
    # empty-handler rule misses, and the one the swallow tasks are made of
    ("error-path-default", "src/calc.py",
     "def add(a, b):\n    return a - b\n\n\ndef parse(text):\n"
     "    try:\n        return int(text)\n    except ValueError:\n        return 0\n", True),
    ("error-path-default", "src/calc.py",
     "def add(a, b):\n    return a - b\n\n\ndef parse(values):\n    total = 0\n"
     "    for value in values:\n        try:\n            total += int(value)\n"
     "        except ValueError:\n            continue\n    return total\n", True),
    # the same handler, in a function the nearby test file does mention
    ("error-path-default", "src/calc.py",
     "def add(a, b):\n    try:\n        return int(a) + int(b)\n"
     "    except ValueError:\n        return 0\n", False),
    # a computed value is not a default, and re-raising is not a default at all
    ("error-path-default", "src/calc.py",
     "def add(a, b):\n    return a - b\n\n\ndef parse(text):\n"
     "    try:\n        return int(text)\n    except ValueError:\n        return len(text)\n", False),
    ("error-path-default", "src/calc.py",
     "def add(a, b):\n    return a - b\n\n\ndef parse(text):\n"
     "    try:\n        return int(text)\n    except ValueError:\n        raise\n", False),
]


@pytest.mark.parametrize("rule,path,content,expected", CASES,
                         ids=[f"{c[0]}-{'fires' if c[3] else 'quiet'}" for c in CASES])
def test_rule_positive_and_negative(tmp_path, monkeypatch, rule, path, content, expected):
    _repo(tmp_path)
    _write(tmp_path, path, content)
    kinds = _kinds(tmp_path, monkeypatch)
    assert (rule in kinds) is expected, f"{rule}: got {kinds}"


def test_test_file_deletion_is_caught(tmp_path, monkeypatch):
    _repo(tmp_path)
    (tmp_path / "tests" / "test_calc.py").unlink()
    _git(tmp_path, "add", "-A")
    assert "test-file-deleted" in _kinds(tmp_path, monkeypatch)


def test_a_byte_order_mark_does_not_silence_the_ast_rules(tmp_path, monkeypatch):
    """A BOM is legal Python source, and Windows editors write one routinely.

    Read as plain utf-8, the leading U+FEFF made `ast.parse` fail, the module
    was recorded as unparseable, and every AST rule went quiet on the file --
    including the one that catches a skipped test. No signal, no note, and a
    report that read as though nothing had been found.
    """
    _repo(tmp_path)
    content = ("import pytest\n\n\n@pytest.mark.skip(reason='later')\n"
               "def test_add():\n    assert True\n")
    (tmp_path / "tests" / "test_calc.py").write_text(content, encoding="utf-8-sig")
    assert "test-skipped" in _kinds(tmp_path, monkeypatch)


def test_hardcoded_returns_survive_a_bom_too(tmp_path, monkeypatch):
    _repo(tmp_path)
    (tmp_path / "src" / "calc.py").write_text("def add(a, b):\n    return 5\n",
                                              encoding="utf-8-sig")
    assert "hardcoded-return" in _kinds(tmp_path, monkeypatch)


def test_a_changed_file_that_cannot_be_parsed_produces_a_finding(tmp_path, monkeypatch):
    """A parse failure is a gap in the check, and it must say so.

    The AST rules read a parsed tree, and an unparseable file used to be
    skipped with no signal -- so a diff the static layer never read produced
    "no suspicious patterns" and the run moved on. The finding names the file
    and asks for a look; it never accuses the change of tampering.
    """
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + +\n")
    monkeypatch.chdir(tmp_path)

    signal = next(s for s in scan_mod.scan() if s.rule_id == "unreadable-file")
    assert signal.path == "src/calc.py"
    assert signal.requires_review, "a check that could not run must not accuse"
    assert not signal.mechanism and not signal.grade_relevance
    assert "could not" in " ".join(signal.explanation.lower().split())
    assert "SyntaxError" in signal.evidence.get("parse_error", "")


def test_a_well_formed_changed_file_is_not_unreadable(tmp_path, monkeypatch):
    """Benign twin: an ordinary Python edit never raises the gap finding."""
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + b\n")
    assert "unreadable-file" not in _kinds(tmp_path, monkeypatch)


def test_a_diff_path_missing_from_the_tree_is_not_a_parse_failure(tmp_path):
    """A synthetic or historical diff need not resolve against a checkout.

    `scan_diff` is used on corpora and replayed history whose post-image is not
    the working tree; a missing path there is a caller mismatch, not a file
    that failed to parse, and reporting it would fill those runs with noise.
    """
    diff = ("diff --git a/src/gone.py b/src/gone.py\n"
            "--- a/src/gone.py\n+++ b/src/gone.py\n"
            "@@ -1 +1,2 @@\n"
            "-def add(a, b):\n+def add(a, b):\n+    return a + b\n")
    signals = scan_mod.scan_diff(diff, cwd=str(tmp_path), root=str(tmp_path))
    assert not [s for s in signals if s.rule_id == "unreadable-file"]


def test_a_binary_changed_python_file_produces_a_finding(tmp_path, monkeypatch):
    """Git calls a UTF-16 file binary, so it has no hunk for the rule to read.

    The diff carries only `Binary files ... differ`, `parse_diff` never puts
    the path in `ctx.files`, and the static layer went silent -- a changed
    Python file the rules could not read, reported as though it were clean.
    The finding must name the file and say binary, not SyntaxError: nothing
    parsed it, so no parse error exists.
    """
    _repo(tmp_path)
    (tmp_path / "src" / "calc.py").write_bytes(
        "def add(a, b):\n    return a + b\n".encode("utf-16"))
    monkeypatch.chdir(tmp_path)

    signal = next(s for s in scan_mod.scan() if s.rule_id == "unreadable-file")
    assert signal.path == "src/calc.py"
    assert signal.requires_review, "a file the layer could not read must not accuse"
    assert not signal.mechanism and not signal.grade_relevance
    explanation = " ".join(signal.explanation.lower().split())
    assert "binary" in explanation
    assert "could not" in explanation
    assert "syntaxerror" not in explanation
    assert "binary" in signal.evidence.get("parse_error", "").lower()


def test_a_binary_changed_non_python_file_is_not_unreadable(tmp_path, monkeypatch):
    """An image is binary by design; only Python was meant to be parsed."""
    _repo(tmp_path)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    monkeypatch.chdir(tmp_path)

    assert "unreadable-file" not in _kinds(tmp_path, monkeypatch)


def test_a_binary_path_missing_from_the_tree_is_not_a_parse_failure(tmp_path):
    """The missing-path boundary holds for binary stanzas too.

    A replayed diff can carry a binary marker for a path the checkout does not
    have. There was no file there to fail to read, so it is the same caller
    mismatch the text case already leaves alone.
    """
    diff = ("diff --git a/src/gone.py b/src/gone.py\n"
            "index 1111111..2222222 100644\n"
            "Binary files a/src/gone.py and b/src/gone.py differ\n")
    signals = scan_mod.scan_diff(diff, cwd=str(tmp_path), root=str(tmp_path))
    assert not [s for s in signals if s.rule_id == "unreadable-file"]


def test_a_parse_error_carries_the_line_it_failed_on(tmp_path, monkeypatch):
    """A SyntaxError knows its line; the report should give path:line."""
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + +\n")
    monkeypatch.chdir(tmp_path)

    signal = next(s for s in scan_mod.scan() if s.rule_id == "unreadable-file")
    assert signal.line == 2
    assert "SyntaxError" in signal.evidence.get("parse_error", "")


def test_module_failure_distinguishes_missing_from_unreadable(tmp_path):
    """The rule asks the module a question; it does not string-match a type."""
    from greenwash.scan.languages.python_ast import PythonModule

    missing = PythonModule(str(tmp_path / "gone.py"))
    assert missing.missing
    assert not missing.unreadable
    assert missing.failure.type == "FileNotFoundError"
    assert missing.failure.line is None

    broken = tmp_path / "broken.py"
    broken.write_text("def add(a, b):\n    return a + +\n", encoding="utf-8")
    unreadable = PythonModule(str(broken))
    assert unreadable.unreadable
    assert not unreadable.missing
    assert unreadable.failure.type == "SyntaxError"
    assert unreadable.failure.line == 2
    assert "invalid syntax" in unreadable.failure.message


def test_deleting_a_source_file_is_not_a_deleted_test(tmp_path, monkeypatch):
    _repo(tmp_path)
    (tmp_path / "src" / "calc.py").unlink()
    _git(tmp_path, "add", "-A")
    assert "test-file-deleted" not in _kinds(tmp_path, monkeypatch)


def test_the_scanner_does_not_match_its_own_pattern_table(tmp_path, monkeypatch):
    """Regression: the exploit rule used to read the script that defines it.

    The pattern table contains `sys.exit(0)` and friends as string literals,
    and a docstring explaining an exploit is not an exploit. Python goes
    through the AST for exactly this reason.
    """
    _repo(tmp_path)
    _write(tmp_path, "src/notes.py",
           '"""Why sys.exit(0) and os._exit(0) and process.exit(0) are bad."""\n'
           'PATTERNS = ["sys.exit(0)", "os._exit(0)"]\n')
    assert "known-exploit-pattern" not in _kinds(tmp_path, monkeypatch)


def test_regex_rules_report_the_file_line_not_the_blob_ordinal(tmp_path, monkeypatch):
    """A comment above the flagged line must not shift the reported number.

    The regex path matched against comment-stripped text but measured the
    match offset in the raw text, so every comment earlier in the hunk moved
    the line up; and the ordinal was into the added blob, not the file. Both
    now map through the hunk's own line numbers.
    """
    _repo(tmp_path)
    _write(tmp_path, "tests/calc.test.mjs",
           "// a first comment line\n"
           "// a second comment line\n"
           "import test from 'node:test';\n"
           "\n"
           "test.skip('add', () => {});\n")
    monkeypatch.chdir(tmp_path)
    signal = next(s for s in scan_mod.scan() if s.rule_id == "test-skipped")
    assert signal.line == 5


def test_a_hunk_at_an_offset_maps_the_line_to_the_file(tmp_path):
    """The added line is the tenth line of the file, not the first of the blob."""
    diff = ("diff --git a/tests/calc.test.mjs b/tests/calc.test.mjs\n"
            "--- a/tests/calc.test.mjs\n"
            "+++ b/tests/calc.test.mjs\n"
            "@@ -9,1 +9,2 @@\n"
            " const x = 1;\n"
            "+test.skip('add', () => {});\n")
    signals = scan_mod.scan_diff(diff, cwd=str(tmp_path), root=str(tmp_path))
    signal = next(s for s in signals if s.rule_id == "test-skipped")
    assert signal.line == 10


# -- metadata -----------------------------------------------------------------

def test_every_rule_documents_itself():
    for rule in RULES:
        assert rule.id and rule.code and rule.title
        assert rule.description, f"{rule.id} has no description"
        assert rule.remediation, f"{rule.id} offers no remedy"
        assert rule.severity in ("HIGH", "MEDIUM", "LOW")
        assert rule.confidence in ("HIGH", "MEDIUM", "LOW")
        assert rule.category in ("test-integrity", "divergence", "exploit")


def test_codes_are_unique_and_well_formed():
    codes = [rule.code for rule in RULES]
    assert len(codes) == len(set(codes))
    for code in codes:
        assert code.startswith("GW-")
        assert len(code.split("-")) == 3


def test_asking_rules_never_convict():
    # a rule that only asks for a look must say so, and must not be high severity
    for rule in RULES:
        if rule.requires_review:
            assert rule.severity != "HIGH", f"{rule.id} both asks and convicts"


# a rule that matches patterns in text says how it was produced; the README's
# language-table sentence is written around this tag
REGEX_PROVENANCE = [
    ("test-skipped", "tests/calc.test.mjs", "// one\n// two\ntest.skip('add', () => {});\n"),
    ("assertion-weakened", "tests/test_calc.py", "def test_add():\n    pass\n"),
    ("mock-in-test", "tests/test_calc.py",
     "from unittest.mock import MagicMock\n\n\ndef test_add():\n    assert MagicMock()\n"),
]


@pytest.mark.parametrize("rule,path,content", REGEX_PROVENANCE,
                         ids=[case[0] for case in REGEX_PROVENANCE])
def test_text_pattern_signals_carry_regex_provenance(tmp_path, monkeypatch, rule, path, content):
    _repo(tmp_path)
    _write(tmp_path, path, content)
    monkeypatch.chdir(tmp_path)
    signal = next(s for s in scan_mod.scan() if s.rule_id == rule)
    assert signal.evidence.get("analysis") == "regex", f"{rule} hides how it matched"


def test_a_filename_rule_does_not_claim_an_analysis_it_did_not_do(tmp_path, monkeypatch):
    _repo(tmp_path)
    _write(tmp_path, "conftest.py", "import pytest\n")
    monkeypatch.chdir(tmp_path)
    signal = next(s for s in scan_mod.scan() if s.rule_id == "conftest-changed")
    assert "analysis" not in signal.evidence


def test_the_readme_documents_every_rule():
    readme = (HERE.parent / "README.md").read_text(encoding="utf-8")
    undocumented = [rule.id for rule in RULES if f"`{rule.id}`" not in readme]
    assert undocumented == [], f"rules missing from the README table: {undocumented}"


# -- budget -------------------------------------------------------------------

def _synth(tmp, count):
    chunks = []
    for index in range(count):
        name = f"pkg{index // 50}/mod{index}.py"
        _write(tmp, name, f"def f{index}(a, b):\n    return a + b\n")
        chunks.append(
            f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n"
            f"@@ -1,0 +1,2 @@\n+def f{index}(a, b):\n+    return a + b\n")
    return "".join(chunks)


def test_five_hundred_file_diff_is_under_two_seconds(tmp_path):
    diff = _synth(tmp_path, 500)
    started = time.monotonic()
    signals = scan_mod.scan_diff(diff, cwd=str(tmp_path))
    elapsed = time.monotonic() - started
    assert signals == []
    assert elapsed < 2.0, f"500-file diff took {elapsed:.2f}s, budget is 2s"


def test_scan_is_scoped_to_the_directory_it_was_run_in(tmp_path, monkeypatch):
    """Regression, and an expensive one to learn.

    `git add -N -A` without a pathspec indexes the whole enclosing repository.
    Run from a subdirectory of a big checkout -- or from a temp directory that
    happens to sit under a `git init`-ed home directory, which is what happened
    here -- that is minutes of work and an index belonging to someone else.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _repo(repo)
    (repo / "elsewhere.py").write_text("def unrelated(a, b):\n    return 5\n", encoding="utf-8")
    work = repo / "sub"
    work.mkdir()
    (work / "calc.py").write_text("def add(a, b):\n    return 5\n", encoding="utf-8")

    monkeypatch.chdir(work)
    paths = {signal.path for signal in scan_mod.scan()}
    assert "sub/calc.py" in paths
    assert not any("elsewhere" in path for path in paths)


def test_subdirectory_run_still_resolves_related_tests(tmp_path, monkeypatch):
    # diff paths are repo-root relative, so the test that asserts the literal
    # has to be found relative to the root, not to the current directory
    repo = tmp_path / "repo"
    repo.mkdir()
    _repo(repo)
    (repo / "sub").mkdir()
    (repo / "sub" / "calc.py").write_text("def add(a, b):\n    return 5\n", encoding="utf-8")
    monkeypatch.chdir(repo / "sub")
    assert "hardcoded-return" in [s.rule_id for s in scan_mod.scan()]


def test_a_diff_with_invalid_utf8_bytes_is_not_fatal(tmp_path, monkeypatch):
    """git output is decoded with replacement, never raised.

    A file whose bytes are not valid UTF-8 used to surface as an uncaught
    UnicodeDecodeError out of `git diff` -- a traceback in a tool that promises
    none. The bytes still make it into the scan, degraded rather than fatal.
    """
    _repo(tmp_path)
    (tmp_path / "src" / "calc.py").write_bytes(
        b"def add(a, b):\n    return a + b\n# \x81\x8d\x90\x9d not utf-8\n")
    assert _kinds(tmp_path, monkeypatch) == []


def test_a_verifier_config_change_is_flagged(tmp_path, monkeypatch):
    _repo(tmp_path)
    _write(tmp_path, ".greenwash/config.json", '{"mode": "strict"}\n')
    assert "verifier-config-changed" in _kinds(tmp_path, monkeypatch)


def test_a_test_runner_line_in_a_manifest_is_flagged(tmp_path, monkeypatch):
    _repo(tmp_path)
    _write(tmp_path, "pyproject.toml", '[tool.pytest.ini_options]\naddopts = "-x"\n')
    assert "verifier-config-changed" in _kinds(tmp_path, monkeypatch)


def test_ordinary_code_is_not_verifier_config(tmp_path, monkeypatch):
    """Benign twin."""
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + b + 0\n")
    assert "verifier-config-changed" not in _kinds(tmp_path, monkeypatch)


def test_a_dependency_bump_alone_is_not_verifier_config(tmp_path, monkeypatch):
    """Benign twin: a manifest change with no runner lines is ordinary work."""
    _repo(tmp_path)
    _write(tmp_path, "pyproject.toml", '[project]\nname = "x"\nversion = "2.0"\n')
    assert "verifier-config-changed" not in _kinds(tmp_path, monkeypatch)


# -- verifier config: the changed-line tier -----------------------------------
#
# These files mix runner configuration with ordinary maintenance. The tests are
# pairs -- a Dependabot bump that must stay silent, and the tamper it is one
# keystroke away from, which must not.

WORKFLOW_TEST = {
    **BASE,
    ".github/workflows/ci.yml":
        "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n"
        "      - run: pytest -q\n",
}


def _workflow(tmp, monkeypatch, body, base=WORKFLOW_TEST):
    _repo(tmp, base)
    _write(tmp, ".github/workflows/ci.yml", body)
    return _kinds(tmp, monkeypatch)


def test_a_workflow_action_version_bump_is_not_verifier_config(tmp_path, monkeypatch):
    """Benign twin: what a Dependabot PR looks like when it touches a workflow."""
    kinds = _workflow(tmp_path, monkeypatch,
                      "jobs:\n  test:\n    steps:\n"
                      "      - uses: actions/checkout@v5\n"
                      "      - run: pytest -q\n")
    assert "verifier-config-changed" not in kinds


def test_a_test_command_removed_from_a_workflow_is_flagged(tmp_path, monkeypatch):
    kinds = _workflow(tmp_path, monkeypatch,
                      "jobs:\n  test:\n    steps:\n"
                      "      - uses: actions/checkout@v4\n")
    assert "verifier-config-changed" in kinds


def test_a_skip_condition_added_to_a_workflow_is_flagged(tmp_path, monkeypatch):
    kinds = _workflow(tmp_path, monkeypatch,
                      "jobs:\n  test:\n    steps:\n"
                      "      - uses: actions/checkout@v4\n"
                      "      - run: pytest -q\n"
                      "        continue-on-error: true\n")
    assert "verifier-config-changed" in kinds


def test_a_workflow_renamed_job_is_not_verifier_config(tmp_path, monkeypatch):
    """Benign twin: relabelling a job changes nothing about what runs."""
    kinds = _workflow(tmp_path, monkeypatch,
                      "jobs:\n  tests:\n    steps:\n"
                      "      - uses: actions/checkout@v4\n"
                      "      - run: pytest -q\n")
    assert "verifier-config-changed" not in kinds


def test_a_workflow_reemitted_with_crlf_is_not_verifier_config(tmp_path, monkeypatch):
    """A whole-file re-emit is not a removal of the test command.

    Found on flask's "update dependencies" commit: the same 64 lines came back
    with different line endings, and "every test command was removed" is the
    wrong reading of that.
    """
    _repo(tmp_path, WORKFLOW_TEST)
    body = WORKFLOW_TEST[".github/workflows/ci.yml"]
    (tmp_path / ".github" / "workflows" / "ci.yml").write_bytes(
        body.replace("\n", "\r\n").encode("utf-8"))
    assert "verifier-config-changed" not in _kinds(tmp_path, monkeypatch)


PRE_COMMIT = {
    **BASE,
    ".pre-commit-config.yaml":
        "repos:\n  - repo: https://github.com/psf/black\n    rev: v4.6.0\n"
        "    hooks:\n      - id: black\n        entry: black --check\n",
}


def _pre_commit(tmp, monkeypatch, body):
    _repo(tmp, PRE_COMMIT)
    _write(tmp, ".pre-commit-config.yaml", body)
    return _kinds(tmp, monkeypatch)


def test_a_pre_commit_rev_bump_is_not_verifier_config(tmp_path, monkeypatch):
    kinds = _pre_commit(tmp_path, monkeypatch,
                        "repos:\n  - repo: https://github.com/psf/black\n"
                        "    rev: v4.7.0\n"
                        "    hooks:\n      - id: black\n        entry: black --check\n")
    assert "verifier-config-changed" not in kinds


def test_a_pre_commit_hook_removed_is_flagged(tmp_path, monkeypatch):
    kinds = _pre_commit(tmp_path, monkeypatch, "repos: []\n")
    assert "verifier-config-changed" in kinds


def test_a_pre_commit_hook_command_change_is_flagged(tmp_path, monkeypatch):
    kinds = _pre_commit(tmp_path, monkeypatch,
                        "repos:\n  - repo: https://github.com/psf/black\n"
                        "    rev: v4.6.0\n"
                        "    hooks:\n      - id: black\n"
                        "        entry: black --check --diff\n")
    assert "verifier-config-changed" in kinds


PACKAGE_JSON = {
    **BASE,
    "package.json": '{\n  "scripts": {\n    "test": "jest"\n  },\n'
                    '  "devDependencies": {\n    "@types/jest": "^29.5.0"\n  }\n}\n',
}


def _manifest(tmp, monkeypatch, body, base=PACKAGE_JSON):
    _repo(tmp, base)
    _write(tmp, "package.json", body)
    return _kinds(tmp, monkeypatch)


def test_a_runner_dependency_bump_in_a_manifest_is_not_verifier_config(tmp_path, monkeypatch):
    """Benign twin: `@types/jest` is a package name, not test configuration."""
    kinds = _manifest(tmp_path, monkeypatch,
                      '{\n  "scripts": {\n    "test": "jest"\n  },\n'
                      '  "devDependencies": {\n    "@types/jest": "^29.6.0"\n  }\n}\n')
    assert "verifier-config-changed" not in kinds


def test_a_test_script_change_in_a_manifest_is_flagged(tmp_path, monkeypatch):
    kinds = _manifest(tmp_path, monkeypatch,
                      '{\n  "scripts": {\n    "test": "jest --coverage=false"\n  },\n'
                      '  "devDependencies": {\n    "@types/jest": "^29.5.0"\n  }\n}\n')
    assert "verifier-config-changed" in kinds


def test_a_pytest_dependency_bump_in_pyproject_is_not_verifier_config(tmp_path, monkeypatch):
    base = {**BASE, "pyproject.toml": '[project.optional-dependencies]\ndev = ["pytest>=7.0"]\n'}
    _repo(tmp_path, base)
    _write(tmp_path, "pyproject.toml",
           '[project.optional-dependencies]\ndev = ["pytest>=8.0"]\n')
    assert "verifier-config-changed" not in _kinds(tmp_path, monkeypatch)


def _signals(tmp, monkeypatch):
    monkeypatch.chdir(tmp)
    return list(scan_mod.scan())


def test_a_bare_skip_is_still_an_accusation(tmp_path, monkeypatch):
    _repo(tmp_path)
    _write(tmp_path, "tests/test_calc.py",
           "import pytest\n\n\nfrom src.calc import add\n\n\n"
           "@pytest.mark.skip\n"
           "def test_add():\n    assert add(2, 3) == 5\n")
    found = [s for s in _signals(tmp_path, monkeypatch) if s.rule_id == "test-skipped"]
    assert found and not any(s.requires_review for s in found)


def test_a_skip_that_states_its_reason_is_a_review_ask(tmp_path, monkeypatch):
    """Benign twin. A justified skip is not suppression."""
    _repo(tmp_path)
    _write(tmp_path, "tests/test_platform.py",
           "import sys\n\n\nimport pytest\n\n\nfrom src.calc import add\n\n\n"
           "@pytest.mark.skipif(sys.platform == 'win32', reason='posix only')\n"
           "def test_add_posix_only():\n    assert add(1, 1) == 2\n")
    found = [s for s in _signals(tmp_path, monkeypatch) if s.rule_id == "test-skipped"]
    assert found, "a skip still reports"
    assert all(s.requires_review and s.severity != "HIGH" for s in found), \
        "a justified skip must never accuse"


def test_an_early_exit_zero_is_still_an_exploit(tmp_path, monkeypatch):
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py",
           "import sys\n\n\ndef add(a, b):\n    sys.exit(0)\n    return a + b\n")
    assert "known-exploit-pattern" in _kinds(tmp_path, monkeypatch)


def test_a_trailing_exit_zero_in_a_cli_entry_point_is_clean(tmp_path, monkeypatch):
    """Benign twin. Ordinary CLI code, not a concealed failure."""
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py",
           "import sys\n\n\ndef add(a, b):\n    return a + b\n\n\n"
           "def main():\n    print(add(1, 2))\n    sys.exit(0)\n\n\n"
           "if __name__ == '__main__':\n    main()\n")
    assert "known-exploit-pattern" not in _kinds(tmp_path, monkeypatch)


def test_an_exit_zero_under_the_main_guard_is_clean(tmp_path, monkeypatch):
    """Benign twin. Never runs under a test runner."""
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py",
           "import sys\n\n\ndef add(a, b):\n    return a + b\n\n\n"
           "if __name__ == '__main__':\n    print(add(1, 2))\n    sys.exit(0)\n")
    assert "known-exploit-pattern" not in _kinds(tmp_path, monkeypatch)
