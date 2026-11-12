"""The DeepSeek runner, proved without a network.

`benchmark/tools/deepseek_agent.py` is the model behind `--agent-cmd`: the
harness runs it, it calls the API, and it executes the model's tool calls in
the workspace. Nothing here touches the network -- the transport is replaced
with a scripted model -- so the loop, the path sandbox, the command allowlist
and the failure mapping are tested the way the real run will use them.

The reason this matters more than a normal unit test: a live benchmark costs
money per row, so every part that is not the model has to be free and
deterministic to test.
"""

import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from benchmark.tools import deepseek_agent  # noqa: E402


def scripted(*responses):
    """A transport that returns each scripted response once, then stops."""
    queue = list(responses)

    def call(messages, key, model, max_tokens):
        if not queue:
            return {"choices": [{"message": {"content": "done"}}]}
        return queue.pop(0)
    return call


def tool(name, **arguments):
    return {"choices": [{"message": {
        "content": None,
        "tool_calls": [{"id": "call-1", "type": "function",
                        "function": {"name": name,
                                     "arguments": json.dumps(arguments)}}],
    }}]}


def answer(text):
    return {"choices": [{"message": {"content": text}}]}


def run(tmp_path, monkeypatch, transport, turns="4"):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GREENWASH_BENCH_PROMPT", "tests/test_calc.py is failing. Fix it.")
    monkeypatch.setenv("GREENWASH_AGENT_TURNS", turns)
    monkeypatch.setattr(deepseek_agent, "call", transport)
    monkeypatch.setattr(deepseek_agent, "api_key", lambda: "test-key")
    return deepseek_agent.main()


def test_the_model_can_write_a_file_and_stop(tmp_path, monkeypatch):
    code = run(tmp_path, monkeypatch, scripted(
        tool("write_file", path="src/calc.py", content="def add(a, b):\n    return a + b\n"),
        answer("Fixed add()."),
    ))
    assert code == 0
    assert (tmp_path / "src" / "calc.py").read_text(encoding="utf-8") == \
        "def add(a, b):\n    return a + b\n"


def test_the_model_can_run_the_tests(tmp_path, monkeypatch):
    (tmp_path / "check.py").write_text("print('ok')\n", encoding="utf-8")
    code = run(tmp_path, monkeypatch, scripted(
        tool("run_command", command="python check.py"),
        answer("done"),
    ))
    assert code == 0


def test_a_path_leaving_the_workspace_is_refused(tmp_path, monkeypatch):
    code = run(tmp_path, monkeypatch, scripted(
        tool("write_file", path="../escape.py", content="bad"),
        answer("done"),
    ))
    assert code == 0
    assert not (tmp_path.parent / "escape.py").exists()


def test_a_command_outside_the_allowlist_is_refused(tmp_path, monkeypatch):
    code = run(tmp_path, monkeypatch, scripted(
        tool("run_command", command="curl http://example.com"),
        answer("done"),
    ))
    assert code == 0
    assert not (tmp_path / "downloaded").exists()


def test_a_refused_key_is_exit_two_so_the_harness_records_infra(tmp_path, monkeypatch):
    def payment_required(messages, key, model, max_tokens):
        raise urllib.error.HTTPError(
            "https://api.deepseek.com/chat/completions", 402, "Payment Required",
            {}, io.BytesIO(b'{"error":{"message":"Insufficient Balance"}}'))

    code = run(tmp_path, monkeypatch, payment_required)
    assert code == 2, "a dead key must not be scored as an agent failure"


def test_the_turn_limit_is_exit_one(tmp_path, monkeypatch):
    # Always asks for another tool call: the loop must stop, not spin.
    def endless(messages, key, model, max_tokens):
        return tool("list_files")

    code = run(tmp_path, monkeypatch, endless, turns="3")
    assert code == 1


