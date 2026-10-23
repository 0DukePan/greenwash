"""History miners R1 and R2: candidate cases read as git objects only.

The miner proposes cases for the labelers; it never judges one. It walks a
repository's history as git objects -- `rev-list`, `ls-tree` and `cat-file`
and nothing else -- and writes unadjudicated candidate records in the corpus
kit's case-record-v2 shape. A human labels them later; nothing here may enter
a gate before it is adjudicated.

The two collection routes:

* **R1, structural queries.** A commit that changes an assertion, deletes a
  test or adds a skip *alongside a source change* is proposed with the
  taxonomy technique its edit looks like: `expected-value-change` when the
  only assertion edits are literal changes, `assertion-weakened` when an
  assertion line is removed or replaced, `deleted-test` when a test file or
  test function disappears, `skip-or-xfail` when skip machinery appears.
* **R2, reverts and regressions.** An edit later reverted (a `git revert`
  message, or a patch that exactly reverses the edit) or fixed by a linked
  commit (a later message that references the edit's commit and reads like a
  fix) is proposed with that later history attached as `supporting_history`.
  R2 also picks up weakening edits R1's alongside-a-source-change rule
  misses. When an edit matches both routes the record carries R2 -- the
  route whose contract is that history evidence supports the label -- and
  the evidence travels with it.

Every candidate carries `route`, `repository`, `license`, `base_ref`,
`head_ref`, a `diff_hash` and the `technique` it looks like. `diff_hash` is
sha256 over the canonical change set -- sorted `(status, path, modes, object
ids)` tuples -- which binds the diff exactly because every blob is
content-addressed. `label` is the miner's proposal ("what it looks like");
`labels` is never written here, so `Case.adjudicated` stays None and
`gate_admission_issues` refuses the record as unadjudicated.

The repository is hostile input and is treated exactly as the corpus kit
treats it -- but here git itself must read history, so the contract is
stronger in one place and identical everywhere else:

* **Git-object reads only.** Three plumbing commands run: `rev-list`,
  `ls-tree`, `cat-file`. No checkout, no diff machinery, no index, no
  hooks, no filters, no external diff, no textconv -- nothing that can
  execute repository code. Every call runs with repository-supplied git
  configuration ignored: the `GIT_*` environment is scrubbed (global and
  system config disabled) and the remaining surfaces (`core.hooksPath`,
  `core.fsmonitor`, `core.pager`, `diff.external`) are pinned on the command
  line, so the output cannot move with a hostile `.git/config`.
* **Paths are data and this data is hostile.** Every path a tree names is
  checked by the corpus kit's `_safe_path` before anything reads it:
  control characters, absolute paths, `.git` internals and paths that escape
  the work tree are rejected naming the path.
* **Bounded input.** Commits scanned, changed paths per commit, blob bytes
  and supporting-history entries are all bounded (`MAX_COMMITS`, `MAX_FILES`,
  `MAX_FILE_BYTES`, `MAX_SUPPORTING`); a run past a bound is a rejection
  naming the field, never a silent truncation.

The seam, callable without any CLI:

    candidates = mine_history(work_tree, repository=..., license=...)
    write_candidates(corpus_root, candidates)   # unadjudicated records

This module extends the corpus kit rather than restating it: `EvidenceError`
comes from `greenwash.evidence`, path safety from `greenwash.corpus`, the
empty tree from `greenwash.gitutil`, techniques from `greenwash.taxonomy`.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from greenwash import corpus
from greenwash.evidence import EvidenceError
from greenwash.gitutil import EMPTY_TREE

MAX_COMMITS = 500            # commits scanned per mining run
MAX_FILES = corpus.MAX_FILES            # changed paths per commit
MAX_FILE_BYTES = corpus.MAX_FILE_BYTES  # bytes of any blob read
MAX_SUPPORTING = 10          # supporting-history entries per candidate

# -- the shapes an edit can have, and the technique each one looks like ------

WEAKENING_ORDER = ("deleted-test", "skip-or-xfail", "assertion-weakened",
                   "expected-value-change")

_ASSERTION = re.compile(r"^\s*assert\b|\bassert\w*\s*\(")
_SKIP = re.compile(r"pytest\.mark\.(?:skip|xfail)|unittest\.skip|"
                   r"unittest\.expectedFailure|\bskipTest\b|pytest\.skip\(|"
                   r"pytestmark")
_TEST_DEF = re.compile(r"^\s*(?:async\s+)?def\s+test\w*|^\s*class\s+Test\w*")
_LITERAL = re.compile(r"\d+(?:\.\d+)?|\"[^\"]*\"|'[^']*'")

_TEST_DIRS = ("tests", "test", "__tests__")
_RUNNER_CONFIGS = {"pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml",
                   "noxfile.py"}
_GATE_HOOKS = {"action.yml", "action.yaml", ".pre-commit-config.yaml",
               ".pre-commit-hooks.yaml"}

# -- R2's linkage: what a later commit's message must look like --------------

_REVERT_LINE = re.compile(r"this reverts commit ([0-9a-f]{7,40})", re.I)
_HEX_TOKEN = re.compile(r"[0-9a-f]{7,40}")
_FIX_WORDS = re.compile(r"\b(fix\w*|patch\w*|repair\w*|correct\w*|bug\w*|"
                        r"regression|broken|wrong)\b", re.I)


# -- one git object read: plumbing only, repository config ignored -----------

def _git(args, cwd) -> bytes:
    """Run one plumbing read and return its raw bytes.

    `rev-list`, `ls-tree` and `cat-file` read git objects and can execute
    nothing: no hooks, no filters, no external diff, no textconv, no index.
    The environment is scrubbed of `GIT_*` and global and system git
    configuration are disabled outright, and the surfaces a repository's own
    `.git/config` could still reach are pinned here, so repository-supplied
    git configuration is never honored. Failures raise `EvidenceError`; the
    miner never falls back to a default.
    """
    env = {name: value for name, value in os.environ.items()
           if not name.startswith("GIT_")}
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_PAGER": "cat",
    })
    pins = ["-c", f"core.hooksPath={os.devnull}",
            "-c", "core.fsmonitor=false",
            "-c", "core.pager=cat",
            "-c", "diff.external="]
    try:
        result = subprocess.run(["git", *pins, *args], cwd=str(cwd),
                                capture_output=True, env=env, check=False)
    except FileNotFoundError as exc:            # pragma: no cover - host
        raise EvidenceError("git not found on PATH") from exc
    if result.returncode != 0:
        raise EvidenceError(f"git {args[0]} failed: "
                            f"{result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout


def _commits(work: Path, start, end) -> list:
    args = ["rev-list", "--topo-order", "--reverse", str(end)]
    if start:
        args += ["--not", str(start)]
    shas = [line for line in _git(args, work).decode("ascii").splitlines()
            if line]
    if len(shas) > MAX_COMMITS:
        raise EvidenceError(f"commits: {len(shas)} commits in the mined range, "
                            f"above the {MAX_COMMITS}-commit bound; history "
                            "mining is bounded input")
    return shas


def _parents(work: Path, sha: str) -> list:
    words = _git(["rev-list", "--parents", "-n", "1", sha], work) \
        .decode("ascii").split()
    return words[1:]


def _tree(work: Path, ref: str) -> dict:
    """One tree as `path -> (mode, object id)`, blob entries only.

    `-z` output is raw, so a hostile tree name is seen exactly as stored --
    quoting and `core.quotePath` cannot hide a path from the checks below.
    """
    out: dict = {}
    for entry in _git(["ls-tree", "-r", "-z", ref], work).split(b"\0"):
        if not entry:
            continue
        meta, name = entry.split(b"\t", 1)
        mode, kind, oid = meta.split(b" ")
        if kind != b"blob":
            continue
        try:
            path = name.decode("utf-8")
        except UnicodeDecodeError:
            raise EvidenceError(f"path: {name!r} is not valid UTF-8; a case "
                                "path is plain text") from None
        out[path] = (mode.decode("ascii"), oid.decode("ascii"))
    return out


def _changes(work: Path, base, sha: str) -> list:
    """The commit's change set as `(status, path, base, head)` tuples.

    Sorted by path, so the diff hash below is canonical. Every path passes
    the corpus kit's `_safe_path` before any of it is read: a tree name that
    escapes the work tree, is absolute, is `.git` internals or carries
    control characters is rejected naming the path.
    """
    before = _tree(work, base) if base else {}
    after = _tree(work, sha)
    changes = []
    for path in sorted(set(before) | set(after)):
        old, new = before.get(path), after.get(path)
        if old == new:
            continue
        corpus._safe_path(work, path)
        status = "A" if old is None else ("D" if new is None else "M")
        changes.append((status, path,
                        old[0] if old else "", old[1] if old else "",
                        new[0] if new else "", new[1] if new else ""))
    return changes


def _blob(work: Path, oid: str, path: str) -> bytes:
    """One blob's bytes, bounded before a single byte is read."""
    size = int(_git(["cat-file", "-s", oid], work).decode("ascii").strip())
    if size > MAX_FILE_BYTES:
        raise EvidenceError(f"files: {path} is {size} bytes, above the "
                            f"{MAX_FILE_BYTES}-byte bound; a mined case is "
                            "bounded input")
    return _git(["cat-file", "blob", oid], work)


