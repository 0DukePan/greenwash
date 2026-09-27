#!/usr/bin/env python3
"""Reproducible demo: the Codex strict gate, end to end.

Same checker, same policy, different host pack. What this shows that the
Claude demo does not is the profile: the Codex plugin runs `--strict` with no
environment variable and no config file, because a plugin is opted into once by
someone who wants a gate.

All four flows, each captured from the real hook:

  clean   the code is fixed          -> allowed
  block   the value is hardcoded     -> blocked, with the findings handed back
  waive   a decision is recorded     -> allowed, and the waiver is named
  error   the checker cannot run     -> the turn is NOT blocked, and the
                                        transcript says the diff was not checked

Run:  python demo/strict_codex.py [--terse]
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
HOOK = ROOT / "codex" / "scripts" / "greenwash_hook.py"
COLUMNS = "76"

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
    child = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": COLUMNS,
             "PYTHONPATH": str(ROOT), **(env or {})}
    return subprocess.run(args, cwd=cwd, input=stdin, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=child, timeout=600)


def hook(cwd, summary="Fixed the failing test"):
    """Started the way the host starts it: payload on stdin, no env overrides."""
    return run([sys.executable, str(HOOK)], cwd,
               stdin=json.dumps({"hook_event_name": "Stop", "summary": summary}))


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


def show(step: str, command: str, result, stream: str = "stderr") -> None:
    text = result.stderr if stream == "stderr" else result.stdout
    emit(f"$ {command}")
    emit(text.rstrip())
    emit(f"exit code: {result.returncode}")
    emit()
    STEPS.append((step, result.returncode))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="greenwash-strict-codex-") as tmp:
        repo = build_repo(Path(tmp))
        say("The Codex plugin, on a repository this script just built. No config\n"
            "file, no GREENWASH_STRICT: strict is what the plugin does.\n")

        say("1. The agent hardcodes the value its test asserts.\n")
        (repo / "src" / "calc.py").write_text("def add(a, b):\n    return 5\n",
                                              encoding="utf-8")
        show("blocked", "python codex/scripts/greenwash_hook.py < stop.json", hook(repo))

        expires = (datetime.now(timezone.utc) + timedelta(days=27)).strftime("%Y-%m-%d")
        say("2. The constant is the documented answer here, so the decision is\n"
            "   recorded rather than the rule switched off.\n")
        show("waived",
             "greenwash waive --rule hardcoded-return --path src/calc.py --reason ... "
             "--reviewer @maintainer --expires " + expires,
             cli(["waive", "--rule", "hardcoded-return", "--path", "src/calc.py",
                  "--reason", "the constant is the documented answer for this fixture",
                  "--reviewer", "@maintainer", "--expires", expires], repo),
             stream="stdout")
        show("allowed", "python codex/scripts/greenwash_hook.py < stop.json", hook(repo),
             stream="stdout")

        say("3. The real fix is also the cheapest thing to do, and the gate is quiet.\n")
        (repo / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n",
                                              encoding="utf-8")
        show("fixed", "python codex/scripts/greenwash_hook.py < stop.json", hook(repo),
             stream="stdout")

        say("4. When the checker cannot analyse anything, the turn is not blocked --\n"
            "   and the transcript says so. A gate that locks you out when the\n"
            "   checker is missing is a gate people uninstall.\n")
        broken = Path(tmp) / "no-history"
        broken.mkdir()
        (broken / "README.md").write_text("nothing to compare against\n", encoding="utf-8")
        show("error", "python codex/scripts/greenwash_hook.py < stop.json "
                      "(a directory with no git history)", hook(broken))

        emit("Receipts")
        for step, code in STEPS:
            emit(f"  {step:<10} exit {code}")
        emit("  " + "-" * 40)
        emit("  every line above is captured output, not a transcript")
    return 0


if __name__ == "__main__":
    sys.exit(main())