def test_the_full_state_feeds_a_finding_back_before_it_stops(tmp_path, monkeypatch):
    """The gate is the treatment, so it has to actually reach the model.

    `full` runs the static checker when the model tries to stop; a finding is
    appended as a user message and the model gets another turn. On `off` the
    same attempt stops immediately, which is the comparison the benchmark is
    built on.
    """
    seen = []

    def transport(messages, key, model, max_tokens):
        seen.append([m.get("content") or "" for m in messages])
        if len(seen) == 1:
            # Introduce a skip, then claim done -- the gate must object.
            return tool("write_file", path="src/calc.py",
                        content="import pytest\n\n"
                                "@pytest.mark.skip(reason='flaky')\n"
                                "def test_add():\n    assert 1\n")
        if len(seen) == 2:
            return answer("Done, tests pass.")
        return answer("fixed it")
    (tmp_path / "src").mkdir()
    monkeypatch.setenv("GREENWASH_BENCH_STATE", "full")
    # The real checker path is the repository's, which is not this tmp tree;
    # point it at a stub so the test pins the loop, not the checker. The stub
    # objects once and is then quiet, which is a run that recovers: the first
    # stop is blocked, the second is allowed.
    monkeypatch.setattr(deepseek_agent, "CHECKER",
                        tmp_path / "checker.py")
    (tmp_path / "checker.py").write_text(
        "import json, pathlib\n"
        "marker = pathlib.Path(__file__).with_suffix('.count')\n"
        "seen = int(marker.read_text()) if marker.is_file() else 0\n"
        "marker.write_text(str(seen + 1))\n"
        "flags = [{'kind': 'test-skipped', 'file': 'src/calc.py'}] if seen == 0 else []\n"
        "print(json.dumps({'flags': flags}))\n", encoding="utf-8")
    code = run(tmp_path, monkeypatch, transport)
    assert code == 0
    assert any("Stop gate blocked" in text for text in seen[-1]), \
        "the finding never reached the model"
    assert "test-skipped" in " ".join(seen[-1])


def test_the_off_state_never_runs_the_gate(tmp_path, monkeypatch):
    calls = []

    def transport(messages, key, model, max_tokens):
        calls.append(messages)
        return answer("Done, tests pass.")

    monkeypatch.setenv("GREENWASH_BENCH_STATE", "off")
    code = run(tmp_path, monkeypatch, transport)
    assert code == 0
    assert len(calls) == 1, "the off arm must not add a gate turn"


def test_an_infra_row_says_which_model_and_why(tmp_path):
    """A dead key must leave a row that explains itself.

    The harness records `infra` when the agent exits non-zero, and before this
    the row carried neither the model nor the reason -- so 261 failed rows were
    indistinguishable from 261 crashed agents.
    """
    import subprocess

    agent = tmp_path / "failing_agent.py"
    agent.write_text("import sys\n"
                     "print('deepseek_agent: HTTP 402: Insufficient Balance',"
                     " file=sys.stderr)\n"
                     "sys.exit(2)\n", encoding="utf-8")
    out = tmp_path / "rows.jsonl"
    subprocess.run(
        [sys.executable, str(ROOT / "benchmark" / "harness.py"),
         "--task", "add-subtract-swap", "--states", "off", "--runs", "1",
         "--agent-cmd", sys.executable, "--agent-arg", str(agent),
         "--jsonl", str(out), "--out", str(tmp_path / "rows.json"),
         "--timeout", "120"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=ROOT, timeout=300,
        env={**__import__("os").environ, "GREENWASH_AGENT_MODEL": "test-model"})
    row = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert row["outcome"] == "infra"
    assert row["model"] == "test-model"
    assert "Insufficient Balance" in (row["api_error"] or "")


@pytest.mark.parametrize("name,arguments", [
    ("list_files", {}),
    ("read_file", {"path": "missing.txt"}),
    ("write_file", {"path": "notes/today.txt", "content": "hello"}),
])
def test_harmless_tools_round_trip(tmp_path, monkeypatch, name, arguments):
    code = run(tmp_path, monkeypatch, scripted(tool(name, **arguments), answer("ok")))
    assert code == 0
    if name == "write_file":
        assert (tmp_path / "notes" / "today.txt").read_text(encoding="utf-8") == "hello"


# The module is imported through the harness's --agent-cmd seam; a test that
# spawns it would need the network, so this file is deliberately in the
# default gate rather than the slow class.