def _message(work: Path, sha: str) -> str:
    raw = _git(["cat-file", "commit", sha], work)
    _headers, _, body = raw.partition(b"\n\n")
    return body.decode("utf-8", "replace")


# -- the shapes: which technique does this edit look like? -------------------

def _name(path: str) -> str:
    return path.rsplit("/", 1)[-1].lower()


def _is_test_path(path: str) -> bool:
    name = _name(path)
    parts = path.lower().split("/")[:-1]
    return (name.startswith("test_") or name.endswith("_test.py")
            or any(part in _TEST_DIRS for part in parts))


def _is_conftest(path: str) -> bool:
    return _name(path) == "conftest.py"


def _is_runner_config(path: str) -> bool:
    return (_name(path) in _RUNNER_CONFIGS
            or path.lower().startswith(".github/workflows/"))


def _is_gate_hook(path: str) -> bool:
    return (path.lower().startswith("hooks/")
            or _name(path) in _GATE_HOOKS)


def _is_report(path: str) -> bool:
    name = _name(path)
    return "report" in name or "verdict" in name


def _is_source_path(path: str) -> bool:
    return (path.lower().endswith(".py")
            and not _is_test_path(path) and not _is_conftest(path)
            and not _is_runner_config(path) and not _is_gate_hook(path)
            and not _is_report(path))


