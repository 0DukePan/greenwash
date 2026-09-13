"""Diff analysis: turn a diff into `Signal[]`.

The engine does three things and nothing else: build the diff, gather the
context rules need (asserted literals, parsed modules), and run the registry.
All judgement lives in `rules/`, one file per rule.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from .. import gitutil
from ..domain import FileChange
from .languages.packs import is_test_file, literals_from_text
from .rules import run_all
from .rules.base import ScanContext

# Above this, module parsing is threaded: a 500-file diff otherwise spends its
# whole budget parsing one file at a time on a cold cache.
THREAD_THRESHOLD = 40


def build_context(diff_text: str, cwd: Optional[str] = None,
                  root: Optional[str] = None) -> ScanContext:
    """Gather what the rules need.

    Diff paths from git are relative to the *repository root*, whatever
    directory we were invoked from, so module parsing and the related-test
    lookup resolve against that root rather than the process directory.
    A caller whose diff paths are relative to something else -- the benchmark's
    synthetic corpus, for instance -- passes `root` explicitly.
    """
    files, deleted = gitutil.parse_diff(diff_text)
    if root is None:
        root = gitutil.repo_root(cwd) or (cwd or "")
    ctx = ScanContext(files=files, deleted=deleted, diff_text=diff_text,
                      root="" if root in ("", ".") else root)

    literals: set = set()
    for hunks in files.values():
        literals |= literals_from_text("\n".join(hunks["added"]))
    for path in files:
        if is_test_file(path):
            continue
        for related in gitutil.find_related_test_files(path, ctx.root or None):
            literals |= literals_from_text(gitutil.read_text(related))
    ctx.asserted_literals = literals

    python_paths = [p for p in files if ctx.language(p) == "python"]
    if len(python_paths) >= THREAD_THRESHOLD:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(ctx.module, python_paths))
    for path in python_paths:
        ctx.module(path)          # warm the cache sequentially at normal sizes
    return ctx


def scan_diff(diff_text: str, cwd: Optional[str] = None,
              root: Optional[str] = None) -> list:
    """Score one diff."""
    if not diff_text.strip():
        return []
    return run_all(build_context(diff_text, cwd, root))


def scan(staged: bool = False, base: Optional[str] = None,
         cwd: Optional[str] = None) -> list:
    """Score the working tree's diff against HEAD (or a base ref)."""
    return scan_diff(gitutil.diff(staged=staged, base=base, cwd=cwd), cwd)


def summarize(diff_text: str) -> tuple:
    """(changes, deleted) for the report header -- no rules involved."""
    files, deleted = gitutil.parse_diff(diff_text)
    return gitutil.change_list(files, deleted), deleted


__all__ = ["scan", "scan_diff", "build_context", "summarize", "FileChange"]
