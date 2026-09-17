"""The CLI contract: what it prints, and what it refuses to do.

Exit codes are load-bearing -- a CI job and a pre-commit hook both turn on them
-- so they are asserted here rather than assumed.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import cli  # noqa: E402
from greenwash.domain import TrustReport, Verdict  # noqa: E402

BASE = {
    "src/calc.py": "def add(a, b):\n    return a - b\n",
    "tests/test_calc.py": "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
}


def _git(tmp, *args):
    subprocess.run(["git", *args], cwd=tmp, check=True, capture_output=True, text=True)


def _write(tmp, rel, content):
    path = Path(tmp) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _repo(tmp):
    _git(tmp, "init", "-q")
    for rel, content in BASE.items():
        _write(tmp, rel, content)
    _git(tmp, "add", "-A")
    _git(tmp, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")


def _run(monkeypatch, capsys, argv):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.fixture()
def cheat(tmp_path, monkeypatch):
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return 5\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_report_is_the_default_and_never_blocks(cheat, monkeypatch, capsys):
    code, out, err = _run(monkeypatch, capsys, [])
    assert code == 0, err
    assert "GREENWASH TRUST REPORT" in out
    assert "SUSPICIOUS" in out            # signals, no behavioral check
    assert "[hardcoded-return]" in out


def test_enforce_mode_blocks_on_suspicion(cheat, monkeypatch, capsys):
    code, _, err = _run(monkeypatch, capsys, ["--enforce"])
    assert code == 2, err


# (verdict, enforce-mode exit code) -- the contract in cli.py's docstring.
ENFORCED = [
    (Verdict.VERIFIED.value, 0),
    (Verdict.PARTIALLY_VERIFIED.value, 0),
    (Verdict.INCONCLUSIVE.value, 0),
    (Verdict.NOT_VERIFIED.value, 1),
    (Verdict.SUSPICIOUS.value, 2),
    (Verdict.VERIFICATION_FAILED.value, 3),
]


@pytest.mark.parametrize("verdict,expected", ENFORCED, ids=[v for v, _ in ENFORCED])
def test_enforce_exit_code_per_verdict(tmp_path, verdict, expected):
    """Evidence (1), a pattern (2), and a check that could not run (3) are three
    different codes.

    `NOT_VERIFIED` used to exit 2 -- the suspicious code -- so a held-out suite
    that actually failed was indistinguishable from a diff that merely looked
    wrong, which is the distinction the whole tool sells.
    """
    report = TrustReport(verdict=verdict)
    assert cli._enforced_exit(report, cli.config_mod.load(str(tmp_path))) == expected


def test_enforce_mode_with_evidence_exits_one(cheat, monkeypatch, capsys):
    _write(cheat, "tests/heldout.py", "from src.calc import add\n\n\ndef test_hidden():\n"
                                      "    assert add(10, -3) == 7\n")
    code, out, err = _run(monkeypatch, capsys, [
        "--enforce",
        "--run-tests", f'"{sys.executable}" -m pytest -q tests/test_calc.py',
        "--heldout", "tests/heldout.py"])
    assert code == 1, err
    assert "NOT_VERIFIED" in out


def test_scan_subcommand_exits_nonzero_on_findings(cheat, monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, ["scan"])
    assert code == 1
    assert "hardcoded-return" in out


def test_scan_subcommand_is_clean_when_it_should_be(tmp_path, monkeypatch, capsys):
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + b\n")
    monkeypatch.chdir(tmp_path)
    code, out, _ = _run(monkeypatch, capsys, ["scan"])
    assert code == 0
    # Nothing suspicious, but nothing was verified either: the report says so
    # rather than claiming the work is verified.
    assert "Verdict: INCONCLUSIVE" in out
    assert "None detected" in out


def test_output_is_not_colourised_when_it_is_not_a_terminal(cheat, monkeypatch, capsys):
    """Piped output is for files and CI logs, not for a TTY."""
    _, out, _ = _run(monkeypatch, capsys, [])
    assert "\033[" not in out


def test_colour_can_be_forced(cheat, monkeypatch, capsys):
    _, out, _ = _run(monkeypatch, capsys, ["--color"])
    assert "\033[" in out


def test_json_output_is_the_versioned_report(cheat, monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, ["--json"])
    payload = json.loads(out)
    assert payload["schema_version"] == "1"
    assert payload["verdict"] == "SUSPICIOUS"
    assert code == 0


def test_markdown_output(cheat, monkeypatch, capsys):
    _, out, _ = _run(monkeypatch, capsys, ["--format", "markdown"])
    assert out.startswith("## Greenwash trust report")


def test_verify_with_a_heldout_failure_is_not_verified(cheat, monkeypatch, capsys):
    _write(cheat, "tests/heldout.py", "from src.calc import add\n\n\ndef test_hidden():\n"
                                      "    assert add(10, -3) == 7\n")
    code, out, err = _run(monkeypatch, capsys, [
        "verify", "--run-tests", f'"{sys.executable}" -m pytest -q tests/test_calc.py',
        "--heldout", "tests/heldout.py"])
    assert code == 1, err
    assert "NOT_VERIFIED" in out
    assert "Observed:" in out


def test_an_unusable_repository_exits_three_with_a_clear_message(tmp_path, monkeypatch, capsys):
    # Not a repository, or one with no commits: exit 3 with one readable line,
    # never a traceback and never a report built out of nothing.
    monkeypatch.chdir(tmp_path)
    code, out, err = _run(monkeypatch, capsys, [])
    assert code == 3
    assert err.startswith("greenwash: ")
    assert "Traceback" not in err
    assert out == ""


def test_a_repository_with_no_commits_says_so(tmp_path, monkeypatch, capsys):
    _git(tmp_path, "init", "-q")
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + b\n")
    monkeypatch.chdir(tmp_path)
    code, _, err = _run(monkeypatch, capsys, [])
    assert code == 3
    assert "no commits" in err


def test_config_can_turn_on_enforcement(cheat, monkeypatch, capsys):
    (cheat / ".greenwash").mkdir()
    (cheat / ".greenwash" / "config.json").write_text(
        json.dumps({"mode": "enforce"}), encoding="utf-8")
    code, out, _ = _run(monkeypatch, capsys, [])
    assert code == 2
    assert "GREENWASH TRUST REPORT" in out


def test_zero_config_runs_the_behavioral_layer(cheat, monkeypatch, capsys):
    """No flags, no config: the tests are discovered and compared to HEAD."""
    code, out, _ = _run(monkeypatch, capsys, [])
    assert code == 0
    assert "detected pytest from" in out
    assert "Visible tests" in out


def test_an_explicit_command_turns_discovery_off(cheat, monkeypatch, capsys):
    _, out, _ = _run(monkeypatch, capsys, [
        "--run-tests", f'"{sys.executable}" -m pytest -q tests/test_calc.py'])
    assert "using the test command you supplied" in out
    assert "detected pytest" not in out


def test_config_can_opt_out_of_the_behavioral_layer(cheat, monkeypatch, capsys):
    (cheat / ".greenwash").mkdir()
    (cheat / ".greenwash" / "config.json").write_text(
        json.dumps({"auto_verify": False}), encoding="utf-8")
    code, out, _ = _run(monkeypatch, capsys, [])
    assert code == 0
    assert "detected pytest" not in out


def test_rules_lists_every_rule(cheat, monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, ["rules"])
    assert code == 0
    assert "GW-TEST-001" in out and "GW-VER-002" not in out
    assert "hardcoded-return" in out


def test_doctor_runs_and_explains(cheat, monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, ["doctor"])
    assert code == 0
    assert "git repository" in out
    assert "mode" in out


def test_init_writes_a_config(cheat, monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, ["init"])
    assert code == 0
    assert (cheat / ".greenwash" / "config.json").is_file()
    assert "report mode is on" in out
