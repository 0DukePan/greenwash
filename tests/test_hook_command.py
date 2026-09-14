"""The plugin's hook command, run the way the host runs it.

`hooks/hooks.json` names `python3` first and falls back to `python`, because
there is no single interpreter name that exists on both a stock Linux (python3,
no python) and a stock Windows (python, no python3). The bare `python` this
replaced silently never ran on Linux -- most of the plugin's audience.

Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` itself and hands the result to
the platform shell, so that is what this does: substitute, then run through
`shell=True` (cmd.exe on Windows, /bin/sh elsewhere) with a Stop payload on
stdin, in a repo where the agent faked a pass. A hook that cannot start is a
hook that does not exist, and this is the gate that says so on either OS.
"""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS = ROOT / "hooks" / "hooks.json"


def _hook_command() -> str:
    data = json.loads(HOOKS.read_text(encoding="utf-8"))
    return data["hooks"]["Stop"][0]["hooks"][0]["command"]


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_the_hook_command_runs_a_report(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calc.py").write_text("def add(a, b):\n    return a - b\n",
                                              encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(
        "from src.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base")

    # the agent's "fix": the literal the test asserts
    (tmp_path / "src" / "calc.py").write_text("def add(a, b):\n    return 5\n",
                                              encoding="utf-8")

    command = _hook_command().replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT))
    result = subprocess.run(
        command, shell=True, cwd=tmp_path, capture_output=True, text=True,
        input=json.dumps({"hook_event_name": "Stop"}),
        env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT)}, timeout=240)

    assert result.returncode == 0, result.stderr
    # The hook's message, not the full report: it is written for the agent.
    assert "greenwash:" in result.stdout, (result.stdout, result.stderr)
    assert "[hardcoded-return]" in result.stdout


def test_the_command_names_both_interpreter_spellings():
    """The fallback is the fix, so pin it rather than trusting a future edit."""
    command = _hook_command()
    assert "python3" in command and "python " in command
