#!/usr/bin/env python3
"""Reproducible demo: the Claude Code strict gate, end to end.

No model, no network, no API key. Everything inside the `$` blocks is the real
hook's own output, captured from a throwaway repository this script builds:
the agent fakes a pass, the gate blocks the end of the turn, a decision is
recorded, and the same turn is then allowed -- with the waiver named in the
report rather than the finding quietly disappearing.

Run:  python demo/strict_claude.py [--terse]

--terse drops the narration and prints only the commands and their output, so
the whole thing can be pasted into a post as a receipt.
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TERSE = "--terse" in sys.argv
ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts" / "greenwash_hook.py"
COLUMNS = "76"
CLAUDE_PLUGIN_ROOT = ROOT

sys.path.insert(0, str(ROOT))

from greenwash.report import terminal  # noqa: E402

STEPS: list = []


def emit(text: str = "") -> None:
    sys.stdout.write(terminal.encode_safe(text) + "\n")


def say(text: str = "") -> None:
    if not TERSE:
        emit(text)


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def run(args, cwd, env=None, stdin=""):
    child = {**os.environ, "PYTHONPATH": str(ROOT), "COLUMNS": COLUMNS,
             "PYTHONIOENCODING": "utf-8", **(env or {})}
    return subprocess.run(args, cwd=cwd, input=stdin, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=child, timeout=600)


def hook(cwd):
    """The hook, started the way the host starts it: payload on stdin."""
    return run([sys.executable, str(HOOK)], cwd,
               env={"CLAUDE_PLUGIN_ROOT": str(CLAUDE_PLUGIN_ROOT), "GREENWASH_STRICT": "1"},
               stdin=json.dumps({"hook_event_name": "Stop",
                                 "summary": "Fixed the failing test"}))


def cli(args, cwd):
    return run([sys.executable, "-m", "greenwash", *args], cwd)


def build_repo(root: Path) -> Path:
    repo = root / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "calc.py").write_text("def add(a, b):\n    return a - b\n",
                                          encoding="utf-8")
    (repo / "tests" / "test_calc.py").write_text(
        "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")
    (repo / "conftest.py").write_text("", encoding="utf-8")
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=demo@demo", "-c", "user.name=demo",
        "commit", "-q", "-m", "add a deliberately wrong add()")
    return repo


def record(step: str, command: str, result) -> None:
    stream = result.stderr if result.stderr.strip() else result.stdout
    emit(f"$ {command}")
    emit(stream.rstrip())
    emit(f"exit code: {result.returncode}")
    emit()
    STEPS.append((step, result.returncode))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="greenwash-strict-claude-") as tmp:
        repo = build_repo(Path(tmp))
        say("Claude Code strict gate, on a repository this script just built.")
        say("The agent was told 'tests/test_calc.py is failing. Fix it.'")
        say('It replied "Done! tests/test_calc.py passes now." -- and it does:')
        say("add(2, 3) returns 5 because the value was hardcoded.\n")

        (repo / "src" / "calc.py").write_text(
            "def add(a, b):\n    return 5\n", encoding="utf-8")

        say("1. The turn tries to end.\n")
        record("blocked", "echo '{\"hook_event_name\": \"Stop\"}' | "
                          "python scripts/greenwash_hook.py", hook(repo))
        say("   exit 2 hands the findings back to the agent: the turn does not\n"
            "   end on an unexplained finding.\n")

        expires = (datetime.now(timezone.utc) + timedelta(days=27)).strftime("%Y-%m-%d")
        say("2. The finding is correct, so a decision is recorded -- with a name,\n"
            "   a reason and an expiry on it.\n")
        record("waived", "greenwash waive --rule hardcoded-return --path src/calc.py \\\n"
                         "      --reason \"the constant is the documented answer for this "
                         "fixture\" \\\n"
                         "      --reviewer @maintainer --expires " + expires,
               cli(["waive", "--rule", "hardcoded-return", "--path", "src/calc.py",
                    "--reason", "the constant is the documented answer for this fixture",
                    "--reviewer", "@maintainer", "--expires", expires], repo))

        say("3. The same turn ends again.\n")
        result = hook(repo)
        emit("$ echo '{\"hook_event_name\": \"Stop\"}' | python scripts/greenwash_hook.py")
        emit(result.stdout.rstrip())
        emit(f"exit code: {result.returncode}")
        emit()
        STEPS.append(("allowed", result.returncode))
        say("   Allowed -- and the waiver is named in the hand-back, because a\n"
            "   waived finding is a decision, not a clean report.\n")

        say("4. For comparison, the same diff in report mode (the CLI default):\n")
        result = cli(["scan", "--no-color", "--quiet"], repo)
        emit("$ greenwash scan --quiet")
        emit(result.stdout.rstrip())
        emit(f"exit code: {result.returncode}  (findings reported, nothing blocked)")
        emit()

        emit("Receipts")
        for step, code in STEPS:
            emit(f"  {step:<10} exit {code}")
        emit("  " + "-" * 40)
        emit("  every line above is captured output, not a transcript")
    return 0


if __name__ == "__main__":
    sys.exit(main())
