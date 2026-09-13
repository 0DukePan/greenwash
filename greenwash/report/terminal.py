"""The terminal report -- the thing a developer actually reads.

Two properties this renderer is built for:

* It is honest about what did *not* happen. A check that never ran prints as
  `not run`, never as a pass.
* Every non-clean verdict carries evidence. There is no path through this file
  that prints a bare `FAILED`.

Colour is opt-out (`NO_COLOR`, `--no-color`, a pipe) and the tick marks fall
back to ASCII when the terminal cannot encode them -- which is what happens on
a default Windows console.
"""

from __future__ import annotations

import os
import sys
import textwrap

from ..domain import Level, Outcome, TrustReport, Verdict

RULE = "\u2500"          # box drawing horizontal
RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
RED, GREEN, YELLOW, CYAN = "\033[31m", "\033[32m", "\033[33m", "\033[36m"

VERDICT_COLOR = {
    Verdict.VERIFIED.value: GREEN,
    Verdict.PARTIALLY_VERIFIED.value: YELLOW,
    Verdict.SUSPICIOUS.value: YELLOW,
    Verdict.NOT_VERIFIED.value: RED,
    Verdict.VERIFICATION_FAILED.value: RED,
    Verdict.INCONCLUSIVE.value: DIM,
}

VERDICT_BLURB = {
    Verdict.VERIFIED.value: "the claim is backed by the checks that ran",
    Verdict.PARTIALLY_VERIFIED.value: "the checks that ran support the claim, with caveats",
    Verdict.SUSPICIOUS.value: "the diff contains a pattern that needs an explanation",
    Verdict.NOT_VERIFIED.value: "a check the claim depends on does not pass",
    Verdict.VERIFICATION_FAILED.value: "the verification itself could not complete",
    Verdict.INCONCLUSIVE.value: "not enough evidence to say either way",
}


def supports_unicode(stream=None) -> bool:
    stream = stream or sys.stdout
    encoding = (getattr(stream, "encoding", "") or "").lower()
    return "utf" in encoding


def marks(stream=None) -> dict:
    if supports_unicode(stream):
        return {"pass": "\u2713", "fail": "\u2717", "warn": "\u26a0",
                "skip": "\u00b7", "bullet": "\u2500"}
    return {"pass": "+", "fail": "x", "warn": "!", "skip": "-", "bullet": "-"}


def use_color(color=None) -> bool:
    if color is None:
        color = bool(getattr(sys.stdout, "isatty", lambda: False)()) \
            and not os.environ.get("NO_COLOR")
    return bool(color)


def _paint(text: str, code: str, color: bool) -> str:
    return f"{code}{text}{RESET}" if color else text


def _check_line(label: str, outcome: str, detail: str, mk: dict, color: bool) -> str:
    if outcome == Outcome.PASS.value:
        mark, paint = mk["pass"], GREEN
    elif outcome == Outcome.FAIL.value:
        mark, paint = mk["fail"], RED
    elif outcome == Outcome.NOT_REQUESTED.value:
        mark, paint = mk["skip"], DIM
    else:
        mark, paint = mk["warn"], YELLOW
    head = f"  {_paint(mark, paint, color)} {label:<22}"
    return f"{head}{detail}".rstrip()


ASCII_FALLBACKS = (
    ("\u2500", "-"), ("\u00b7", "-"), ("\u2014", "--"), ("\u2013", "-"),
    ("\u2713", "+"), ("\u2717", "x"), ("\u26a0", "!"), ("\u201c", '"'),
    ("\u201d", '"'), ("\u2018", "'"), ("\u2019", "'"), ("\u2026", "..."),
)


def encode_safe(text: str, stream=None) -> str:
    """Make text printable on the stream we actually have.

    A default Windows console is cp1252, where a tick mark raises
    UnicodeEncodeError. Rather than crash -- or emit UTF-8 bytes that the
    console renders as mojibake -- the decoration degrades to ASCII, and so
    does any exotic character that arrived inside a claim or a rule's detail.
    """
    stream = stream or sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
        return text
    except (UnicodeEncodeError, LookupError):
        for fancy, plain in ASCII_FALLBACKS:
            text = text.replace(fancy, plain)
        return text.encode(encoding, "replace").decode(encoding, "replace")


def width(default: int = 96) -> int:
    """How wide to wrap prose.

    `COLUMNS` wins when it is set (the demo pins it so the GIF and the README
    transcript agree), then a sane default. Structure lines are never wrapped;
    only sentences.
    """
    try:
        columns = int(os.environ.get("COLUMNS", ""))
    except (TypeError, ValueError):
        columns = default
    return max(48, min(columns, 200))


def wrap(text: str, indent: int, limit: int = None) -> str:
    return textwrap.fill(text, width=limit or width(),
                         subsequent_indent=" " * (indent + 4),
                         break_long_words=False, break_on_hyphens=False)


