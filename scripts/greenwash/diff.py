"""git diff plumbing: fetch, parse (with new-file line numbers), file helpers."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Optional


def run_git_diff(staged: bool, base: Optional[str]) -> str:
    # Register brand-new, never-`git add`-ed files as "intent to add" so they
    # show up in the diff at all -- otherwise a freshly created conftest.py or
    # cheat-y test file is invisible to `git diff` until someone stages it.
    subprocess.run(["git", "add", "-N", "-A"], capture_output=True, text=True)

    if base:
        cmd = ["git", "diff", f"{base}...HEAD"]
    elif staged:
        cmd = ["git", "diff", "--staged"]
    else:
        cmd = ["git", "diff", "HEAD"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        sys.exit("greenwash: git not found on PATH")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"greenwash: git diff failed:\n{exc.stderr}")
    return result.stdout


def parse_diff(diff_text: str):
    """Return (files, deleted).

    files maps path -> {"added": [str], "removed": [str], "added_lines": set[int]}
    where added_lines are 1-indexed line numbers in the *new* file, so AST
    checks can tell whether a node was introduced by this diff.
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


def find_related_test_files(impl_path: str) -> list:
    stem, ext = os.path.splitext(os.path.basename(impl_path))
    dirname = os.path.dirname(impl_path)
    guesses = [
        os.path.join(dirname, f"test_{stem}{ext}"),
        os.path.join(dirname, f"{stem}_test{ext}"),
        os.path.join(dirname, f"{stem}.test{ext}"),
        os.path.join(dirname, f"{stem}.spec{ext}"),
        os.path.join(dirname, "tests", f"test_{stem}{ext}"),
        os.path.join(dirname, "tests", f"{stem}_test{ext}"),
        os.path.join("tests", f"test_{stem}{ext}"),
        os.path.join("tests", f"{stem}_test{ext}"),
        os.path.join("test", f"test_{stem}{ext}"),
        os.path.join("__tests__", f"{stem}{ext}"),
    ]
    return [g for g in guesses if os.path.isfile(g)]


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""
