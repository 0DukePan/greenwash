"""Static scan: compare the diff against the language packs + AST checks."""

from __future__ import annotations

import os
import re

from . import ast_checks
from .diff import find_related_test_files, parse_diff, read_text, run_git_diff
from .patterns import (
    ASSERT_LITERAL_PATTERNS,
    GENERIC_EXPLOITS,
    PACKS,
    RETURN_LITERAL_PATTERN,
    TRIVIAL_LITERALS,
    is_test_file,
    language_of,
)
from .report import Flag


def literals_from_text(text: str) -> set:
    found = set()
    for pattern in ASSERT_LITERAL_PATTERNS:
        found.update(re.findall(pattern, text))
    return {lit for lit in found if lit.lower() not in TRIVIAL_LITERALS}


def _regex_flags(patterns, text, filename, kind):
    return [Flag(filename, kind, label) for pattern, label in patterns if re.search(pattern, text)]


def _strip_comments(text: str, lang) -> str:
    """Drop comments before pattern matching.

    Reduces false positives (a comment that merely mentions `@pytest.mark.skip`)
    and small spacing evasions. The `(?<!:)` guard keeps `https://` intact.
    """
    if lang in ("python", "ruby"):
        return re.sub(r"#.*", "", text)
    if lang in ("javascript", "go", "rust", "java"):
        return re.sub(r"(?<!:)//.*", "", text)
    return text



def check_file(filename, hunks, asserted_literals):
    flags = []
    added = "\n".join(hunks["added"])
    removed = "\n".join(hunks["removed"])
    lang = language_of(filename)
    pack = PACKS.get(lang, {})
    is_test = is_test_file(filename)
    added_code = _strip_comments(added, lang)

    flags += _regex_flags(pack.get("skip", []), added_code, filename, "test-skipped")

    removed_asserts = len(re.findall(r"assert\w*|expect\s*\(", removed))
    added_asserts = len(re.findall(r"assert\w*|expect\s*\(", added))
    if is_test and removed_asserts and added_asserts < removed_asserts:
        flags.append(Flag(filename, "assertion-weakened",
                          f"{removed_asserts} assertion(s) removed, {added_asserts} added back"))

    if os.path.basename(filename) == "conftest.py":
        flags.append(Flag(filename, "conftest-changed",
                          "conftest.py changed -- fixture/hook patching here can mask "
                          "failures repo-wide, worth a manual look"))

    if is_test:
        flags += _regex_flags(pack.get("mock", []), added_code, filename, "mock-in-test")

    if lang == "python":
        flags += ast_checks.check_python(filename, hunks.get("added_lines", set()),
                                         asserted_literals, is_test)
    else:
        flags += _regex_flags(pack.get("swallow", []), added_code, filename, "swallowed-exception")
        flags += _regex_flags(GENERIC_EXPLOITS, added_code, filename, "known-exploit-pattern")
        if not is_test and asserted_literals:
            for match in re.finditer(RETURN_LITERAL_PATTERN, added_code):
                value = match.group(1)
                if value in asserted_literals:
                    flags.append(Flag(filename, "hardcoded-return",
                                      f"returns literal {value!r}, which a test asserts "
                                      f"against -- check this isn't a pass-through"))

    seen, out = set(), []
    for flag in flags:
        key = (flag.file, flag.kind, flag.detail)
        if key not in seen:
            seen.add(key)
            out.append(flag)
    return out


def scan(staged: bool = False, base=None) -> list:
    diff_text = run_git_diff(staged, base)
    if not diff_text.strip():
        return []
    files, deleted = parse_diff(diff_text)

    asserted_literals = set()
    for hunks in files.values():
        asserted_literals |= literals_from_text("\n".join(hunks["added"]))
    for filename in files:
        if is_test_file(filename):
            continue
        for related in find_related_test_files(filename):
            asserted_literals |= literals_from_text(read_text(related))

    flags = []
    for path in deleted:
        if is_test_file(path):
            flags.append(Flag(path, "test-file-deleted", "entire test file removed in this diff"))
    for filename, hunks in files.items():
        flags.extend(check_file(filename, hunks, asserted_literals))
    return flags
