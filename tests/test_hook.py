"""The Stop hook contract, tested without launching Claude Code.

Documented behaviour (https://code.claude.com/docs/en/hooks): exit 0 allows
the agent to stop; exit 2 blocks the stop and hands stderr back to the agent.
These drive scripts/greenwash_hook.py the same way Claude Code does -- a JSON
payload on stdin -- so the enforcement layer is covered even when no model is
reachable.
"""

import json
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


def _stop(tmp, payload=None):
    return subprocess.run(
        [sys.executable, str(HOOK)],
        cwd=tmp,
        input=json.dumps(payload or {"hook_event_name": "Stop"}),
        capture_output=True, text=True)


def test_hook_blocks_a_faked_pass(tmp_path):
    _repo(tmp_path)
    _write(tmp_path, "src/calc.py", "def add(a, b):\n    return 5\n")
    result = _stop(tmp_path)
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
    result = _stop(tmp_path, {"hook_event_name": "Stop", "stop_hook_active": True})
    assert result.returncode == 0
