"""The strict profile: report mode, plus one question -- who signed off?

Report mode answers "what is this claim worth?" and exits 0. Strict mode
answers the same question and then refuses to let the turn end on an
unexplained finding. It is the profile the Claude and Codex plugins run.

The policy, in full:

| Condition | Strict mode |
|---|---|
| `VERIFIED` | allow |
| `INCONCLUSIVE` | allow, with an explicit no-evidence notice |
| `NOT_VERIFIED` | block (exit 1) -- evidence is not waivable |
| `VERIFICATION_FAILED` | block (exit 3) |
| `SUSPICIOUS` | block (exit 2) unless every finding is waived |
| a `requires_review` finding | block (exit 2) unless that finding is waived |
| an expired, stale or malformed waiver | block (exit 2, or 3 when unreadable) |
| broad `ignore_rules` suppression | reject (exit 3) |

Two lines are drawn deliberately.

**Evidence outranks a decision.** A waiver excuses a *pattern*; it cannot
excuse a held-out suite that failed, a regression, or a requirement the claim
itself named. Those are observations, and a signature does not change what
happened.

**Suppression is not a waiver.** `ignore_rules` turns a rule off for every
finding it will ever produce, with no reviewer and no expiry. Strict mode
refuses to run past it and keeps the suppressed findings in the report, so the
team migrating from a broad ignore list can see exactly what it was hiding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .domain import TrustReport, Verdict
from .waivers import ACTIVE

ALLOWED, BLOCKED = "allowed", "blocked"

EXIT_NOT_VERIFIED = 1
EXIT_SUSPICIOUS = 2
EXIT_CANNOT_CHECK = 3


def waived(signal) -> bool:
    """Whether an *active* waiver covers this finding.

    An expired waiver is annotated on the signal so the report can show it, and
    this deliberately does not count it: a lapsed review is not a decision.
    """
    return bool(signal.waiver) and signal.waiver.get("status") == ACTIVE


def unwaived(signals: Iterable) -> list:
    return [s for s in signals if not waived(s)]


@dataclass
class Gate:
    """The strict decision, and the sentences that explain it."""

    blocked: bool = False
    exit_code: int = 0
    reasons: list = field(default_factory=list)
    notices: list = field(default_factory=list)
    waived: list = field(default_factory=list)

    @property
    def state(self) -> str:
        return BLOCKED if self.blocked else ALLOWED

    def to_dict(self) -> dict:
        return {"state": self.state, "exit_code": self.exit_code,
                "reasons": list(self.reasons), "notices": list(self.notices),
                "waived": list(self.waived), "summary": self.summary()}

    def summary(self) -> str:
        if self.blocked:
            return f"blocked -- {self.reasons[0]}" if self.reasons else "blocked"
        if self.waived:
            return f"allowed -- {len(self.waived)} finding(s) waived with review"
        return "allowed"


def _blocked(exit_code: int, *reasons: str) -> Gate:
    return Gate(blocked=True, exit_code=exit_code,
                reasons=[reason for reason in reasons if reason])


def _describe(signal) -> str:
    where = signal.path + (f":{signal.line}" if signal.line else "")
    return f"[{signal.rule_id}] {where}".strip()


def decide(report: TrustReport, rows: Iterable = (),
           ignored_rules: Iterable = (), ledger_problems: Iterable = ()) -> Gate:
    """The table in the module docstring, in the order it has to be applied."""
    rows = list(rows)
    signals = list(report.signals)
    verification = report.verification

    ignored = sorted({str(rule) for rule in (ignored_rules or ()) if str(rule)})
    if ignored:
        return _blocked(EXIT_CANNOT_CHECK,
                        "strict mode rejects broad rule suppression: ignore_rules "
                        f"names {', '.join(ignored)}",
                        "a waiver binds one finding and expires; a suppressed rule "
                        "binds every finding forever. Waive the individual finding, "
                        "or remove the rule from ignore_rules.")

    broken = [row for row in rows if row.status == "malformed"]
    if broken:
        return _blocked(EXIT_CANNOT_CHECK,
                        f"{len(broken)} waiver entry(ies) cannot be honoured: "
                        + "; ".join(row.note for row in broken[:3]),
                        "fix or delete the entry in .greenwash/waivers.json -- an "
                        "unreadable waiver is not a decision.")

    ledger_problems = list(ledger_problems or ())
    if ledger_problems:
        return _blocked(EXIT_CANNOT_CHECK,
                        "the waiver ledger could not be read: " + "; ".join(ledger_problems[:2]),
                        "repair .greenwash/waivers.json; strict mode will not pass on a "
                        "ledger it cannot read.")

    if verification is not None and verification.harness_error:
        return _blocked(EXIT_CANNOT_CHECK,
                        f"the verification itself could not complete: {verification.harness_error}".strip())

    verdict = report.verdict
    if verdict == Verdict.VERIFICATION_FAILED.value:
        return _blocked(EXIT_CANNOT_CHECK,
                        "a check the claim depends on could not run at all")
    if verdict == Verdict.NOT_VERIFIED.value:
        return _blocked(EXIT_NOT_VERIFIED,
                        "a check the claim depends on does not pass, and evidence is "
                        "not something a waiver can excuse")

    gate = Gate()
    review_findings = unwaived(s for s in signals if s.requires_review)
    if review_findings:
        return _blocked(EXIT_SUSPICIOUS,
                        f"{len(review_findings)} finding(s) need a decision: "
                        + ", ".join(_describe(s) for s in review_findings[:4]),
                        "waive each one with `greenwash waive --rule <rule> --path <path> "
                        "--reason <why> --reviewer @you --expires <date>`, or change the code.")

    lapsed = [row for row in rows if row.status in ("expired", "stale")]
    if lapsed:
        return _blocked(EXIT_SUSPICIOUS,
                        "; ".join(f"{row.waiver.summary()}: {row.note}" for row in lapsed[:3]),
                        "re-review the finding and write a new waiver, or fix it.")

    if verdict == Verdict.SUSPICIOUS.value and (not signals or unwaived(signals)):
        # `not signals` is the belt to the braces: a report the CLI called
        # suspicious with nothing attached to it is still not something strict
        # mode passes, because there is nothing a reviewer could have decided
        unexplained = ", ".join(_describe(s) for s in unwaived(signals)[:4]) \
            or "the report carries no signal to explain"
        return _blocked(EXIT_SUSPICIOUS,
                        "the diff contains a pattern that needs an explanation: "
                        + unexplained)

    gate.waived = [row.waiver.summary() for row in rows if row.status == ACTIVE]
    if gate.waived:
        gate.notices.append(f"{len(gate.waived)} finding(s) waived with review: "
                            + "; ".join(gate.waived[:3]))
    if verdict == Verdict.INCONCLUSIVE.value or (verification is not None
                                                 and not verification.ran):
        gate.notices.append("no behavioral check ran -- strict mode allowed this "
                            "because there was nothing to gate, not because the "
                            "claim was verified")
    unmatched = [row.waiver.summary() for row in rows if row.status == "unmatched"]
    if unmatched:
        gate.notices.append(f"{len(unmatched)} waiver(s) match nothing in this diff: "
                            + "; ".join(unmatched[:3]))
    return gate
