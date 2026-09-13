"""Rule metadata and the Signal it produces.

A rule is data plus one function. The data is what shows up in a report and in
`docs/rules.md`; the function is what looks at the diff. Keeping them together
means a rule cannot exist without an explanation, a severity and a remedy --
which is the difference between a linter and a linter you can argue with.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from ...domain import Level, Signal

# Categories, used for the code prefix and for grouping in reports.
TEST_INTEGRITY = "test-integrity"
DIVERGENCE = "divergence"
EXPLOIT = "exploit"


@dataclass(frozen=True)
class Rule:
    id: str
    code: str
    title: str
    category: str
    severity: str
    confidence: str
    description: str
    remediation: str
    requires_review: bool = False
    languages: tuple = ()

    def signal(self, path: str = "", line: Optional[int] = None,
               explanation: str = "", analysis: Optional[str] = None, **evidence) -> Signal:
        confidence = self.confidence
        if analysis and analysis != "ast" and confidence == Level.HIGH.value:
            # A regex cannot parse the language beneath it, so a rule that is
            # HIGH confidence on a parsed file is only MEDIUM confidence here.
            # The severity is unchanged: a skipped test is a skipped test.
            confidence = Level.MEDIUM.value
        if analysis:
            evidence["analysis"] = analysis
        return Signal(
            rule_id=self.id,
            code=self.code,
            title=self.title,
            category=self.category,
            severity=self.severity,
            confidence=confidence,
            explanation=explanation or self.description,
            files=[path] if path else [],
            line=line,
            evidence=evidence,
            remediation=self.remediation,
            requires_review=self.requires_review,
        )


@dataclass
class ScanContext:
    """Everything the rules are allowed to look at."""

    files: dict = field(default_factory=dict)      # path -> {added, removed, added_lines}
    deleted: list = field(default_factory=list)
    diff_text: str = ""
    asserted_literals: set = field(default_factory=set)
    root: str = ""                                 # repo root the paths are relative to
    _modules: dict = field(default_factory=dict)

    def paths(self) -> list:
        return list(self.files)

    def is_test(self, path: str) -> bool:
        from ..languages.packs import is_test_file
        return is_test_file(path)

    def language(self, path: str) -> Optional[str]:
        from ..languages.packs import language_of
        return language_of(path)

    def added_lines(self, path: str) -> set:
        return set(self.files.get(path, {}).get("added_lines", set()))

    def added_text(self, path: str) -> str:
        return "\n".join(self.files.get(path, {}).get("added", []))

    def added_code(self, path: str) -> str:
        """Added text with comments stripped, for regex rules."""
        from ..languages.packs import strip_comments
        language = self.language(path) or ""
        return strip_comments(self.added_text(path), language)

    def removed_text(self, path: str) -> str:
        return "\n".join(self.files.get(path, {}).get("removed", []))

    def module(self, path: str):
        """A parsed Python file, parsed at most once per scan.

        Resolved against the repo root, not the process directory: a library
        caller passing `cwd=` must not have its files read from wherever the
        process happens to be standing.
        """
        from ..languages.python_ast import PythonModule
        if path not in self._modules:
            full = os.path.join(self.root, path) if self.root else path
            self._modules[path] = PythonModule(full)
        return self._modules[path]

    def counts(self, path: str) -> dict:
        hunks = self.files.get(path, {})
        return {"added": len(hunks.get("added", [])), "removed": len(hunks.get("removed", []))}
