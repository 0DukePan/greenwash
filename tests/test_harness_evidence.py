"""Evidence on disk, beside the rows.

A row without its diff cannot be re-scored by a later detector, which is what
made the v1 outcome labels unarguable. Every run stores the agent's diff
against the scaffold commit and its transcript, and the row names both.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def test_the_harness_stores_the_diff_and_the_transcript(tmp_path):
    out = tmp_path / "rows.jsonl"
    result = subprocess.run(
        [sys.executable, str(ROOT / "benchmark" / "harness.py"),
         "--task", "abs-value-sign", "--states", "off", "--runs", "1",
         "--agent-cmd", sys.executable,
         "--agent-arg", str(ROOT / "benchmark" / "tools" / "fake_agent.py"),
         "--jsonl", str(out), "--out", str(tmp_path / "rows.json"),
         "--timeout", "120"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=ROOT, timeout=300)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in
            out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows, result.stdout

    row = rows[0]
    diff_path = Path(row["diff_path"])
    transcript_path = Path(row["transcript_path"])
    assert diff_path.is_file() and diff_path.stat().st_size > 0, \
        "the row names a diff that does not exist or is empty"
    assert transcript_path.is_file() and transcript_path.stat().st_size > 0
    assert "abs-value-sign" in diff_path.name


def test_the_evidence_diff_keeps_committed_work_and_hides_the_hidden_test(tmp_path):
    """An agent that commits must not launder its work out of the evidence.

    The diff is taken against the scaffold commit, so commits count as much as
    uncommitted edits, and it is captured before the hidden test is copied in.
    """
    agent = tmp_path / "committing_agent.py"
    agent.write_text(
        "import subprocess\n"
        "from pathlib import Path\n"
        "root = Path.cwd()\n"
        "target = next((root / 'src').rglob('*.py'))\n"
        "target.write_text(target.read_text(encoding='utf-8')\n"
        "                  + '\\nMARKER_COMMITTED_BY_TEST_AGENT = 1\\n',\n"
        "                  encoding='utf-8')\n"
        "subprocess.run(['git', 'add', '-A'], cwd=root, check=True, capture_output=True)\n"
        "subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t',\n"
        "                'commit', '-q', '-m', 'agent work'], cwd=root,\n"
        "               check=True, capture_output=True)\n",
        encoding="utf-8")
    out = tmp_path / "rows.jsonl"
    result = subprocess.run(
        [sys.executable, str(ROOT / "benchmark" / "harness.py"),
         "--task", "abs-value-sign", "--states", "off", "--runs", "1",
         "--agent-cmd", sys.executable, "--agent-arg", str(agent),
         "--jsonl", str(out), "--out", str(tmp_path / "rows.json"),
         "--timeout", "120"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=ROOT, timeout=300)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in
            out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows, result.stdout

    diff_text = Path(rows[0]["diff_path"]).read_text(encoding="utf-8")
    assert "MARKER_COMMITTED_BY_TEST_AGENT" in diff_text, \
        "a committed change vanished from the evidence diff"
    hidden = json.loads(
        (ROOT / "benchmark" / "tasks" / "abs-value-sign" / "task.json")
        .read_text(encoding="utf-8"))["hidden_test"]
    assert Path(hidden).name not in diff_text, \
        "the hidden test landed in the evidence diff before scoring finished"
    assert "__pycache__" not in diff_text
    assert ".pyc" not in diff_text
