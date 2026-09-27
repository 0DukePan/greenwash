"""Waivers: parsing, fingerprints, expiry, reviewers, paths, rules.

A waiver is the one thing in this tool that lets a blocked turn through, so
every property that makes it auditable has a test here: the digest moves when
the finding moves, the fields are all required, the lifetime is capped, and a
lapsed decision lapses. The point of each case is that the *quiet* failure --
a waiver that silently stops applying and is read as "nothing to declare" --
cannot happen.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash import waivers  # noqa: E402
from greenwash.domain import Signal  # noqa: E402

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


def signal(line=2, literal="5", path="src/calc.py", code="GW-TEST-004"):
    return Signal(rule_id="hardcoded-return", code=code, title="Hardcoded return",
                  category="test-integrity", severity="HIGH", confidence="MEDIUM",
                  explanation="returns literal 5 (directly), which a test asserts against",
                  files=[path], line=line, evidence={"literal": literal, "analysis": "ast"})


def waiver(**overrides):
    values = {
        "id": "GW-2026-0001",
        "rule_id": "GW-TEST-004",
        "signal_fingerprint": waivers.fingerprint(signal()),
        "path": "src/calc.py",
        "reason": "the constant is the documented answer for this fixture",
        "reviewer": "@maintainer",
        "created_at": waivers.iso(NOW),
        "expires_at": waivers.iso(NOW + timedelta(days=10)),
    }
    values.update(overrides)
    return waivers.Waiver(**values)


def ledger_of(*entries):
    return waivers.Ledger(path=".greenwash/waivers.json", waivers=list(entries))


# ---- the fingerprint ---------------------------------------------------------

def test_fingerprint_is_stable_for_the_same_finding():
    assert waivers.fingerprint(signal()) == waivers.fingerprint(signal())


def test_fingerprint_is_a_sha256():
    digest = waivers.fingerprint(signal())
    assert waivers.FINGERPRINT_PATTERN.match(digest), digest


@pytest.mark.parametrize("changed", [
    {"line": 9},          # the finding moved
    {"literal": "7"},     # the finding changed what it says
    {"path": "src/other.py"},
    {"code": "GW-DIV-002"},
])
def test_fingerprint_moves_when_the_finding_moves(changed):
    """This is what makes a stale waiver visible instead of silently permissive."""
    assert waivers.fingerprint(signal(**changed)) != waivers.fingerprint(signal())


def test_fingerprint_is_order_insensitive_over_evidence():
    first, second = signal(), signal()
    first.evidence = {"a": 1, "b": 2}
    second.evidence = {"b": 2, "a": 1}
    assert waivers.fingerprint(first) == waivers.fingerprint(second)


def test_parse_time_returns_none_for_invalid_timestamp():
    """Malformed configuration is rejected by validation rather than treated as time."""
    assert waivers.parse_time("not-a-date") is None


# ---- validation --------------------------------------------------------------

@pytest.mark.parametrize("field,value,needle", [
    ("reason", "", "reason"),
    ("reason", "yes", "reason"),
    ("reviewer", "maintainer", "reviewer"),
    ("reviewer", "@", "reviewer"),
    ("path", "/etc/passwd", "repository-relative"),
    ("path", "../outside.py", "repository-relative"),
    ("signal_fingerprint", "deadbeef", "sha256"),
    ("rule_id", "", "rule_id"),
    ("id", "", "id"),
    ("created_at", "not-a-date", "created_at"),
    ("expires_at", "", "expires_at"),
])
def test_validation_rejects(field, value, needle):
    problems = waiver(**{field: value}).problems()
    assert any(needle in problem for problem in problems), problems


def test_lifetime_is_capped_at_thirty_days():
    long_lived = waiver(expires_at=waivers.iso(NOW + timedelta(days=31)))
    assert any("maximum" in problem for problem in long_lived.problems())

    at_the_cap = waiver(expires_at=waivers.iso(NOW + timedelta(days=30)))
    assert at_the_cap.problems() == []


def test_expiry_must_follow_creation():
    backwards = waiver(expires_at=waivers.iso(NOW - timedelta(days=1)))
    assert any("after created_at" in problem for problem in backwards.problems())


def test_an_unknown_rule_is_rejected():
    problems = waiver(rule_id="GW-XXX-999").problems(waivers.known_rules())
    assert any("unknown rule" in problem for problem in problems)


@pytest.mark.parametrize("name", ["GW-DIV-002", "error-path-default",
                                  "GW-VER-005", "test-weakened"])
def test_every_real_rule_resolves_by_code_and_by_id(name):
    assert name in waivers.known_rules()


# ---- the ledger on disk ------------------------------------------------------

def test_record_then_load_round_trips(tmp_path):
    waivers.record(waiver(), str(tmp_path))
    ledger = waivers.load(str(tmp_path))
    assert ledger.problems == []
    assert [entry.id for entry in ledger.waivers] == ["GW-2026-0001"]
    assert ledger.waivers[0].to_dict()["rule_id"] == "GW-TEST-004"


def test_ids_count_up_within_a_year():
    existing = [waiver(id="GW-2026-0001"), waiver(id="GW-2025-0007")]
    assert waivers.next_id(existing, 2026) == "GW-2026-0002"


def test_a_broken_ledger_is_a_problem_not_an_exception(tmp_path):
    (tmp_path / ".greenwash").mkdir()
    (tmp_path / ".greenwash" / "waivers.json").write_text("{not json", encoding="utf-8")
    ledger = waivers.load(str(tmp_path))
    assert ledger.waivers == []
    assert ledger.problems and "could not read" in ledger.problems[0]


def test_a_duplicate_id_is_malformed(tmp_path):
    (tmp_path / ".greenwash").mkdir()
    entries = [waiver().to_dict(), waiver().to_dict()]
    (tmp_path / ".greenwash" / "waivers.json").write_text(
        json.dumps({"version": 1, "waivers": entries}), encoding="utf-8")
    ledger = waivers.load(str(tmp_path))
    assert "duplicate" in ledger.waivers[1].problems()[0]


def test_an_entry_that_is_not_an_object_is_malformed():
    parsed = waivers.Waiver.from_dict(["not", "an", "object"])
    assert parsed.problems() == ["entry is not a JSON object"]


# ---- applying a waiver to a diff --------------------------------------------

def test_an_active_waiver_annotates_the_finding():
    application = waivers.apply([signal()], ledger_of(waiver()), now=NOW)
    assert application.active[0].status == waivers.ACTIVE
    assert application.signals[0].waived is True
    assert application.signals[0].waiver["reviewer"] == "@maintainer"
    assert application.blocking == []


def test_an_expired_waiver_stops_waiving():
    lapsed = waiver(created_at=waivers.iso(NOW - timedelta(days=40)),
                    expires_at=waivers.iso(NOW - timedelta(days=10)))
    application = waivers.apply([signal()], ledger_of(lapsed), now=NOW)
    assert application.rows[0].status == waivers.EXPIRED
    assert application.signals[0].waived is False
    assert application.blocking, "an expired waiver must block in strict mode"


def test_a_waiver_for_a_changed_line_is_stale():
    """The finding is still there -- so the decision no longer covers it."""
    application = waivers.apply([signal(line=9)], ledger_of(waiver()), now=NOW)
    assert application.rows[0].status == waivers.STALE
    assert application.blocking


def test_a_waiver_matching_nothing_is_visible_but_not_blocking():
    application = waivers.apply([signal(path="src/other.py")], ledger_of(waiver()), now=NOW)
    assert application.rows[0].status == waivers.UNMATCHED
    assert application.blocking == []


def test_a_malformed_entry_is_blocking():
    application = waivers.apply([signal()], ledger_of(waiver(reason="")), now=NOW)
    assert application.rows[0].status == waivers.MALFORMED
    assert application.blocking


def test_waiving_one_finding_leaves_the_others_alone():
    other = signal(line=7, literal="9", code="GW-DIV-002")
    application = waivers.apply([signal(), other], ledger_of(waiver()), now=NOW)
    assert application.signals[0].waived is True
    assert application.signals[1].waived is False


# ---- the command -------------------------------------------------------------

BASE = {
    "src/calc.py": "def add(a, b):\n    return a - b\n",
    "tests/test_calc.py": "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    "conftest.py": "",
}


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def cli(cwd, *args):
    import os
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-m", "greenwash", *args], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)


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


def test_the_command_writes_a_waiver_for_the_finding_in_the_diff(cheat):
    result = cli(cheat, "waive", "--rule", "hardcoded-return", "--path", "src/calc.py",
                 "--reason", "the constant is the documented answer for this fixture",
                 "--reviewer", "@maintainer", "--expires", "2026-10-20")
    assert result.returncode == 0, result.stderr
    written = json.loads((cheat / ".greenwash" / "waivers.json").read_text(encoding="utf-8"))
    entry = written["waivers"][0]
    assert entry["rule_id"] == "GW-TEST-004"
    assert entry["path"] == "src/calc.py"
    assert waivers.FINGERPRINT_PATTERN.match(entry["signal_fingerprint"])


def test_the_command_refuses_a_rule_it_does_not_know(cheat):
    result = cli(cheat, "waive", "--rule", "GW-NOPE-001", "--path", "src/calc.py",
                 "--reason", "a long enough reason to be a sentence",
                 "--reviewer", "@maintainer", "--expires", "2026-10-20")
    assert result.returncode == 3
    assert "unknown rule" in result.stderr


def test_the_command_refuses_when_there_is_nothing_to_waive(cheat):
    result = cli(cheat, "waive", "--rule", "GW-DIV-002", "--path", "src/calc.py",
                 "--reason", "a long enough reason to be a sentence",
                 "--reviewer", "@maintainer", "--expires", "2026-10-20")
    assert result.returncode == 3
    assert "no GW-DIV-002 finding" in result.stderr


def test_the_command_refuses_a_short_reason(cheat):
    result = cli(cheat, "waive", "--rule", "hardcoded-return", "--path", "src/calc.py",
                 "--reason", "fine", "--reviewer", "@maintainer", "--expires", "2026-10-20")
    assert result.returncode == 3
    assert "reason" in result.stderr


def test_the_command_requires_an_expiry(cheat):
    """No default expiry: a decision with no end date is a decision nobody re-reads."""
    result = cli(cheat, "waive", "--rule", "hardcoded-return", "--path", "src/calc.py",
                 "--reason", "the constant is the documented answer for this fixture",
                 "--reviewer", "@maintainer")
    assert result.returncode == 2
    assert "--expires" in result.stderr


def test_the_command_takes_a_fingerprint_when_the_path_has_several_findings(cheat):
    (cheat / "src" / "calc.py").write_text(
        "def add(a, b):\n    return 5\n\n\ndef mul(a, b):\n    return 10\n", encoding="utf-8")
    (cheat / "tests" / "test_calc.py").write_text(
        "from src.calc import add, mul\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
        "\n\ndef test_mul():\n    assert mul(2, 5) == 10\n", encoding="utf-8")
    result = cli(cheat, "waive", "--rule", "hardcoded-return", "--path", "src/calc.py",
                 "--reason", "the constants are the documented answers for this fixture",
                 "--reviewer", "@maintainer", "--expires", "2026-10-20")
    assert result.returncode == 3
    assert "2 hardcoded-return findings" in result.stderr
    assert "sha256:" in result.stderr
