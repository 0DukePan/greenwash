"""Twin matching: one positive, one legitimate twin of the same surface shape.

A twin is the realistic neighbor a false-alarm rate is measured against
(docs/specs/validation-program.md, user story 16): a legitimate edit with the
same AST-level edit class and a diff size close to the positive's. The match
is recorded as a `TwinPair` carrying the similarity score, and
`TwinPair.linked_records` stamps `twin_id` and `similarity` onto both case
records (the case-record-v2 fields `greenwash.corpus` already validates).

The contracts, each one load-bearing:

* **Same AST-level edit class.** `edit_classes` reads a unified diff and
  classifies each changed statement through `ast.parse` -- a changed
  `assert X == literal`, a deleted test function, a rewritten docstring, a
  changed constant, a new skip marker -- never a raw text match. A pair
  requires the two diffs' class sets to be identical.
* **Diff-size proximity.** `size_similarity` is `1 - |a - b| / max(a, b)` over
  changed-line counts; a pair requires at least `MIN_SIMILARITY`, so a
  two-line edit is never paired with a twenty-line one. The score of a pair is
  exactly this proximity: the edit class already matches exactly.
* **Never across repositories.** A candidate from another repository is never
  a twin; the pairing is refused naming `repository`.
* **Never a synthetic record.** A synthetic injected tamper -- `origin:
  synthetic` or a `synthetic:` / `planted` source category -- is never a twin,
  and neither is a record that is not legitimate (`label` other than
  `greenwash.corpus.CLEAN`).
* **Fail closed, naming the field.** A missing or empty diff, a non-legitimate
  candidate, a foreign repository, a synthetic record, a foreign edit class
  or a size outside the window is a `TwinError` naming the field. When no
  candidate survives, the refusal lists every candidate's first refusal.

The runner's seam, all callable without a CLI:

    pair = match_twin(positive, candidates, diffs)   # diffs: id -> diff text
    classes = edit_classes(diff_text)                # the AST-level shape
    linked = pair.linked_records(positive, twin)     # records with the score

This module rides on the corpus kit rather than restating it: record fields
are read without prejudice (a mapping or a `Case`), and the linked records
carry `twin_id` and `similarity` exactly as `greenwash.corpus.validate_case`
checks them.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from greenwash.corpus import CLEAN, EXTENDED, FIELDS, NON_GATE_SOURCES

#: The edit classes `edit_classes` can name, sorted as reported.
EDIT_CLASSES = ("assert-added", "assert-deleted", "constant-change",
                "docstring-rewrite", "expected-value", "skip-added",
                "statement-change", "test-deleted", "unknown")

#: A pair needs at least this size proximity: the larger diff at most twice
#: the smaller one.
MIN_SIMILARITY = 0.5

HUNK = re.compile(r"^diff --git a/(\S+) b/(\S+)")
DEF_TEST = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)\s*\(")
SKIP_ATTRS = ("skip", "skipif", "skipUnless", "skipIf", "xfail")


class TwinError(ValueError):
    """A pairing cannot be made. Rejected by name, never defaulted: a twin
    that is not a same-repository, legitimate, same-shape neighbor would make
    the false-alarm rate measure nothing."""


# -- reading a record without prejudice --------------------------------------

def _field(entry, name):
    if isinstance(entry, Mapping):
        return entry.get(name)
    return getattr(entry, name, None)


def _as_dict(entry) -> dict:
    if isinstance(entry, Mapping):
        return dict(entry)
    return {field: getattr(entry, field, None) for field in FIELDS + EXTENDED}


def _is_synthetic(entry) -> str | None:
    """The named refusal when a record is by-construction material, else None."""
    if _field(entry, "origin") == "synthetic":
        return ("origin: a synthetic injected tamper; a synthetic record is "
                "never a twin")
    category = str(_field(entry, "source") or "").split(":", 1)[0].strip().lower()
    if category in NON_GATE_SOURCES:
        return (f"source: a {category} by-construction record; a {category} "
                "record is never a twin")
    return None


# -- the AST-level edit class of a diff --------------------------------------

def _changed_lines(diff_text: str) -> dict:
    """{path: (removed, added)} of changed source lines, headers excluded."""
    per_path: dict = {}
    path = ""
    for line in (diff_text or "").splitlines():
        hunk = HUNK.match(line)
        if hunk:
            path = hunk.group(2)
            per_path.setdefault(path, ([], []))
            continue
        if not path:
            continue
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            per_path[path][0].append(line[1:])
        elif line.startswith("+"):
            per_path[path][1].append(line[1:])
    return per_path


def diff_size(diff_text: str) -> int:
    """Changed lines (added plus removed) in the diff."""
    per_path = _changed_lines(diff_text)
    return sum(len(removed) + len(added)
               for removed, added in per_path.values())


def _parse_stmt(line: str):
    """One changed source line as an AST statement, or None.

    A line ending in a colon is completed with a `pass` body so `def` and
    `class` headers parse; anything that will not parse returns None and is
    classified `unknown` rather than guessed at.
    """
    text = line.strip()
    if not text:
        return None
    if text.endswith(":"):
        text += "\n    pass"
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    body = tree.body
    return body[0] if len(body) == 1 else None


def _assert_constant(node):
    """(target dump, constant repr) for `assert X == literal`, else None."""
    if not isinstance(node, ast.Assert):
        return None
    test = node.test
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)):
        return None
    return ast.dump(test.left), repr(test.comparators[0].value)


def _assign_constant(node):
    """(target name, constant repr) for `NAME = literal`, else None."""
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return None
    target = node.targets[0]
    if not isinstance(target, ast.Name) or not isinstance(node.value,
                                                          ast.Constant):
        return None
    return target.id, repr(node.value.value)


def _is_docstring(node) -> bool:
    return (isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str))


def _is_skip(node) -> bool:
    if node is None:
        return False
    for part in ast.walk(node):
        if isinstance(part, ast.Attribute) and part.attr in SKIP_ATTRS:
            return True
    return False


def _classify_path(removed: list, added: list) -> set:
    """The edit classes of one file's changed lines.

    Removed test-function deletions swallow their indented body, so a deleted
    test is one `test-deleted` unit instead of a pile of deleted asserts.
    """
    classes: set = set()
    removed_nodes = [(line, _parse_stmt(line)) for line in removed]
    added_nodes = [(line, _parse_stmt(line)) for line in added]
    consumed_removed = [False] * len(removed_nodes)
    consumed_added = [False] * len(added_nodes)

    # expected-value: `assert X == a` removed and `assert X == b` added
    removed_asserts: dict = {}
    for index, (_, node) in enumerate(removed_nodes):
        pair = _assert_constant(node)
        if pair:
            removed_asserts.setdefault(pair[0], []).append((index, pair[1]))
    for jndex, (_, node) in enumerate(added_nodes):
        pair = _assert_constant(node)
        if not pair:
            continue
        pending = removed_asserts.get(pair[0])
        if pending:
            index, old = pending.pop(0)
            if old != pair[1]:
                classes.add("expected-value")
            else:
                classes.add("statement-change")
            consumed_removed[index] = True
            consumed_added[jndex] = True

    # constant-change: `NAME = a` removed and `NAME = b` added
    removed_assigns: dict = {}
    for index, (_, node) in enumerate(removed_nodes):
        if consumed_removed[index]:
            continue
        pair = _assign_constant(node)
        if pair:
            removed_assigns.setdefault(pair[0], []).append((index, pair[1]))
    for jndex, (_, node) in enumerate(added_nodes):
        if consumed_added[jndex]:
            continue
        pair = _assign_constant(node)
        if not pair or pair[0] not in removed_assigns:
            continue
        index, old = removed_assigns[pair[0]].pop(0)
        classes.add("constant-change" if old != pair[1] else "statement-change")
        consumed_removed[index] = True
        consumed_added[jndex] = True

    # test-deleted: a removed `def test_*` with its indented body
    for index, (line, _) in enumerate(removed_nodes):
        if consumed_removed[index] or not DEF_TEST.match(line):
            continue
        indent = len(line) - len(line.lstrip())
        consumed_removed[index] = True
        classes.add("test-deleted")
        for after in range(index + 1, len(removed_nodes)):
            if consumed_removed[after]:
                continue
            body_line = removed[after]
            body_indent = len(body_line) - len(body_line.lstrip())
            if body_line.strip() and body_indent <= indent:
                break
            consumed_removed[after] = True

    # the remaining changed lines, one class each
    for index, (_, node) in enumerate(removed_nodes):
        if consumed_removed[index]:
            continue
        consumed_removed[index] = True
        classes.add(_class_of(node, removed=True))
    for jndex, (_, node) in enumerate(added_nodes):
        if consumed_added[jndex]:
            continue
        consumed_added[jndex] = True
        if _is_skip(node):
            classes.add("skip-added")
        else:
            classes.add(_class_of(node, removed=False))
    return classes


def _class_of(node, removed: bool) -> str:
    if node is None:
        return "unknown"
    if _is_docstring(node):
        return "docstring-rewrite"
    if isinstance(node, ast.Assert) and _assert_constant(node):
        return "assert-deleted" if removed else "assert-added"
    return "statement-change"


def edit_classes(diff_text: str) -> tuple:
    """The AST-level edit class of a diff: its sorted class set.

    Each changed statement is classified through `ast.parse`; the diff's
    class is the set of classes it contains, sorted, so two edits match on
    shape exactly (a docstring rewrite plus an expected-value change is
    `("docstring-rewrite", "expected-value")` on both sides or on neither).
    """
    classes: set = set()
    for removed, added in _changed_lines(diff_text).values():
        classes |= _classify_path(removed, added)
    return tuple(sorted(classes))


# -- the similarity score ----------------------------------------------------

def size_similarity(size_a: int, size_b: int) -> float:
    """Diff-size proximity: 1 - |a - b| / max(a, b), 1.0 for two empty diffs.

    One computed return: two identical sizes (including two empty diffs) have
    a zero gap, so the score is the arithmetic of the definition and never a
    literal a test can assert against without computing anything.
    """
    if size_a < 0 or size_b < 0:
        raise TwinError(f"similarity: negative diff size ({size_a}, {size_b})")
    largest = max(size_a, size_b)
    gap = abs(size_a - size_b) / largest if largest else 0.0
    return 1 - gap


@dataclass(frozen=True)
class TwinPair:
    """One positive paired with one legitimate twin, and the score that says
    how close their surface shapes are."""

    positive_id: str
    twin_id: str
    edit_classes: tuple
    similarity: float
    positive_size: int
    twin_size: int

    def linked_records(self, positive, twin) -> tuple:
        """Both records with `twin_id` and `similarity` recorded on each."""
        first = _as_dict(positive)
        second = _as_dict(twin)
        first["twin_id"] = self.twin_id
        second["twin_id"] = self.positive_id
        first["similarity"] = self.similarity
        second["similarity"] = self.similarity
        return first, second


# -- matching ----------------------------------------------------------------

def _diff_for(entry, diffs: Mapping, field_name: str = "diff") -> str:
    entry_id = str(_field(entry, "id") or "").strip()
    text = diffs.get(entry_id) if entry_id else None
    if not isinstance(text, str) or not text.strip():
        raise TwinError(f"diff: missing for {entry_id or '?'}; twin matching "
                        "reads each record's diff text")
    return text


def _candidate_refusal(candidate, repository: str, diffs: Mapping,
                       classes: tuple) -> str | None:
    """The named refusal for one candidate, or None when it may be a twin."""
    candidate_id = str(_field(candidate, "id") or "").strip()
    if not candidate_id:
        return "id: missing; a twin candidate is a named record"
    if _field(candidate, "label") != CLEAN:
        return (f"label: {_field(candidate, 'label')!r} is not "
                f"{CLEAN!r}; a twin is a legitimate record")
    synthetic = _is_synthetic(candidate)
    if synthetic:
        return synthetic
    if _field(candidate, "repository") != repository:
        return (f"repository: {_field(candidate, 'repository')!r} is not "
                f"{repository!r}; matching never pairs across repositories")
    try:
        candidate_diff = _diff_for(candidate, diffs)
    except TwinError as exc:
        return str(exc)
    candidate_classes = edit_classes(candidate_diff)
    if candidate_classes != classes:
        return (f"edit: edit class {candidate_classes} does not match the "
                f"positive's {classes}; a twin has the same surface shape")
    return None


def match_twin(positive, candidates: Iterable, diffs: Mapping) -> TwinPair:
    """The positive's legitimate twin of the same surface shape, scored.

    `diffs` maps record id to unified diff text; a record without its diff is
    refused naming `diff`. A candidate is a twin only when it is legitimate
    (`label` clean), not synthetic or planted, from the positive's own
    repository, of the same AST-level edit class, and within the diff-size
    window. The best surviving candidate is the closest in size; the recorded
    score is that size proximity. When no candidate survives, `TwinError`
    names each candidate's first refusal.
    """
    positive_id = str(_field(positive, "id") or "").strip()
    if not positive_id:
        raise TwinError("id: missing; a positive record is a named record")
    repository = str(_field(positive, "repository") or "").strip()
    if not repository:
        raise TwinError("repository: missing; matching never pairs across "
                        "repositories, so a positive names its repository")
    synthetic = _is_synthetic(positive)
    if synthetic:
        raise TwinError(synthetic)
    positive_diff = _diff_for(positive, diffs)
    classes = edit_classes(positive_diff)
    positive_size = diff_size(positive_diff)

    scored: list = []
    refusals: list = []
    for candidate in candidates:
        refusal = _candidate_refusal(candidate, repository, diffs, classes)
        if refusal:
            refusals.append(f"{_field(candidate, 'id') or '?'}: {refusal}")
            continue
        candidate_diff = _diff_for(candidate, diffs)
        candidate_size = diff_size(candidate_diff)
        similarity = round(size_similarity(positive_size, candidate_size), 4)
        if similarity < MIN_SIMILARITY:
            refusals.append(
                f"{_field(candidate, 'id')}: similarity: {similarity} is below "
                f"{MIN_SIMILARITY}; a twin has a diff size close to the "
                "positive's")
            continue
        scored.append((similarity, str(_field(candidate, "id")), candidate,
                       candidate_size))
    if not scored:
        detail = "; ".join(refusals) if refusals else "no candidates offered"
        raise TwinError(f"twin: no legitimate twin for {positive_id}; "
                        f"{detail}")
    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    similarity, twin_id, candidate, candidate_size = scored[0]
    return TwinPair(positive_id=positive_id, twin_id=twin_id,
                    edit_classes=classes, similarity=similarity,
                    positive_size=positive_size, twin_size=candidate_size)
