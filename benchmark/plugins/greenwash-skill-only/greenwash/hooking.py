"""Shared Stop-hook mechanics: profile detection, block budget, deadlines.

Both Stop hooks -- the Claude plugin's and the Codex plugin's -- make the same
three decisions, and answering them in two places is how the two gates drift
apart. The policy itself lives in the CLI; this module only carries it.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile

from . import config as config_mod
from . import gitutil

BLOCK_BUDGET = 3
DEFAULT_HOOK_TIMEOUT = 240


def hook_timeout(default: int = DEFAULT_HOOK_TIMEOUT) -> int:
    """The hook's own deadline, deliberately not GREENWASH_TIMEOUT.

    GREENWASH_TIMEOUT budgets one test run. This budgets the whole report,
    which runs up to five of them. Sharing one knob kills a legitimately long
    suite at exactly the moment the check matters.
    """
    raw = os.environ.get("GREENWASH_HOOK_TIMEOUT", "")
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def blocking_mode(cwd=".") -> str:
    """"strict", "enforce", or "report", from the environment then the config.

    The mechanical-failure path needs the profile without the CLI: the checker
    is exactly what could not run, so the hook decides for itself. A config
    that says strict must not get the fail-open treatment just because the
    environment stayed quiet.
    """
    if os.environ.get("GREENWASH_STRICT") == "1":
        return "strict"
    if os.environ.get("GREENWASH_ENFORCE") == "1":
        return "enforce"
    config = config_mod.load(cwd)
    if config.strict:
        return "strict"
    if config.enforcing:
        return "enforce"
    return "report"


def _state_path(cwd=None) -> str:
    try:
        return gitutil.git_path(os.path.join("greenwash", "state.json"), cwd=cwd)
    except gitutil.GitError:
        key = _key(cwd).split(":", 1)[0]
        return os.path.join(tempfile.gettempdir(), f"greenwash-hook-{key}.json")


def _key(cwd=None) -> str:
    try:
        root = gitutil.repo_root(cwd) or (cwd or ".")
    except Exception:                       # pragma: no cover - git plumbing
        root = cwd or "."
    return hashlib.sha1(os.path.realpath(root).encode("utf-8")).hexdigest()[:12]


def take_block(cwd=None, session_id: str = "") -> bool:
    """Consume one block from the session's budget. True means: block now.

    The budget is what bounds the loop. A finding the agent cannot resolve --
    one that needs a human waiver -- blocks at most BLOCK_BUDGET times and then
    ends in UNRESOLVED AT STOP, never an infinite retry. An agent that ignores
    every block gets the same ceiling. A missing or unreadable state file is a
    fresh budget, never an open gate -- and never a crash: the hook failing to
    read its own state would silently remove the gate.
    """
    key = f"{_key(cwd)}:{session_id or 'default'}"
    path = _state_path(cwd)
    record = {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        record = {}
    if not isinstance(record, dict):
        record = {}
    try:
        used = int((record.get("blocks") or {}).get(key, 0))
    except (TypeError, ValueError):
        print(f"greenwash: the block budget state is unreadable; starting a fresh "
              f"budget ({path})", file=sys.stderr)
        used = 0
    if used >= BLOCK_BUDGET:
        return False
    record.setdefault("blocks", {})[key] = used + 1
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
    except OSError as exc:
        print(f"greenwash: could not record the block budget ({exc}); "
              "blocking anyway", file=sys.stderr)
    return True


def unresolved_banner(cwd=None) -> str:
    """The line a transcript keeps when the budget runs out.

    The note is logged next to the budget state, never inside it: the state
    file is JSON the next run reads, and appending text to it would corrupt the
    count and hand the session a fresh budget.
    """
    try:
        with open(_state_path(cwd) + ".log", "a", encoding="utf-8") as handle:
            handle.write("UNRESOLVED AT STOP\n")
    except OSError as exc:
        print(f"greenwash: could not log the unresolved stop ({exc})", file=sys.stderr)
    return ("UNRESOLVED AT STOP -- greenwash blocked as often as its budget "
            "allows and the findings are still open. A human must look at them.")


def run_with_deadline(command, env=None, timeout: int = DEFAULT_HOOK_TIMEOUT):
    """(stdout, stderr, returncode), or the subprocess error is raised.

    On timeout the whole process tree dies, the way the test runner does it:
    a pytest grandchild left running is a hang the next report inherits.
    """
    from .verify.runner import _kill_tree
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=env, encoding="utf-8", errors="replace")
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        raise
    return out, err, proc.returncode


__all__ = ["BLOCK_BUDGET", "DEFAULT_HOOK_TIMEOUT", "hook_timeout", "blocking_mode",
           "take_block", "unresolved_banner", "run_with_deadline"]
