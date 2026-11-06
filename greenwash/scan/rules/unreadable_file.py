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

The unreadability has two shapes, and both are the same gap. A file that will
not parse is one. A file git classifies as binary is the other: it has no
hunks in the diff at all, so it never reaches `ctx.paths()` and the older rule
could not see it even to note its absence. `ScanContext.binary_paths()` carries
those paths, and the report says *binary*, not "SyntaxError" -- nothing parsed
the file, so there is no parse error to quote.

A path that is simply absent from the tree is not reported, in either shape.
`scan_diff` also runs over synthetic corpora and replayed history whose
post-image is not the checkout; a missing path there is a diff/tree mismatch,
not a file that failed to be read. What this rule reports is a file that was
there and could not be read.
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
    description="A changed Python file could not be read -- git calls it "
                "binary, or it will not parse -- so the static checks did not "
                "run on it. The file is unchecked, not clean.",
    remediation="Fix the syntax error, or say why this file is not meant to be "
                "parsed. Leave it unexplained and the static layer never sees it.",
    requires_review=True,
)


def _explanation(failure) -> str:
    """What the report says, and why, without conflating binary with a parse error."""
    if failure.binary:
        return ("git reports this changed file as binary, so the static layer "
                "could not read it as Python -- it is unchecked, not clean")
    return (f"the static layer could not read this changed file "
            f"({failure.type}: {failure.message}) -- the checks that parse "
            "Python did not run on it, so it is unchecked, not clean")


def check(ctx) -> list:
    signals = []
    for path in [*ctx.paths(), *ctx.binary_paths()]:
        if ctx.language(path) != "python":
            continue
        module = ctx.module(path)
        if module.ok or not module.unreadable:
            # `missing` -- a path the checkout does not hold -- is a caller
            # mismatch (a synthetic corpus, a historical replay), not a file
            # that failed to be read. There was nothing there to report.
            continue
        failure = module.failure
        signals.append(RULE.signal(
            path, failure.line, _explanation(failure),
            parse_error=f"{failure.type}: {failure.message}"))
    return signals
