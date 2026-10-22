"""Verifier integrity: the checker's own inputs, pinned outside the sandbox.

The diff under inspection is untrusted input, and so is everything an agent can
write inside the working tree -- including the files the verifier reads to
decide what gets checked and what may pass. Three classes of input are pinned
at the base ref (in CI, the merge target) and hash-verified before use:

  checker   greenwash's own code as tracked in this repository -- the self-check
            case. When the checker runs from outside the repository it is
            outside the sandbox entirely, and that is recorded instead.
  config    `.greenwash/config.json`, the policy that decides the gate.
  pinned    the test files the verification replays as "the original tests".

A checker or config copy that does not match its pin is an integrity failure:
the run stops before any verdict and exits with its own code, because a verdict
produced through a modified checker or a modified policy is not a verdict about
the diff. Two shapes are refused per class: a *changed* pin (edited or deleted
working copy) always, and for checker code also a copy that *appeared* where
the base ref had none -- code the diff introduced cannot be the judge of the
diff. A config that appears mid-session is the one deliberate exception: it is
honoured and flagged by `verifier-config-changed` (existing contract: an added
config is a decision to review, and it cannot move a pinned policy because a
pinned policy that moved stops the run first).

An edited or deleted pinned test is detected before the run starts and
reported, but never fatal: a test edit is diff content for the verdict to judge
(test-weakened, test-deleted), never a moved pin. What counts as evidence is
the copy at the base ref, and the report says so with its digest.

This is a guard, not a security boundary. An agent with git access can rewrite
the base ref as well; what it cannot do is change what this run pins without
that change being visible in the report.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

from . import gitutil
from .verify.integrity import test_side

CONFIG_PATH = ".greenwash/config.json"
CHECKER_PREFIX = "greenwash/"
CHECKER_PATHS = ("scripts/greenwash_check.py", "scripts/greenwash_hook.py")
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache"}
SKIP_SUFFIXES = (".pyc", ".pyo")


def _normalized(content):
    """Newline-normalised bytes, or None.

    A checkout's CRLF translation is not a modification: what git stored is
    the same text, so digests are taken over normalised newlines and a
    line-ending-only difference never fails a pin.
    """
    if content is None:
        return None
    return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _digest(content) -> str:
    content = _normalized(content)
    return "sha256:" + hashlib.sha256(content).hexdigest() if content is not None else ""


@dataclass
class GuardedFile:
    """One pinned input, and what became of its working copy."""

    path: str = ""
    role: str = ""                        # checker | config | pinned test
    pinned_sha256: str = ""               # "" when the base ref has no copy
    working_sha256: str = ""
    state: str = "absent"                 # match | edited | deleted | added | absent

    @property
    def fatal(self) -> bool:
        """Whether this divergence stops the run before any verdict.

        A test edit is judged as diff content, so it is never fatal here; a
        checker or config that moved from under the run always is.
        """
        if self.state in ("match", "absent") or self.role == "pinned test":
            return False
        if self.state == "added":
            return self.role == "checker"
        return True                       # edited or deleted

    def to_dict(self) -> dict:
        return {"path": self.path, "role": self.role, "state": self.state,
                "pinned_sha256": self.pinned_sha256,
                "working_sha256": self.working_sha256}


@dataclass
class GuardReport:
    """What was pinned, what diverged, and what that means for the run."""

    base_ref: str = ""
    files: list = field(default_factory=list)
    pinned: bool = True                   # False: no usable base ref to pin at

    @property
    def failures(self) -> list:
        return [f for f in self.files if f.fatal]

    @property
    def problems(self) -> list:
        return [f"{f.path} ({f.role}): {f.state} since the base ref"
                for f in self.failures]

    def notices(self) -> list:
        """Divergences detected before the run starts, one sentence each.

        Quiet when nothing moved: an honest diff earns no commentary.
        """
        out = []
        for f in self.files:
            if f.role == "pinned test" and f.state in ("edited", "deleted"):
                out.append(
                    f"verifier integrity: {f.path} is {f.state} in the working tree -- "
                    f"the pinned original at the base ref is what counts as evidence "
                    f"({f.pinned_sha256})")
        return out

    def notes(self) -> list:
        return self.notices()

    def to_dict(self) -> dict:
        return {"base_ref": self.base_ref, "pinned": self.pinned,
                "files": [f.to_dict() for f in self.files],
                "problems": self.problems}


def _working_bytes(root: str, path: str):
    try:
        with open(os.path.join(root, *path.split("/")), "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _guarded(path: str, role: str, base_ref: str, root: str) -> GuardedFile:
    pinned = _normalized(gitutil.show_bytes(base_ref, path, cwd=root))
    working = _normalized(_working_bytes(root, path))
    entry = GuardedFile(path=path, role=role,
                        pinned_sha256=_digest(pinned),
                        working_sha256=_digest(working))
    if pinned is None and working is None:
        entry.state = "absent"
    elif pinned is None:
        entry.state = "added"
    elif working is None:
        entry.state = "deleted"
    elif pinned == working:
        entry.state = "match"
    else:
        entry.state = "edited"
    return entry


def _checker_paths(base_ref: str, root: str) -> list:
    """Checker code in this repository: the base ref's copy plus the working tree.

    Both sides matter. A file deleted from the working tree is still a modified
    checker, and one the diff introduced cannot be allowed to judge the diff.
    """
    found = set()
    for rel in gitutil.tree_files(base_ref, ("greenwash", "scripts"), cwd=root):
        rel = rel.replace("\\", "/")
        if rel.startswith(CHECKER_PREFIX) or rel in CHECKER_PATHS:
            found.add(rel)
    package = os.path.join(root, "greenwash")
    for current, dirs, names in os.walk(package):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if name.endswith(SKIP_SUFFIXES):
                continue
            rel = os.path.relpath(os.path.join(current, name), root).replace("\\", "/")
            found.add(rel)
    for rel in CHECKER_PATHS:
        if _working_bytes(root, rel) is not None:
            found.add(rel)
    return sorted(found)


def check(base_ref: str, changes=None, cwd=None) -> GuardReport:
    """Hash-verify the verifier's inputs against the base ref, before the run.

    `changes` is the diff's change list; its test-side files are the pinned
    originals the verification will judge against. Returns the report; the
    caller refuses to produce a verdict when `failures` is non-empty.
    """
    root = cwd or "."
    if not base_ref or base_ref == gitutil.EMPTY_TREE \
            or not gitutil.object_exists(base_ref, cwd=root):
        return GuardReport(base_ref=base_ref or "", files=[], pinned=False)

    files = [_guarded(CONFIG_PATH, "config", base_ref, root)]
    for path in _checker_paths(base_ref, root):
        files.append(_guarded(path, "checker", base_ref, root))
    for change in (changes or []):
        path = change.path.replace("\\", "/")
        if test_side(path):
            files.append(_guarded(path, "pinned test", base_ref, root))
    return GuardReport(base_ref=base_ref, files=files, pinned=True)


def describe_failure(report: GuardReport) -> str:
    """The loud block: what failed to verify, and what it is not."""
    lines = ["greenwash: verifier integrity failure -- the run stops before any verdict"]
    for f in report.failures:
        lines.append(f"  {f.path} ({f.role}): {f.state} since the base ref "
                     f"{report.base_ref[:12]}")
        lines.append(f"      pinned   {f.pinned_sha256 or '(absent)'}")
        lines.append(f"      working  {f.working_sha256 or '(absent)'}")
    lines.append(NOT_A_VERDICT)
    return "\n".join(lines)


NOT_A_VERDICT = ("this is not a verdict about the diff: the checker's own inputs did not "
                 "match their pinned copies at the base ref, so nothing about the change "
                 "was judged.")


def failure_payload(report: GuardReport) -> dict:
    """The same refusal as JSON -- with no verdict field, deliberately."""
    return {"schema_version": "1", "integrity": "failure",
            "base_ref": report.base_ref, "problems": report.problems,
            "files": [f.to_dict() for f in report.files],
            "note": NOT_A_VERDICT}


__all__ = ["check", "describe_failure", "failure_payload", "GuardReport", "GuardedFile",
           "CONFIG_PATH", "NOT_A_VERDICT"]
