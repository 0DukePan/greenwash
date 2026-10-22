"""Verifier integrity: the checker's own inputs, pinned outside the sandbox.

The diff under inspection is untrusted, and so is everything an agent can write
inside the working tree -- including the files the verifier reads to decide what
gets checked and what may pass. The contract asserted here:

- the checker, its config and the pinned original tests are hash-verified
  against their copies at the base ref before the run starts;
- a modified checker or config fails loudly before any verdict, with its own
  exit code, and never reads as a verdict about the diff;
- an edited pinned test is detected, and the run still pins the base copy;
- a scripted integrity suite attempts every one of those alterations from
  inside the sandbox and reports zero successful modifications.

Every test drives the public CLI seam against a real temporary repository.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash import cli  # noqa: E402

CHECK = ROOT / "scripts" / "greenwash_check.py"
PYTEST = f'"{sys.executable}" -m pytest -q'

CONFIG = '{"mode": "report", "test_integrity": true}\n'
GREEN = {
    "src/calc.py": "def add(a, b):\n    return a + b\n",
    "tests/test_calc.py": (
        "from src.calc import add\n\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n\n\n"
        "def test_add_negative():\n    assert add(-1, -1) == -2\n"
    ),
    ".greenwash/config.json": CONFIG,
}
# A repository that also carries its own copy of the checker (the self-check
# case: in CI the checker comes from the base ref of the repository it grades).
CHECKER_FILES = {
    "greenwash/__init__.py": "",
    "greenwash/guard.py": "# the checker's own integrity guard\n",
}
WEAKENED_TEST = "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
BROKEN_CALC = "def add(a, b):\n    return abs(a) + abs(b)\n"


def _git(tmp, *args):
    subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True, text=True)


def _write(tmp, rel, content):
    path = Path(tmp) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _repo(tmp, files=GREEN):
    _git(tmp, "init", "-q")
    for rel, content in files.items():
        _write(tmp, rel, content)
    _git(tmp, "add", "-A")
    _git(tmp, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")


def _run(monkeypatch, capsys, argv):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _sha(path) -> str:
    """The guard's digest: newline-normalised text (a checkout's CRLF
    translation is not a modification)."""
    data = Path(path).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _flat(text) -> str:
    """Whitespace-normalised text: report prose is word-wrapped on render."""
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# A modified checker, config or pinned test is detected before the run starts.
# ---------------------------------------------------------------------------

def test_a_modified_config_fails_loudly_before_any_verdict(tmp_path, monkeypatch, capsys):
    _repo(tmp_path)
    pinned = _sha(tmp_path / ".greenwash" / "config.json")
    _write(tmp_path, ".greenwash/config.json",
           '{"mode": "report", "ignore_rules": ["hardcoded-return"]}\n')
    monkeypatch.chdir(tmp_path)

    code, out, err = _run(monkeypatch, capsys, [])

    assert code == 4, out + err          # its own exit code, not 0/1/2/3
    assert "verifier integrity failure" in err
    assert "not a verdict about the diff" in err
    assert ".greenwash/config.json" in err
    assert pinned in err                 # the base copy is what was pinned
    assert "Verdict:" not in out and "GREENWASH TRUST REPORT" not in out


def test_a_modified_checker_fails_loudly_before_any_verdict(tmp_path, monkeypatch, capsys):
    _repo(tmp_path, {**GREEN, **CHECKER_FILES})
    _write(tmp_path, "greenwash/guard.py", "# neutered: always says clean\n")
    monkeypatch.chdir(tmp_path)

    code, out, err = _run(monkeypatch, capsys, [])

    assert code == 4, out + err
    assert "verifier integrity failure" in err
    assert "not a verdict about the diff" in err
    assert "greenwash/guard.py" in err
    assert "Verdict:" not in out and "GREENWASH TRUST REPORT" not in out


def test_a_modified_pinned_test_is_detected_before_the_run_starts(tmp_path, monkeypatch, capsys):
    _repo(tmp_path)
    pinned = _sha(tmp_path / "tests" / "test_calc.py")
    _write(tmp_path, "tests/test_calc.py", WEAKENED_TEST)
    monkeypatch.chdir(tmp_path)

    code, out, err = _run(monkeypatch, capsys, ["verify", "--run-tests", PYTEST])

    # a test edit is diff content for the verdict to judge, not a moved pin:
    # detected before the run starts, named, and pinned to the base copy
    assert "verifier integrity" in err
    assert "tests/test_calc.py" in err
    assert pinned in err
    assert _sha(tmp_path / "tests" / "test_calc.py") not in err
    assert code != 4        # judged as diff content, never refused as integrity


# ---------------------------------------------------------------------------
# Base-ref loading: the branch copy cannot become the evidence.
# ---------------------------------------------------------------------------

def test_the_pinned_original_tests_still_come_from_the_base_ref(tmp_path, monkeypatch, capsys):
    _repo(tmp_path)
    pinned_test = _sha(tmp_path / "tests" / "test_calc.py")
    _write(tmp_path, "src/calc.py", BROKEN_CALC)        # break the code ...
    _write(tmp_path, "tests/test_calc.py", WEAKENED_TEST)  # ... and fit the test to it
    monkeypatch.chdir(tmp_path)

    code, out, err = _run(monkeypatch, capsys, ["verify", "--run-tests", PYTEST])

    # what counts as evidence is the base copy: its digest, never the edited one
    shown = _flat(out)
    assert pinned_test in shown, out + err
    assert _sha(tmp_path / "tests" / "test_calc.py") not in shown
    assert "Verdict: VERIFIED" not in out


# ---------------------------------------------------------------------------
# Integrity failure has its own exit code and never reads as a verdict.
# ---------------------------------------------------------------------------

def test_integrity_failure_is_not_a_verdict_even_in_json(tmp_path, monkeypatch, capsys):
    _repo(tmp_path)
    _write(tmp_path, ".greenwash/config.json", '{"test_integrity": false}\n')
    monkeypatch.chdir(tmp_path)

    code, out, err = _run(monkeypatch, capsys, ["--json"])

    assert code == 4
    payload = json.loads(out)
    assert payload["integrity"] == "failure"
    assert "verdict" not in payload      # never a verdict about the diff
    assert any(".greenwash/config.json" in problem for problem in payload["problems"])
    assert "not a verdict about the diff" in payload["note"]


def test_the_ci_entry_point_refuses_with_the_same_code(tmp_path):
    """`scripts/greenwash_check.py` is what CI runs; the base ref is its pin."""
    _repo(tmp_path)
    _write(tmp_path, ".greenwash/config.json", '{"test_integrity": false}\n')

    result = subprocess.run([sys.executable, str(CHECK), "verify"], cwd=tmp_path,
                            capture_output=True, text=True,
                            encoding="utf-8", errors="replace")

    assert result.returncode == 4, result.stdout + result.stderr
    assert "verifier integrity failure" in result.stderr
    assert "not a verdict about the diff" in result.stderr
    assert result.stdout.strip() == ""   # no verification summary, no "clean"


# ---------------------------------------------------------------------------
# The scripted integrity suite: zero successful modifications.
# ---------------------------------------------------------------------------

FORGED_WAIVER = {"waivers": [{
    "id": "GW-WV-9999",
    "rule_id": "GW-TEST-002",
    "signal_fingerprint": "sha256:" + "0" * 64,
    "path": "src/calc.py",
    "reason": "looks fine to me",
    "reviewer": "@agent",
    "created_at": "2026-01-01T00:00:00+00:00",
    "expires_at": "2030-01-01T00:00:00+00:00",
}]}


def _mutate_config_lowered(repo):
    _write(repo, ".greenwash/config.json",
           '{"mode": "report", "ignore_rules": ["hardcoded-return"]}\n')


def _mutate_config_checks_off(repo):
    _write(repo, ".greenwash/config.json",
           '{"mode": "report", "test_integrity": false, "auto_verify": false}\n')


def _mutate_config_deleted(repo):
    (Path(repo) / ".greenwash" / "config.json").unlink()


def _mutate_checker_edited(repo):
    _write(repo, "greenwash/guard.py", "# neutered: always says clean\n")


def _mutate_checker_planted(repo):
    _write(repo, "greenwash/guard.py", "# a checker the diff introduced\n")


def _mutate_pinned_test_weakened(repo):
    _write(repo, "src/calc.py", BROKEN_CALC)
    _write(repo, "tests/test_calc.py", WEAKENED_TEST)


def _mutate_pinned_test_deleted(repo):
    _write(repo, "src/calc.py", BROKEN_CALC)
    (Path(repo) / "tests" / "test_calc.py").unlink()


def _mutate_waiver_forged(repo):
    _write(repo, "src/calc.py", "def add(a, b):\n    return 5\n")
    _write(repo, ".greenwash/waivers.json", json.dumps(FORGED_WAIVER) + "\n")


def _mutate_anchor_rewritten(repo):
    _write(repo, "src/calc.py", "def add(a, b):\n    return 5\n")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "cheat")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()
    _write(repo, ".git/greenwash/session-base", json.dumps({"base": head, "stash": ""}))


def _proceeded(code, out, err) -> bool:
    """The tampered policy was in force: the run went past the guard."""
    return code != 4


def _pin_moved_or_laundered(code, out, err) -> bool:
    """The edited working copy became the evidence, or the break read clean."""
    return ("pinned original at the base ref" not in _flat(out)
            or "Verdict: VERIFIED" in out)


def _finding_vanished(code, out, err) -> bool:
    return "hardcoded-return" not in out and "SUSPICIOUS" not in out


# Each attempt: what it alters, how it mutates the sandbox from the inside,
# and what would count as the attacker's success. The suite requires zero.
ATTEMPTS = [
    {"id": "config-lowered", "alters": "config", "mutate": _mutate_config_lowered,
     "wins": _proceeded},
    {"id": "config-checks-off", "alters": "config", "mutate": _mutate_config_checks_off,
     "wins": _proceeded},
    {"id": "config-deleted", "alters": "config", "mutate": _mutate_config_deleted,
     "wins": _proceeded},
    {"id": "checker-edited", "alters": "checker", "mutate": _mutate_checker_edited,
     "wins": _proceeded, "base_files": CHECKER_FILES},
    {"id": "checker-planted", "alters": "checker", "mutate": _mutate_checker_planted,
     "wins": _proceeded},
    {"id": "pinned-test-weakened", "alters": "checker inputs", "mutate": _mutate_pinned_test_weakened,
     "wins": _pin_moved_or_laundered, "argv": ["verify", "--run-tests", PYTEST]},
    {"id": "pinned-test-deleted", "alters": "checker inputs", "mutate": _mutate_pinned_test_deleted,
     "wins": _pin_moved_or_laundered, "argv": ["verify", "--run-tests", PYTEST]},
    {"id": "waiver-forged", "alters": "output", "mutate": _mutate_waiver_forged,
     "wins": _finding_vanished, "argv": ["scan"]},
    {"id": "anchor-rewritten", "alters": "output", "mutate": _mutate_anchor_rewritten,
     "wins": _finding_vanished, "argv": ["scan"], "prerun": True},
]


def test_the_integrity_suite_reports_zero_successful_modifications(tmp_path, monkeypatch, capsys):
    successes = []
    judged = []
    for attempt in ATTEMPTS:
        sandbox = tmp_path / attempt["id"]
        sandbox.mkdir()
        _repo(sandbox, {**GREEN, **attempt.get("base_files", {})})
        monkeypatch.chdir(sandbox)
        if attempt.get("prerun"):
            _run(monkeypatch, capsys, [])      # pin the session, as the hook does
            capsys.readouterr()
        attempt["mutate"](sandbox)
        code, out, err = _run(monkeypatch, capsys, attempt.get("argv", []))
        won = attempt["wins"](code, out, err)
        judged.append(attempt["id"])
        if won:
            successes.append(attempt["id"])

    assert len(judged) == len(ATTEMPTS)
    assert successes == [], (
        f"the integrity suite reports {len(successes)} successful modification(s): "
        f"{successes}")
