"""Files that decide what gets checked were touched.

These decide what runs, how much of it runs, and what may pass: the test
command, the gate's profile, the waiver ledger, the hook wiring. An agent
editing its own verifier is the move that launders everything else, so a
change here asks for a review rather than accuses -- dependency bumps in
package manifests are ordinary work, which is why the section-scoped files
only count when the changed lines mention a runner.
"""

from __future__ import annotations

import os
import re

from .base import TEST_INTEGRITY, Rule

RULE = Rule(
    id="verifier-config-changed",
    code="GW-TEST-007",
    title="verifier configuration changed",
    category=TEST_INTEGRITY,
    severity="MEDIUM",
    confidence="LOW",
    description="files that decide what gets checked and what may pass were changed.",
    remediation="Confirm the change does not weaken the checks for this repository.",
    requires_review=True,
)

WATCHED_BASENAMES = {"pytest.ini", "tox.ini", "noxfile.py", "action.yml",
                     ".pre-commit-config.yaml", ".pre-commit-hooks.yaml"}
WATCHED_PREFIXES = (".greenwash/", "codex/hooks/", ".github/workflows/", ".claude/")
WATCHED_PATHS = {"hooks/hooks.json"}
# The ledger is verifier config too, but it has its own lifecycle: writing a
# waiver must close a finding, not open another one. The self-issued marker is
# what guards it.
EXEMPT = {".greenwash/waivers.json"}
# Whole-file watchers for manifests that carry test configuration among
# ordinary project metadata: only runner lines in the diff count, and only as
# whole words ("latest" and "testnet" are not test configuration).
SECTION_WATCHED = {"pyproject.toml", "setup.cfg", "package.json"}
RUNNER_TOKENS = ("pytest", "jest", "vitest", "tox", "nox", "test", "tests",
                 "testpaths", "test_command", "coverage", "addopts",
                 "collect_ignore", "deselect")


def _normalize(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized[2:] if normalized.startswith("./") else normalized


def watched(path: str) -> bool:
    normalized = _normalize(path)
    return (os.path.basename(normalized) in WATCHED_BASENAMES
            or normalized in WATCHED_PATHS
            or normalized.startswith(WATCHED_PREFIXES))


def check(ctx) -> list:
    out = []
    for path in [*ctx.paths(), *ctx.deleted]:
        normalized = _normalize(path)
        if normalized in EXEMPT:
            continue
        if watched(path):
            out.append(RULE.signal(path, None, "verifier configuration changed -- "
                                          "this file decides what gets checked and "
                                          "what may pass"))
        elif os.path.basename(normalized) in SECTION_WATCHED:
            hunks = ctx.files.get(path, {})
            changed = "\n".join(hunks.get("added", []) + hunks.get("removed", []))
            deleted_manifest = path in ctx.deleted
            if deleted_manifest or any(
                    re.search(rf"\b{re.escape(token)}\b", changed.lower())
                    for token in RUNNER_TOKENS):
                out.append(RULE.signal(path, None, "test-runner configuration changed in "
                                              "this manifest -- it decides what runs"))
    return out