def render(report: TrustReport, color=None, verbose: bool = False,
           quiet: bool = False) -> str:
    color = use_color(color)
    mk = marks()
    lines: list[str] = []

    title = "GREENWASH TRUST REPORT"
    lines.append(_paint(title, BOLD, color))
    lines.append(RULE * len(title))
    lines.append("")

    if quiet:
        return encode_safe(_quiet(report, mk, color))

    claim = report.run.claim if report.run else None
    if claim and claim.text:
        lines.append(f'Agent claim: "{claim.text}"')
    if report.run and (report.run.agent or report.run.changed_files):
        bits = [b for b in (report.run.agent, report.run.mode and f"mode: {report.run.mode}")
                if b]
        lines.append(f"{'Run':<13}{' \u00b7 '.join(bits)}")

    lines.append("")
    lines.append("Changes:")
    lines.append(f"  {report.run.diff_summary() if report.run else 'no changes detected'}")
    if verbose and report.run:
        for change in report.run.changed_files[:20]:
            lines.append(f"    {change.kind:<8} {change.path} (+{change.added}/-{change.removed})")
        if len(report.run.changed_files) > 20:
            lines.append(f"    ... and {len(report.run.changed_files) - 20} more")

    verification = report.verification
    lines.append("")
    lines.append("Verification:")
    if verification is None:
        lines.append(_check_line("Behavioral checks", Outcome.NOT_REQUESTED.value,
                                 "not run", mk, color))
    else:
        detail = verification.summary_line()
        if verification.test_command:
            detail = f"{detail}  ({verification.test_command})"
        lines.append(_check_line("Visible tests", verification.outcome, detail, mk, color))

        held = verification.heldout
        held_detail = ""
        if held == Outcome.FAIL.value:
            failed = verification.heldout_detail.get("failed")
            passed = verification.heldout_detail.get("passed")
            if failed is not None and passed is not None:
                held_detail = f"{passed}/{passed + failed} cases"
        lines.append(_check_line("Held-out checks", held, held_detail or
                                 ("not supplied" if held == Outcome.NOT_REQUESTED.value
                                  else held), mk, color))
        lines.append(_check_line("Baseline comparison",
                                 verification.baseline if verification.ran
                                 else Outcome.NOT_REQUESTED.value,
                                 _baseline_detail(verification), mk, color))
        regressions = verification.regressions
        lines.append(_check_line(
            "Regression checks",
            Outcome.FAIL.value if regressions else
            (Outcome.PASS.value if verification.baseline == Outcome.PASS.value
             else Outcome.NOT_REQUESTED.value),
            f"{len(regressions)} regressed" if regressions else
            ("none" if verification.baseline != Outcome.NOT_REQUESTED.value else "not run"),
            mk, color))
        if verification.harness_error:
            lines.append(_check_line("Harness", Outcome.UNAVAILABLE.value,
                                     verification.harness_error, mk, color))

    lines.append("")
    lines.append("Suspicious patterns:")
    if not report.signals:
        lines.append(f"  {mk['pass'] if report.verdict == Verdict.VERIFIED.value else mk['skip']}"
                     f" None detected")
    else:
        for signal in report.signals:
            location = signal.path + (f":{signal.line}" if signal.line else "")
            code = f" {DIM}{signal.code}{RESET}" if signal.code and color else \
                (f" {signal.code}" if signal.code else "")
            tag = f"[{signal.rule_id}]"
            lines.append(f"  {_paint(mk['warn'], YELLOW, color)} {tag}{code}"
                         f"{'  ' + location if location else ''}")
            lines.append(wrap("      " + signal.explanation, 6))
            if signal.requires_review:
                lines.append(f"      {_paint('requires review -- not a failure by itself',
                                             DIM, color)}")
            elif verbose and signal.remediation:
                lines.append(wrap("      " + _paint("to resolve: ", DIM, color)
                                  + signal.remediation, 6))

    evidence = (verification.evidence if verification else [])
    if evidence:
        lines.append("")
        lines.append("Evidence:")
        for item in evidence[:6]:
            if item.expected:
                lines.append(wrap("  Expected: " + item.expected, 2))
            if item.observed:
                lines.append(wrap("  Observed: " + item.observed, 2))
            if item.source:
                lines.append(wrap("  Source:   " + item.source, 2))
            if item.command:
                lines.append(wrap("  Command:  " + item.command, 2))
            if verbose and item.summary:
                lines.append(wrap("  Summary:  " + item.summary, 2))

    lines.append("")
    lines.append(f"Verdict: {_paint(report.verdict, BOLD + VERDICT_COLOR.get(
        report.verdict, ''), color)} -- {VERDICT_BLURB.get(report.verdict, '')}")
    if report.confidence:
        lines.append(f"Confidence: {report.confidence.level} "
                     f"(score {report.confidence.score}/100)")
        shown = report.confidence.reasons if verbose else report.confidence.reasons[:4]
        for reason in shown:
            lines.append(wrap(f"  {mk['bullet']} {reason}", 2))

    for note in report.notes:
        lines.append(wrap("note: " + note, 6))

    if not report.verification or not report.verification.ran:
        lines.append("")
        lines.append(_paint("No behavioral check ran -- this report is a diff review only.",
                            DIM, color))

    return encode_safe("\n".join(lines).rstrip() + "\n")


def _baseline_detail(verification) -> str:
    if verification.baseline == Outcome.PASS.value:
        return "no regressions"
    if verification.baseline == Outcome.FAIL.value:
        return f"{len(verification.newly_failing)} test(s) newly failing"
    if verification.baseline == Outcome.NOT_REQUESTED.value:
        return "not requested"
    return "unavailable"


def _quiet(report: TrustReport, mk: dict, color: bool) -> str:
    mark = {Verdict.VERIFIED.value: (mk["pass"], GREEN),
            Verdict.INCONCLUSIVE.value: (mk["skip"], DIM)}.get(
                report.verdict, (mk["warn"], YELLOW))
    confidence = f" ({report.confidence.level.lower()} confidence)" \
        if report.confidence else ""
    return (f"{_paint(mark[0], mark[1], color)} greenwash: {report.verdict.lower()}"
            f"{confidence} -- {len(report.signals)} signal(s)\n")
