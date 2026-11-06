"""The git plumbing the session anchor depends on.

The anchor is written twice: a per-worktree state file and a git ref. The
fallbacks here -- recovering a missing or corrupt file from the ref, and
flagging a file that disagrees with it -- are load bearing: rebuilding or
rewriting the anchor silently would be an invisible laundering path.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import gitutil  # noqa: E402


def _repo(tmp):
    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True, capture_output=True)
    (tmp / "notes.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "base"], cwd=tmp, check=True, capture_output=True)


def test_adopt_then_read_round_trips(tmp_path):
    _repo(tmp_path)
    state = gitutil.adopt_session_base(tmp_path)
    assert state["base"] == gitutil.head_commit(tmp_path)
    assert gitutil.read_session_base(tmp_path) == {"base": state["base"], "stash": "",
                                                  "recovered": False, "mismatch": False}


def test_read_session_base_recovers_a_corrupt_file_from_its_ref(tmp_path):
    _repo(tmp_path)
    adopted = gitutil.adopt_session_base(tmp_path)
    state = Path(gitutil.session_base_path(tmp_path))
    state.write_text("{not json", encoding="utf-8")
    read = gitutil.read_session_base(tmp_path)
    assert read["base"] == adopted["base"]
    assert read["recovered"] is True
    assert read["mismatch"] is False


def test_read_session_base_flags_an_edited_anchor(tmp_path):
    _repo(tmp_path)
    adopted = gitutil.adopt_session_base(tmp_path)
    state = Path(gitutil.session_base_path(tmp_path))
    state.write_text(json.dumps({"base": gitutil.EMPTY_TREE, "stash": ""}),
                     encoding="utf-8")
    read = gitutil.read_session_base(tmp_path)
    assert read["base"] == adopted["base"]
    assert read["mismatch"] is True


def test_session_diff_keeps_committed_work_in_scope(tmp_path):
    _repo(tmp_path)
    state = gitutil.adopt_session_base(tmp_path)
    (tmp_path / "notes.txt").write_text("cheat\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "agent work"], cwd=tmp_path,
                   check=True, capture_output=True)
    assert "cheat" in gitutil.session_diff(state["base"], cwd=tmp_path)


def test_binary_paths_are_read_from_the_differ_line():
    """A binary stanza has no +++ line, so it needs its own parse."""
    diff = ("diff --git a/src/calc.py b/src/calc.py\n"
            "index 1111111..2222222 100644\n"
            "Binary files a/src/calc.py and b/src/calc.py differ\n"
            "diff --git a/assets/logo.png b/assets/logo.png\n"
            "new file mode 100644\n"
            "index 0000000..3333333\n"
            "Binary files /dev/null and b/assets/logo.png differ\n"
            "diff --git a/assets/old.png b/assets/old.png\n"
            "deleted file mode 100644\n"
            "index 4444444..0000000\n"
            "Binary files a/assets/old.png and /dev/null differ\n")
    assert gitutil.binary_paths(diff) == ["src/calc.py", "assets/logo.png"]

import pytest  # noqa: E402

# Excluded from the default gate: this module spawns a process
# (a CLI, a hook, a git repository or a benchmark harness).
pytestmark = pytest.mark.slow
