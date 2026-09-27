"""The strict profile: the decision table, the exit codes, and the hook flows.

Strict mode is the profile the Claude and Codex plugins run, so what it does
when it is wrong matters more than what it does when it is right. Two lines get
their own tests here:

* **evidence is not waivable** -- a waiver excuses a pattern, never a held-out
  suite that failed;
* **suppression is not a waiver** -- `ignore_rules` is refused rather than
  honoured, and the findings it was hiding stay in the report.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash import strict, waivers  # noqa: E402
from greenwash.domain import (Outcome, Signal, TrustReport, VerificationResult,  # noqa: E402
                              Verdict)

HOOK = ROOT / "scripts" / "greenwash_hook.py"
CODEX_HOOK = ROOT / "codex" / "scripts" / "greenwash_hook.py"

BASE = {
    "src/calc.py": "def add(a, b):\n    return a - b\n",
    "tests/test_calc.py": "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    "conftest.py": "",
}


def review_signal(path="src/loan.py", code="GW-DIV-002"):
    return Signal(rule_id="error-path-default", code=code, title="Error path returns a default",
                  severity="MEDIUM", confidence="MEDIUM", requires_review=True,
                  files=[path], line=12, evidence={"function": "load"})


def strong_signal(path="src/calc.py"):
    return Signal(rule_id="hardcoded-return", code="GW-TEST-004", title="Hardcoded return",
                  severity="HIGH", confidence="MEDIUM", files=[path], line=2,
                  evidence={"literal": "5"})


def verification(outcome=Outcome.PASS.value, heldout=Outcome.NOT_REQUESTED.value):
    return VerificationResult(test_command="pytest -q", outcome=outcome,
                              tests_run=1, tests_passed=1, heldout=heldout)


# ---- the decision table ------------------------------------------------------

@pytest.mark.parametrize("verdict,expected_exit", [
    (Verdict.VERIFIED.value, 0),
    (Verdict.PARTIALLY_VERIFIED.value, 0),
    (Verdict.INCONCLUSIVE.value, 0),
    (Verdict.NOT_VERIFIED.value, 1),
    (Verdict.SUSPICIOUS.value, 2),
    (Verdict.VERIFICATION_FAILED.value, 3),
])
def test_each_verdict_keeps_its_own_exit_code(verdict, expected_exit):
    """The same codes as --enforce: evidence (1), a pattern (2), a broken check (3)."""
    report = TrustReport(verdict=verdict, verification=verification())
    assert strict.decide(report).exit_code == expected_exit


def test_a_clean_report_is_allowed():
    report = TrustReport(verdict=Verdict.VERIFIED.value, verification=verification())
    gate = strict.decide(report)
    assert gate.blocked is False and gate.state == strict.ALLOWED


def test_inconclusive_is_allowed_but_says_nothing_was_verified():
    report = TrustReport(verdict=Verdict.INCONCLUSIVE.value,
                         verification=VerificationResult())
    gate = strict.decide(report)
    assert gate.blocked is False
    assert any("no behavioral check ran" in notice for notice in gate.notices)


def test_a_review_finding_blocks_until_it_is_decided():
    report = TrustReport(verdict=Verdict.PARTIALLY_VERIFIED.value,
                         signals=[review_signal()], verification=verification())
    gate = strict.decide(report)
    assert gate.blocked is True and gate.exit_code == 2
    assert "need a decision" in gate.reasons[0]


def test_a_waived_review_finding_is_allowed_and_still_visible():
    signal = review_signal()
    signal.waiver = {"id": "GW-2026-0001", "reviewer": "@maintainer",
                     "expires_at": "2026-10-20", "status": waivers.ACTIVE}
    row = waivers.Row(waiver=waivers.Waiver(
        id="GW-2026-0001", rule_id="GW-DIV-002", path="src/loan.py",
        signal_fingerprint="sha256:" + "0" * 64,
        reason="the fallback is documented and an integration test covers it",
        reviewer="@maintainer", created_at="2026-09-25", expires_at="2026-10-20"),
        status=waivers.ACTIVE, note="waived with review")
    report = TrustReport(verdict=Verdict.PARTIALLY_VERIFIED.value, signals=[signal],
                         verification=verification())
    gate = strict.decide(report, [row])
    assert gate.blocked is False
    assert gate.waived, "a waived finding is reported, never dropped"
    assert any("waived with review" in notice for notice in gate.notices)


def test_evidence_is_not_waivable():
    """A signature does not change what the held-out suite did."""
    signal = Signal(rule_id="heldout-failed", code="GW-VER-002", severity="HIGH",
                    files=["src/calc.py"])
    signal.waiver = {"id": "GW-2026-0001", "reviewer": "@maintainer",
                     "status": waivers.ACTIVE}
    report = TrustReport(verdict=Verdict.NOT_VERIFIED.value, signals=[signal],
                         verification=verification(heldout=Outcome.FAIL.value))
    gate = strict.decide(report)
    assert gate.blocked is True and gate.exit_code == 1
    assert "not something a waiver can excuse" in gate.reasons[0]


def test_a_harness_error_blocks_with_the_could_not_check_code():
    report = TrustReport(verdict=Verdict.VERIFICATION_FAILED.value,
                         verification=VerificationResult(harness_error="python not found"))
    gate = strict.decide(report)
    assert gate.exit_code == 3 and "could not complete" in gate.reasons[0]


def test_ignore_rules_is_refused_rather_than_honoured():
    report = TrustReport(verdict=Verdict.PARTIALLY_VERIFIED.value,
                         verification=verification())
    gate = strict.decide(report, ignored_rules=["mock-in-test", "swallowed-exception"])
    assert gate.blocked is True and gate.exit_code == 3
    assert "rejects broad rule suppression" in gate.reasons[0]
    assert "mock-in-test" in gate.reasons[0]


def test_a_lapsed_waiver_blocks():
    lapsed = waivers.Row(waiver=waivers.Waiver(
        id="GW-2026-0002", rule_id="GW-DIV-002", path="src/loan.py",
        signal_fingerprint="sha256:" + "0" * 64, reason="a long enough reason to count",
        reviewer="@maintainer", created_at="2026-08-01", expires_at="2026-08-31"),
        status=waivers.EXPIRED, note="waiver expired")
    report = TrustReport(verdict=Verdict.PARTIALLY_VERIFIED.value, verification=verification())
    gate = strict.decide(report, [lapsed])
    assert gate.blocked is True and gate.exit_code == 2


def test_an_unreadable_ledger_blocks():
    report = TrustReport(verdict=Verdict.VERIFIED.value, verification=verification())
    gate = strict.decide(report, ledger_problems=["could not read .greenwash/waivers.json"])
    assert gate.exit_code == 3 and "ledger could not be read" in gate.reasons[0]


# ---- through the CLI ---------------------------------------------------------

def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def cli(cwd, *args, env=None):
    environment = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8",
                   **(env or {})}
    return subprocess.run([sys.executable, "-m", "greenwash", *args], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=environment)


@pytest.fixture()
def cheat(tmp_path):
    git(tmp_path, "init", "-q")
    for rel, text in BASE.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")
    (tmp_path / "src" / "calc.py").write_text("def add(a, b):\n    return 5\n", encoding="utf-8")
    return tmp_path


def test_strict_blocks_a_faked_pass_where_report_mode_does_not(cheat):
    """Same diff, same findings: the only difference is who reads them."""
    reported = cli(cheat, "scan", "--no-color")
    assert reported.returncode == 1, "the scan subcommand reports findings, it does not gate"
    assert "Strict gate" not in reported.stdout

    blocked = cli(cheat, "scan", "--strict", "--no-color")
    assert blocked.returncode == 2
    assert "Strict gate:" in blocked.stdout
    assert "blocked" in blocked.stdout


def test_the_same_finding_passes_once_it_is_waived(cheat):
    waived = cli(cheat, "waive", "--rule", "hardcoded-return", "--path", "src/calc.py",
                 "--reason", "the constant is the documented answer for this fixture",
                 "--reviewer", "@maintainer", "--expires", "2026-10-20")
    assert waived.returncode == 0, waived.stderr

    result = cli(cheat, "scan", "--strict", "--no-color")
    assert result.returncode == 0, result.stderr
    assert "waived with review" in result.stdout
    assert "SUSPICIOUS" in result.stdout, "waived is a decision, not a clean verdict"


def test_expiring_the_waiver_restores_the_block(cheat):
    cli(cheat, "waive", "--rule", "hardcoded-return", "--path", "src/calc.py",
        "--reason", "the constant is the documented answer for this fixture",
        "--reviewer", "@maintainer", "--expires", "2026-10-20")
    store = cheat / ".greenwash" / "waivers.json"
    data = json.loads(store.read_text(encoding="utf-8"))
    # a waiver that was valid when written and lapsed since -- the ordinary way
    # one expires, as opposed to the nonsense entry the next test covers
    data["waivers"][0]["created_at"] = "2026-08-01T00:00:00+00:00"
    data["waivers"][0]["expires_at"] = "2026-08-31T00:00:00+00:00"
    store.write_text(json.dumps(data), encoding="utf-8")

    result = cli(cheat, "scan", "--strict", "--no-color")
    assert result.returncode == 2, result.stdout
    assert "expired" in result.stdout
    assert "unwaived again" in result.stdout


def test_a_waiver_that_lapsed_before_it_was_written_is_malformed(cheat):
    """Nonsense dates cannot be read as a lapsed decision -- they are not a decision."""
    cli(cheat, "waive", "--rule", "hardcoded-return", "--path", "src/calc.py",
        "--reason", "the constant is the documented answer for this fixture",
        "--reviewer", "@maintainer", "--expires", "2026-10-20")
    store = cheat / ".greenwash" / "waivers.json"
    data = json.loads(store.read_text(encoding="utf-8"))
    data["waivers"][0]["expires_at"] = "2026-09-01"
    store.write_text(json.dumps(data), encoding="utf-8")

    result = cli(cheat, "scan", "--strict", "--no-color")
    assert result.returncode == 3
    assert "cannot be honoured" in result.stdout


def test_config_mode_strict_is_the_same_gate(cheat):
    (cheat / ".greenwash").mkdir()
    (cheat / ".greenwash" / "config.json").write_text(
        json.dumps({"mode": "strict"}), encoding="utf-8")
    result = cli(cheat, "scan", "--no-color")
    assert result.returncode == 2
    assert "Strict gate:" in result.stdout


def test_strict_refuses_ignore_rules_and_shows_what_they_hid(cheat, tmp_path):
    (cheat / ".greenwash").mkdir()
    (cheat / ".greenwash" / "config.json").write_text(
        json.dumps({"mode": "strict", "ignore_rules": ["hardcoded-return"]}),
        encoding="utf-8")
    result = cli(cheat, "scan", "--no-color")
    assert result.returncode == 3
    assert "[hardcoded-return]" in result.stdout, "the finding stays visible"
    assert "rejects broad rule suppression" in result.stdout


def test_report_mode_still_honours_ignore_rules_and_names_them(cheat):
    (cheat / ".greenwash").mkdir()
    (cheat / ".greenwash" / "config.json").write_text(
        json.dumps({"ignore_rules": ["hardcoded-return"]}), encoding="utf-8")
    result = cli(cheat, "scan", "--no-color")
    assert result.returncode == 0
    assert "suppressed by config.ignore_rules: hardcoded-return" in result.stdout


def test_strict_takes_precedence_over_fail_on_and_says_so(cheat):
    result = cli(cheat, "scan", "--strict", "--fail-on", "not_verified", "--no-color")
    assert result.returncode == 2, result.stderr
    assert "--fail-on was given alongside a strict profile" in result.stdout


def test_the_gate_is_in_the_json(tmp_path):
    report = TrustReport(verdict=Verdict.SUSPICIOUS.value, verification=verification())
    payload = strict.decide(report).to_dict()
    assert payload["state"] == "blocked"
    assert payload["exit_code"] == 2
    assert payload["reasons"] and payload["summary"]


def test_doctor_describes_the_profile_it_is_actually_running(cheat):
    """Strict blocks on more than block_on; a doctor line that said otherwise
    would be a confident description of a policy the tool does not run."""
    (cheat / ".greenwash").mkdir()
    (cheat / ".greenwash" / "config.json").write_text(
        json.dumps({"mode": "strict"}), encoding="utf-8")
    cli(cheat, "waive", "--rule", "hardcoded-return", "--path", "src/calc.py",
        "--reason", "the constant is the documented answer for this fixture",
        "--reviewer", "@maintainer", "--expires", "2026-10-20")

    result = cli(cheat, "doctor")
    assert result.returncode == 0, result.stderr
    assert "strict --" in result.stdout
    assert "ignore_rules is refused" in result.stdout
    assert "waiver ledger" in result.stdout
    assert "1 entry" in result.stdout


def test_doctor_flags_a_ledger_it_cannot_read(cheat):
    (cheat / ".greenwash").mkdir()
    (cheat / ".greenwash" / "waivers.json").write_text("{not json", encoding="utf-8")
    result = cli(cheat, "doctor")
    assert result.returncode == 1, result.stdout
    assert "waiver ledger" in result.stdout
    assert "could not read" in result.stdout


# ---- the two stop gates: same policy, same verdict ---------------------------

def stop(hook, cwd, payload=None, env=None):
    environment = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8",
                   **(env or {})}
    return subprocess.run([sys.executable, str(hook)], cwd=cwd,
                          input=json.dumps(payload or {"hook_event_name": "Stop"}),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=environment, timeout=300)


@pytest.mark.parametrize("hook", [HOOK, CODEX_HOOK], ids=["claude", "codex"])
def test_strict_hook_blocks_a_faked_pass(cheat, hook):
    result = stop(hook, cheat, env={"GREENWASH_STRICT": "1"})
    assert result.returncode == 2, (result.stdout, result.stderr)
    combined = result.stdout + result.stderr
    assert "hardcoded-return" in combined
    assert "blocked" in combined.lower()


@pytest.mark.parametrize("hook", [HOOK, CODEX_HOOK], ids=["claude", "codex"])
def test_strict_hook_allows_a_clean_tree(cheat, hook):
    (cheat / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n",
                                           encoding="utf-8")
    result = stop(hook, cheat, env={"GREENWASH_STRICT": "1"})
    assert result.returncode == 0, (result.stdout, result.stderr)


@pytest.mark.parametrize("hook", [HOOK, CODEX_HOOK], ids=["claude", "codex"])
def test_strict_hook_allows_a_waived_finding_and_still_reports_it(cheat, hook):
    cli(cheat, "waive", "--rule", "hardcoded-return", "--path", "src/calc.py",
        "--reason", "the constant is the documented answer for this fixture",
        "--reviewer", "@maintainer", "--expires", "2026-10-20")
    result = stop(hook, cheat, env={"GREENWASH_STRICT": "1"})
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "waiv" in (result.stdout + result.stderr).lower()


@pytest.mark.parametrize("hook", [HOOK, CODEX_HOOK], ids=["claude", "codex"])
def test_a_broken_checker_never_blocks(tmp_path, hook):
    """Uncertainty is printed; the developer is not locked out of their own repo."""
    tmp_path.joinpath("notes.txt").write_text("not a repository\n", encoding="utf-8")
    result = stop(hook, tmp_path, env={"GREENWASH_STRICT": "1"})
    assert result.returncode == 0
    combined = (result.stdout + result.stderr).lower()
    assert "could not" in combined