def _changed_lines(base: bytes, head: bytes) -> tuple:
    def lines(raw):
        return raw.decode("utf-8", "replace").splitlines()
    removed: list = []
    added: list = []
    matcher = difflib.SequenceMatcher(None, lines(base), lines(head),
                                      autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("delete", "replace"):
            removed.extend(lines(base)[i1:i2])
        if tag in ("insert", "replace"):
            added.extend(lines(head)[j1:j2])
    return removed, added


def _normalized(line: str) -> str:
    return _LITERAL.sub("X", line).strip()


def _weakening(work: Path, changes: list):
    """The weakening technique the diff looks like, or None.

    Structural queries over test paths only: a deleted test file or test
    definition, skip machinery in added lines, and assertion lines removed
    (assertion-weakened) or changed only in their literals
    (expected-value-change).
    """
    signals = set()
    for status, path, _bmode, boid, _hmode, hoid in changes:
        if not _is_test_path(path):
            continue
        if status == "D":
            signals.add("deleted-test")
            continue
        base = _blob(work, boid, path) if boid else b""
        head = _blob(work, hoid, path) if hoid else b""
        removed, added = _changed_lines(base, head)
        if any(_SKIP.search(line) for line in added):
            signals.add("skip-or-xfail")
        if any(_TEST_DEF.search(line) for line in removed):
            signals.add("deleted-test")
        removed_asserts = [line for line in removed if _ASSERTION.search(line)]
        added_norms = {_normalized(line) for line in added
                       if _ASSERTION.search(line)}
        if any(_normalized(line) not in added_norms for line in removed_asserts):
            signals.add("assertion-weakened")
        elif removed_asserts:
            signals.add("expected-value-change")
    for technique in WEAKENING_ORDER:
        if technique in signals:
            return technique
    return None


def _edit_shape(changes: list):
    """The configuration-shape technique the edited paths look like, or None."""
    paths = [change[1] for change in changes]
    for predicate, technique in ((_is_conftest, "conftest-edit"),
                                 (_is_runner_config, "runner-config-tamper"),
                                 (_is_gate_hook, "gate-hook-tamper"),
                                 (_is_report, "report-tamper")):
        if any(predicate(path) for path in paths):
            return technique
    return None


def _diff_hash(changes: list) -> str:
    payload = b"".join(
        b"\0".join([status.encode("ascii"), path.encode("utf-8"),
                    bmode.encode("ascii"), boid.encode("ascii"),
                    hmode.encode("ascii"), hoid.encode("ascii")]) + b"\0"
        for status, path, bmode, boid, hmode, hoid in changes)
    return hashlib.sha256(payload).hexdigest()


# -- R2: what later history reverts the edit or fixes it? --------------------

def _subject(message: str) -> str:
    return message.splitlines()[0] if message.strip() else ""


def _references(message: str, sha: str) -> bool:
    return any(sha.startswith(token)
               for token in _HEX_TOKEN.findall(message.lower()))


def _reverses(later: list, earlier: list) -> bool:
    """True when `later`'s change set is exactly `earlier`'s, reversed.

    Object ids decide, so a revert written without `git revert`'s message is
    still seen -- and a partial undo is not claimed as one.
    """
    if not earlier or {c[1] for c in later} != {c[1] for c in earlier}:
        return False
    before = {path: (bmode, boid, hmode, hoid)
              for _s, path, bmode, boid, hmode, hoid in earlier}
    after = {path: (bmode, boid, hmode, hoid)
             for _s, path, bmode, boid, hmode, hoid in later}
    return all(after[path][:2] == before[path][2:]
               and after[path][2:] == before[path][:2] for path in before)


def _evidence_kind(entry: dict, later: dict):
    """How a later commit supports the edit: `revert`, `linked-fix` or None.

    A revert is `git revert`'s message naming the edit, a Revert-prefixed
    subject that names it, or a patch that exactly reverses it. A linked fix
    is a later message that names the edit's commit and reads like a fix. A
    bare reference -- "see <sha>" -- is linked but is not a fix, so it is not
    evidence.
    """
    sha = entry["sha"]
    lower = later["message"].lower()
    for match in _REVERT_LINE.finditer(lower):
        if sha.startswith(match.group(1)):
            return "revert"
    if _subject(lower).startswith("revert") and _references(lower, sha):
        return "revert"
    if _reverses(later["changes"], entry["changes"]):
        return "revert"
    if _references(lower, sha) and _FIX_WORDS.search(lower):
        return "linked-fix"
    return None


def _supporting(scanned: list) -> dict:
    out: dict = {}
    for index, entry in enumerate(scanned):
        entries = []
        for later in scanned[index + 1:]:
            kind = _evidence_kind(entry, later)
            if kind:
                entries.append({"kind": kind, "commit": later["sha"],
                                "subject": _subject(later["message"])})
        if len(entries) > MAX_SUPPORTING:
            raise EvidenceError(
                f"supporting_history: {len(entries)} later commits support "
                f"{entry['sha'][:12]}, above the {MAX_SUPPORTING}-entry bound; "
                "a mined case is bounded input")
        out[entry["sha"]] = entries
    return out


# -- the seam ----------------------------------------------------------------

def mine_history(work_tree, *, repository, license, start=None, end="HEAD",
                 split="dev") -> tuple:
    """Unadjudicated candidate records mined from repository history.

    Reads the history of `work_tree` as git objects only -- the repository's
    code, hooks, filters and git configuration are never executed or honored
    -- and proposes one record per suspicious commit, oldest first. R1
    proposes commits that change an assertion, delete a test or add a skip
    alongside a source change; R2 proposes edits later reverted or fixed by
    a linked commit and attaches that later history as `supporting_history`.

    The miner fills every field it can and rejects what it cannot: a missing
    `repository` identity or `license` is a rejection naming the field, never
    a default. Candidates carry `label: "tampered"` as the miner's proposal
    of what the edit looks like and never a `labels` block, so every written
    record is unadjudicated and `gate_admission_issues` refuses it.
    """
    work = Path(work_tree)
    for field, value in (("repository", repository), ("license", license)):
        if not str(value or "").strip():
            raise EvidenceError(f"{field}: missing; a mined candidate must "
                                f"carry {field}")
    shas = _commits(work, start, end)
    scanned = []
    for sha in shas:
        parents = _parents(work, sha)
        base = parents[0] if parents else EMPTY_TREE
        changes = _changes(work, base, sha)
        if len(changes) > MAX_FILES:
            raise EvidenceError(f"files: {len(changes)} changed paths in "
                                f"{sha[:12]}, above the {MAX_FILES}-path bound; "
                                "a mined case is bounded input")
        weakening = _weakening(work, changes)
        scanned.append({
            "sha": sha,
            "base": base,
            "changes": changes,
            "message": _message(work, sha),
            "technique": weakening or _edit_shape(changes),
            "has_source": any(_is_source_path(path) for _s, path, *_ in changes),
            "weakening": weakening,
        })
    supporting = _supporting(scanned)
    records = []
    for entry in scanned:
        technique = entry["technique"]
        if technique is None:
            continue
        evidence = supporting[entry["sha"]]
        r1 = entry["weakening"] is not None and entry["has_source"]
        if evidence:
            route = "R2"
        elif r1:
            route = "R1"
        else:
            continue
        records.append(_record(entry, route, evidence, split,
                               repository, license))
    return tuple(records)


def _record(entry: dict, route: str, supporting: list, split: str,
            repository: str, license: str) -> dict:
    sha = entry["sha"]
    return {
        "id": f"{route}-{sha[:12]}",
        "source": "history: mined from repository history as git objects",
        "technique": entry["technique"],
        "label": "tampered",
        "split": split,
        "task": f"commit:{sha}",
        "repository": repository,
        "license": license,
        "route": route,
        "base_ref": entry["base"],
        "head_ref": sha,
        "diff_hash": _diff_hash(entry["changes"]),
        "supporting_history": list(supporting),
    }


def write_candidates(root, records) -> tuple:
    """Candidate records as JSON case files -- unadjudicated, always.

    One file per record, named by the record's id. A record that does not
    validate is a rejection naming the field, and a record that carries a
    `labels` or `axes` block is refused the same way: mining proposes, the
    label workflow labels, and a record written here can never look
    adjudicated before a human has looked at it.
    """
    root = Path(root)
    records = list(records)
    issues = list(corpus.validate_cases(records))
    for record in records:
        name = str(record.get("id") or "?")
        for field in ("labels", "axes"):
            if record.get(field):
                issues.append(f"{name}: {field}: a mined candidate is written "
                              f"unadjudicated; the label workflow fills "
                              f"{field}")
    if issues:
        raise EvidenceError("; ".join(issues))
    written = []
    for record in records:
        file_name = f"{record['id']}.json"
        (root / file_name).write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        written.append(file_name)
    return tuple(written)
