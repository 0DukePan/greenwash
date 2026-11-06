"""A changed Python file the static layer could not read.

The AST rules work on a parsed tree, so a file that will not parse is invisible
to every one of them. That silence used to be indistinguishable from a clean
result: no signal, no note, and the report moved on -- the exact shape this
tool exists to reject, because a check that could not run must never read as a
pass.

The finding is deliberately an ask, not an accusation. A file that does not
parse may be a template, generated code, a stub for another toolchain, or a
merge leftover; none of that is cheating. What it is not is a pass, so the
finding names the file, says the static layer could not read it, and stays out
of the verdict as an accusation: it carries no mechanism and no grade
relevance, so it can never resolve to TAMPERED, and it never outranks a
finding that did run.

A path that is simply absent from the tree is not reported. `scan_diff` also
runs over synthetic corpora and replayed history whose post-image is not the
checkout; a missing path there is a diff/tree mismatch, not a file that failed
to parse. What this rule reports is a file that was there and would not parse.
"""

from __future__ import annotations

from .base import DIVERGENCE, Rule

RULE = Rule(
    id="unreadable-file",
    code="GW-DIV-003",
    title="Changed file could not be read",
    category=DIVERGENCE,
    severity="LOW",
    confidence="HIGH",
    description="A changed Python file could not be parsed, so the static "
                "checks did not run on it -- the file is unchecked, not clean.",
    remediation="Fix the syntax error, or say why this file is not meant to be "
                "parsed. Leave it unexplained and the static layer never sees it.",
    requires_review=True,
)


def check(ctx) -> list:
    signals = []
    for path in ctx.paths():
        if ctx.language(path) != "python":
            continue
        module = ctx.module(path)
        if module.ok:
            continue
        if module.error_type == "FileNotFoundError":
            # A diff whose paths do not resolve against `root` is a caller
            # mismatch (a synthetic corpus, a historical replay), not a file
            # that failed to parse. There was nothing there to read, so there
            # is nothing to report about its contents.
            continue
        reason = module.error or "not valid Python"
        signals.append(RULE.signal(
            path, None,
            f"the static layer could not read this changed file ({reason}) -- "
            "the checks that parse Python did not run on it, so it is "
            "unchecked, not clean",
            parse_error=reason))
    return signals
