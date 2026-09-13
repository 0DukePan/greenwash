"""git plumbing shared by the scanner and the verifier.

Kept separate because both layers need the same three things -- the diff, a
detached baseline worktree, and basic repo identity -- and because this is the
one place that talks to a subprocess that can fail in ways we must survive.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional

from .domain import FileChange


class GitError(RuntimeError):
    """git is missing, or this is not a repository."""


def _git(args, cwd=None, check=False) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, check=check)
    except FileNotFoundError as exc:  # pragma: no cover - depends on the host
        raise GitError("git not found on PATH") from exc


def is_repo(cwd=None) -> bool:
    result = _git(["rev-parse", "--is-inside-work-tree"], cwd=cwd)
    return result.returncode == 0 and result.stdout.strip() == "true"


def repo_root(cwd=None) -> str:
    result = _git(["rev-parse", "--show-toplevel"], cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ""


def head_commit(cwd=None) -> str:
    result = _git(["rev-parse", "HEAD"], cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ""


def branch(cwd=None) -> str:
    result = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ""


def diff(staged: bool = False, base: Optional[str] = None, cwd=None) -> str:
    """The diff we analyse, scoped to the directory we were invoked in.

    Brand-new, never-`git add`-ed files are registered as intent-to-add first:
    otherwise a freshly created conftest.py or test file is invisible to
    `git diff`, which is exactly the diff we most want to see.

    The `-- .` pathspec is not decoration. Without it, running in any
    subdirectory of a large repository (a monorepo checkout, or a temp
    directory that happens to sit under a `git init`-ed home directory) makes
    `git add -N -A` index the *entire* enclosing repository, which is slow
    enough to look like a hang and mutates an index that is not ours to touch.
    """
    if not is_repo(cwd):
        raise GitError("not a git repository (or any parent is missing a .git)")
    if not base and not head_commit(cwd):
        # Checked up front rather than by matching git's error text: the wording
        # for an empty repository varies ("bad revision 'HEAD'", "ambiguous
        # argument 'HEAD'", "does not have any commits yet").
        raise GitError("this repository has no commits yet, so there is nothing to "
                       "compare against -- commit once and run greenwash again")
    scope = ["--", "."]
    _git(["add", "-N", "-A", *scope], cwd=cwd)

    if base:
        args = ["diff", f"{base}...HEAD", *scope]
    elif staged:
        args = ["diff", "--staged", *scope]
    else:
        args = ["diff", "HEAD", *scope]
    result = _git(args, cwd=cwd)
    if result.returncode != 0:
        raise GitError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def is_subdirectory(cwd=None) -> bool:
    """True when we are below the repository root (so the diff is scoped)."""
    root = repo_root(cwd)
    if not root:
        return False
    return os.path.normcase(os.path.realpath(root)) != \
        os.path.normcase(os.path.realpath(cwd or os.getcwd()))


def parse_diff(diff_text: str):
    """Return (files, deleted).

    files maps path -> {"added": [str], "removed": [str], "added_lines": set[int]}
    where added_lines are 1-indexed line numbers in the *new* file, so
    structural checks can tell whether a node was introduced by this diff.
    """
    files: dict[str, dict] = {}
    deleted: list[str] = []
    current: Optional[str] = None
    pending_old: Optional[str] = None
    new_line = 0

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            current = None
            pending_old = None
        elif line.startswith("--- "):
            old = line[4:]
            pending_old = None if old == "/dev/null" else (old[2:] if old.startswith("a/") else old)
        elif line.startswith("+++ "):
            new = line[4:]
            if new == "/dev/null":
                if pending_old:
                    deleted.append(pending_old)
                current = None
            else:
                current = new[2:] if new.startswith("b/") else new
                files.setdefault(current, {"added": [], "removed": [], "added_lines": set()})
        elif line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else 0
        elif current is None:
            continue
        elif line.startswith("+"):
            files[current]["added"].append(line[1:])
            files[current]["added_lines"].add(new_line)
            new_line += 1
        elif line.startswith("-"):
            files[current]["removed"].append(line[1:])
        elif line.startswith(" "):
            new_line += 1

    return files, deleted


def change_list(files: dict, deleted: list) -> list:
    """FileChange records for the report's Changes section."""
    changes = []
    for path, hunks in sorted(files.items()):
        added, removed = len(hunks.get("added", [])), len(hunks.get("removed", []))
        kind = "added" if added and not removed else ("modified" if removed else "added")
        changes.append(FileChange(path=path, added=added, removed=removed, kind=kind))
    for path in deleted:
        if path not in files:
            changes.append(FileChange(path=path, kind="deleted"))
    return changes


def find_related_test_files(impl_path: str, cwd=None) -> list:
    stem, ext = os.path.splitext(os.path.basename(impl_path))
    dirname = os.path.dirname(impl_path)
    guesses = [
        os.path.join(dirname, f"test_{stem}{ext}"),
        os.path.join(dirname, f"{stem}_test{ext}"),
        os.path.join(dirname, f"{stem}.test{ext}"),
        os.path.join(dirname, f"{stem}.spec{ext}"),
        os.path.join(dirname, "tests", f"test_{stem}{ext}"),
        os.path.join(dirname, "tests", f"{stem}_test{ext}"),
        os.path.join(dirname, "tests", f"{stem}.test{ext}"),
        os.path.join(dirname, "tests", f"{stem}.spec{ext}"),
        os.path.join("tests", f"test_{stem}{ext}"),
        os.path.join("tests", f"{stem}_test{ext}"),
        os.path.join("tests", f"{stem}.test{ext}"),
        os.path.join("tests", f"{stem}.spec{ext}"),
        os.path.join("test", f"test_{stem}{ext}"),
        os.path.join("__tests__", f"{stem}{ext}"),
    ]
    return [os.path.join(cwd, g) if cwd else g
            for g in guesses
            if os.path.isfile(os.path.join(cwd, g) if cwd else g)]


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            return handle.read()
    except OSError:
        return ""


def baseline_worktree(cwd=None) -> Optional[str]:
    """A detached worktree at HEAD, for the before/after comparison.

    Returns None when it cannot be created -- the caller reports 'baseline
    unavailable' rather than pretending the comparison passed.
    """
    tmp = tempfile.mkdtemp(prefix="greenwash-base-")
    os.rmdir(tmp)                      # git worktree add creates the directory
    _git(["worktree", "prune"], cwd=cwd)
    result = _git(["worktree", "add", "--detach", tmp, "HEAD"], cwd=cwd)
    if result.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    return tmp


def drop_worktree(path: str, cwd=None) -> None:
    _git(["worktree", "remove", "--force", path], cwd=cwd)
    shutil.rmtree(path, ignore_errors=True)
