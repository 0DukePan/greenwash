"""The Stop hook contract, tested without launching Claude Code.

Documented behaviour (https://code.claude.com/docs/en/hooks): exit 0 allows
the agent to stop; exit 2 blocks the stop and hands stderr back to the agent.

greenwash's own contract, which these pin down:

  report mode (default)  exit 0 and the report on stdout -- the agent may stop,
                         the developer still sees what the claim was worth
  enforce mode           exit 2 and the report on stderr, so the stop is
                         blocked and the agent gets the findings
                         (GREENWASH_ENFORCE=1, or "mode": "enforce" in config)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = HERE.parent / "scripts" / "greenwash_hook.py"

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


def _repo(tmp):
    _git(tmp, "init", "-q")
    for rel, content in BASE.items():
        _write(tmp, rel, content)
    _git(tmp, "add", "-A")
    _git(tmp, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")


def _stop(tmp, payload=None, enforce=False):
    env = dict(os.environ)
    if enforce:
        env["GREENWASH_ENFORCE"] = "1"
    return subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=tmp,
        input=json.dumps(payload or {"hook_event_name": "Stop"}),
        capture_output=True, text=True, env=env)


def test_hook_reports_a_faked_pass_without_blocking(tmp_path):
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return 5\n")
    result = _stop(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "hardcoded-return" in result.stdout


def test_hook_blocks_a_faked_pass_when_enforcing(tmp_path):
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return 5\n")
    result = _stop(tmp_path, enforce=True)
    assert result.returncode == 2
    assert "hardcoded-return" in result.stderr


def test_hook_allows_a_clean_tree(tmp_path):
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return a + b\n")
    result = _stop(tmp_path)
    assert result.returncode == 0, result.stderr


def test_hook_does_not_block_twice(tmp_path):
    # stop_hook_active means a previous Stop hook already forced a retry this
    # turn; blocking again is how you get an infinite loop.
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return 5\n")
    result = _stop(tmp_path, {"hook_event_name": "Stop", "stop_hook_active": True},
                   enforce=True)
    assert result.returncode == 0
