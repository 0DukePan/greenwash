"""Markdown report -- for pasting into a pull request.

Kept deliberately plain: headings, a table, and the evidence as a blockquote.
No HTML, no images, nothing that renders as noise in a code review.
"""

from __future__ import annotations

from ..domain import Outcome, TrustReport, VerificationResult


def _cell(outcome: str, detail: str) -> tuple:
    label = {Outcome.PASS.value: "pass", Outcome.FAIL.value: "**FAIL**",
             Outcome.NOT_REQUESTED.value: "not run",
             Outcome.UNAVAILABLE.value: "unavailable",
             Outcome.INCONCLUSIVE.value: "inconclusive"}.get(outcome, outcome)
    return label, detail or "\u2014"


def render(report: TrustReport, verbose: bool = False) -> str:
    run = report.run
    verification = report.verification or VerificationResult()
    out: list[str] = []

    out.append("## Greenwash trust report")
    out.append("")
    claim = run.claim if run else None
    if claim and claim.text:
        out.append(f"**Agent claim:** \u201c{claim.text}\u201d")
        out.append("")
    out.append(f"**Changes:** {run.diff_summary() if run else 'none detected'}")
    out.append("")

    out.append("| Check | Result | Detail |")
    out.append("|---|---|---|")
    label, detail = _cell(verification.outcome, verification.summary_line())
    out.append(f"| Visible tests | {label} | {detail} |")
    label, detail = _cell(verification.heldout,
                          verification.test_command or "held-out suite")
    out.append(f"| Held-out checks | {label} | {detail} |")
    label, detail = _cell(verification.baseline, "")
    detail = (f"{len(verification.newly_failing)} newly failing"
              if verification.baseline == Outcome.FAIL.value else detail)
    out.append(f"| Baseline comparison | {label} | {detail} |")
    out.append("")

    if report.signals:
        out.append("### Suspicious patterns")
        out.append("")
        for signal in report.signals:
            where = signal.path + (f":{signal.line}" if signal.line else "")
            code = f" ({signal.code})" if signal.code else ""
            title = signal.title or signal.rule_id
            location = f" \u2014 `{where}`" if where else ""
            out.append(f"- **{title}**{code}{location}")
            out.append(f"  - {signal.explanation}")
            if signal.requires_review:
                out.append("  - requires review \u2014 not a failure by itself")
            elif verbose and signal.remediation:
                out.append(f"  - to resolve: {signal.remediation}")
    else:
        out.append("### Suspicious patterns")
        out.append("")
        out.append("None detected.")
    out.append("")

    if verification.evidence:
        out.append("### Evidence")
        out.append("")
        for item in verification.evidence[:6]:
            if item.expected:
                out.append(f"> **Expected:** {item.expected}  ")
            if item.observed:
                out.append(f"> **Observed:** {item.observed}  ")
            if item.source:
                out.append(f"> **Source:** {item.source}")
            out.append("")

    if verification.notes:
        out.append("### Notes")
        out.append("")
        for note in verification.notes:
            out.append(f"- {note}")
        out.append("")

    out.append(f"**Verdict: {report.verdict}**")
    if report.confidence:
        out.append("")
        out.append(f"**Confidence: {report.confidence.level}** "
                   f"(score {report.confidence.score}/100)")
        for reason in report.confidence.reasons:
            out.append(f"- {reason}")

    out.append("")
    out.append(f"<sub>greenwash schema v{report.schema_version} \u00b7 "
               f"report only \u00b7 nothing here blocked your run</sub>")
    return "\n".join(out).rstrip() + "\n"
