"""Files that decide what gets checked were touched in a way that matters.

These decide what runs, how much of it runs, and what may pass: the test
command, the gate's profile, the waiver ledger, the hook wiring. An agent
editing its own verifier is the move that launders everything else, so a
change here asks for a review rather than accuses.

Three tiers, because "a watched file was touched" is not the same question as
"what runs may have changed":

1. **Whole-file watchers.** Files whose only purpose is runner configuration --
   ``pytest.ini``, ``tox.ini``, ``noxfile.py``, the action's own manifest, the
   pre-commit hook manifest, the hook wiring, the gate's config. Any change is a
   change to what runs.
2. **Changed-line watchers.** Files that mix runner configuration with ordinary
   metadata -- CI workflows, the pre-commit config, project manifests. A change
   fires only when a changed line carries a runner token, a bypass token, a hook
   definition, or removes one. A Dependabot ``uses:``/``rev:`` bump does not.
3. **Everything else**, which is not verifier configuration.

The bias is deliberate and asymmetric. Firing too often costs a review; firing
too rarely costs the detection the rule exists for. So the exclusions are
narrow (version references), the bypass tokens always win, and an unparseable
line is treated as ordinary rather than as a finding.
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
    description=("files that decide what gets checked and what may pass were "
                 "changed, in a way that can alter what runs."),
    remediation="Confirm the change does not weaken the checks for this repository.",
    requires_review=True,
)

# Tier 1: whole-file watchers. The name of the file is the finding.
WATCHED_BASENAMES = {"pytest.ini", "tox.ini", "noxfile.py", "action.yml",
                     ".pre-commit-hooks.yaml"}
WATCHED_PREFIXES = (".greenwash/", "codex/hooks/", ".claude/")
WATCHED_PATHS = {"hooks/hooks.json"}
# The ledger is verifier config too, but it has its own lifecycle: writing a
# waiver must close a finding, not open another one. The self-issued marker is
# what guards it.
EXEMPT = {".greenwash/waivers.json"}

# Tier 2: changed-line watchers.
WORKFLOW_PREFIX = ".github/workflows/"
PRE_COMMIT_BASENAME = ".pre-commit-config.yaml"
MANIFEST_BASENAMES = {"pyproject.toml", "setup.cfg", "package.json"}

# Tier 2 exclusions: a version reference is not runner configuration, whatever
# else the line contains. This is what a dependency bump looks like in each of
# the three file shapes, and it is why the rule no longer asks about them.
VERSION_LINE = re.compile(
    r"^\s*-?\s*(uses|rev)\s*:"                     # action / hook revision
    r"|^\s*\"[^\"]+\"\s*:\s*\"[~^<>=0-9*]"         # package.json dependency
    r"|^\s*\"?[\w.\-\[\]()]+\s*(>=|<=|==|~=|!=|>|<)"  # PEP 508 requirement
    r"|\"[A-Za-z0-9_.\-\[\]]+\s*(>=|<=|==|~=|!=|>|<)[^\"]*\""  # quoted requirement
    r"|^\s*-?\s*version\s*:",                      # explicit version key
    re.I,
)

# Executable and gate-shaped lines in a workflow. `name:` and `runs-on:` are
# labels; the run command, its condition and its environment decide what runs.
WORKFLOW_LINE = re.compile(
    r"^\s*-?\s*(run|if|continue-on-error|with|env|uses)\s*:", re.I)

# Runner tokens: specific enough that a package called `test-utils`, a job
# named `coverage` or a prose paragraph cannot trip them. The bare words `test`
# and `tests` are deliberately absent.
RUNNER_TOKENS = re.compile(
    r"\bpytest\b|\btox\b|\bnox\b|\bnoxfile\b|\bjest\b|\bvitest\b|\bmocha\b"
    r"|\bava\b|\brspec\b|\bphpunit\b|\bgo\s+test\b|\bcargo\s+test\b"
    r"|\bdotnet\s+test\b|\bmvn\b.*\btest\b|\bgradle\b.*\btest\b"
    r"|\b(npm|yarn|pnpm)\s+(run\s+)?test\b"
    r"|\btestpaths\b|\baddopts\b|\bcollect_ignore\b|\bdeselect\b"
    r"|\b--cov\b|\bcoverage\b",
    re.I,
)

# Bypass tokens: a way to keep the check green without keeping it strict. They
# fire whatever file they appear in and whatever else the line says.
BYPASS_TOKENS = re.compile(
    r"continue-on-error|if:\s*false\b|--ignore\b|--deselect\b|--no-cov\b"
    r"|\|\|\s*true\b|\bset\s+\+e\b|allow_failure|ignore_fail"
    r"|-k\s+[\"']?(not|skip)\b",
    re.I,
)

# Pre-commit: a hook's identity, command and scope. `rev:` is excluded above as
# a version reference, which is the bulk of the dependency-bump noise.
HOOK_IDENTITY = re.compile(r"^\s*-?\s*id\s*:", re.I)
HOOK_SHAPE = re.compile(
    r"^\s*-?\s*(entry|args|stages|files|exclude|always_run|pass_filenames)"
    r"\s*:", re.I)


def _normalize(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized[2:] if normalized.startswith("./") else normalized


def watched(path: str) -> bool:
    """Tier 1: the whole file is verifier configuration."""
    normalized = _normalize(path)
    return (os.path.basename(normalized) in WATCHED_BASENAMES
            or normalized in WATCHED_PATHS
            or normalized.startswith(WATCHED_PREFIXES))


def _is_workflow(normalized: str) -> bool:
    return normalized.startswith(WORKFLOW_PREFIX)


def _is_changed_line_watched(normalized: str) -> bool:
    return (_is_workflow(normalized)
            or os.path.basename(normalized) == PRE_COMMIT_BASENAME
            or os.path.basename(normalized) in MANIFEST_BASENAMES)


def _lines(ctx, path) -> tuple:
    hunks = ctx.files.get(path, {})
    return list(hunks.get("removed", [])), list(hunks.get("added", []))


def _candidates(lines) -> list:
    """The changed lines that are not version references."""
    return [line for line in lines if line.strip()
            and not VERSION_LINE.search(line)]


def _workflow_reason(removed, added) -> str:
    for line in [*removed, *added]:
        if BYPASS_TOKENS.search(line):
            return ("a skip condition was added, removed or changed in this "
                    "workflow -- it can make a failing suite read as passing")
    for line in removed:
        if WORKFLOW_LINE.match(line) and RUNNER_TOKENS.search(line):
            return ("a test command was removed from this workflow -- the "
                    "suite no longer runs there")
    for line in added:
        if WORKFLOW_LINE.match(line) and RUNNER_TOKENS.search(line):
            return ("a test command or runner setting changed in this "
                    "workflow -- it decides what runs")
    return ""


def _pre_commit_reason(removed, added) -> str:
    for line in removed:
        if HOOK_IDENTITY.match(line):
            return ("a pre-commit hook was removed -- a check that used to "
                    "run no longer does")
    for line in [*removed, *added]:
        if HOOK_SHAPE.match(line):
            return ("a pre-commit hook's command or scope changed -- it "
                    "decides what gets checked")
    return ""


def _manifest_reason(removed, added) -> str:
    for line in [*removed, *added]:
        if RUNNER_TOKENS.search(line):
            return ("test-runner configuration changed in this manifest -- "
                    "it decides what runs")
    return ""


def _changed_line_reason(normalized, ctx, path) -> str:
    removed, added = _lines(ctx, path)
    removed, added = _candidates(removed), _candidates(added)
    # A line that is removed and re-added with only whitespace or line-ending
    # churn is not a change; a whole-file re-emit (a formatter, a CRLF
    # conversion, a merge) otherwise reads as "every test command was removed".
    added_norm = {line.strip() for line in added}
    removed_norm = {line.strip() for line in removed}
    removed = [line for line in removed if line.strip() not in added_norm]
    added = [line for line in added if line.strip() not in removed_norm]
    if _is_workflow(normalized):
        return _workflow_reason(removed, added)
    if os.path.basename(normalized) == PRE_COMMIT_BASENAME:
        return _pre_commit_reason(removed, added)
    return _manifest_reason(removed, added)


def check(ctx) -> list:
    out = []
    for path in [*ctx.paths(), *ctx.deleted]:
        normalized = _normalize(path)
        if normalized in EXEMPT:
            continue
        if watched(path):
            out.append(RULE.signal(path, None, "verifier configuration changed "
                                          "-- this file decides what gets "
                                          "checked and what may pass"))
            continue
        if not _is_changed_line_watched(normalized):
            continue
        if path in ctx.deleted:
            out.append(RULE.signal(path, None, "a file that decides what runs "
                                          "was deleted -- confirm the checks it "
                                          "carried are elsewhere"))
            continue
        reason = _changed_line_reason(normalized, ctx, path)
        if reason:
            out.append(RULE.signal(path, None, reason))
    return out
