"""The domain model: the schemas every other module depends on.

Design rules, in order of importance:

1. Serialization never crashes. Every field has a default, `from_dict` ignores
   unknown keys and tolerates wrong types, and a malformed report degrades to
   an empty one rather than raising.
2. Nothing is asserted that wasn't observed. `VerificationResult` records
   `unavailable` rather than a pass it did not see.
3. The words are careful. Signals are "suspicious" or "require review"; this
   module has no vocabulary for accusing anyone of cheating.

`TrustReport.to_dict()` is the versioned wire format (`schema_version: "1"`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

SCHEMA_VERSION = "1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Verdict(str, Enum):
    """What the evidence supports. Deliberately not a percentage."""

    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    SUSPICIOUS = "SUSPICIOUS"
    NOT_VERIFIED = "NOT_VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"

    @classmethod
    def parse(cls, value: Any) -> "Verdict":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().upper())
        except ValueError:
            return cls.INCONCLUSIVE


class Level(str, Enum):
    """LOW / MEDIUM / HIGH. Used for both confidence and severity."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @classmethod
    def parse(cls, value: Any, default: "Level" = None) -> "Level":
        default = default or cls.MEDIUM
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().upper())
        except ValueError:
            return default


class Outcome(str, Enum):
    """The result of one check: pass, fail, or an honest 'I could not tell'."""

    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"
    NOT_REQUESTED = "not_requested"
    INCONCLUSIVE = "inconclusive"

    @classmethod
    def parse(cls, value: Any, default: "Outcome" = None) -> "Outcome":
        default = default or cls.UNAVAILABLE
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return default


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class _Model:
    """Shared (de)serialization: tolerant in, predictable out."""

    def to_dict(self) -> dict:
        out: dict = {}
        for spec in fields(self):  # type: ignore[arg-type]
            value = getattr(self, spec.name)
            if isinstance(value, Enum):
                value = value.value
            elif is_dataclass(value):
                value = value.to_dict()
            elif isinstance(value, list):
                value = [v.to_dict() if isinstance(v, _Model) else
                         (v.value if isinstance(v, Enum) else v) for v in value]
            elif isinstance(value, dict):
                value = {k: (v.to_dict() if isinstance(v, _Model) else v)
                         for k, v in value.items()}
            out[spec.name] = value
        return out

    @classmethod
    def from_dict(cls, data: Any):
        data = _as_dict(data)
        known = {spec.name for spec in fields(cls)}  # type: ignore[arg-type]
        kwargs = {k: v for k, v in data.items() if k in known}
        try:
            return cls(**kwargs)  # type: ignore[call-arg]
        except TypeError:
            return cls()  # type: ignore[call-arg]


@dataclass
class Claim(_Model):
    """What the agent said it accomplished."""

    text: str = ""
    source: str = ""                      # "hook", "cli", "pr-description", ...
    files_touched: list = field(default_factory=list)
    structured: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Any) -> "Claim":
        data = _as_dict(data)
        return cls(
            text=_as_str(data.get("text")),
            source=_as_str(data.get("source")),
            files_touched=[_as_str(f) for f in _as_list(data.get("files_touched"))],
            structured=_as_dict(data.get("structured")),
        )

    def __bool__(self) -> bool:
        return bool(self.text.strip())


@dataclass
class FileChange(_Model):
    path: str = ""
    added: int = 0
    removed: int = 0
    kind: str = "modified"                # added | modified | deleted | renamed

    @classmethod
    def from_dict(cls, data: Any) -> "FileChange":
        if isinstance(data, str):
            return cls(path=data)
        data = _as_dict(data)
        return cls(
            path=_as_str(data.get("path")),
            added=_as_int(data.get("added")) or 0,
            removed=_as_int(data.get("removed")) or 0,
            kind=_as_str(data.get("kind"), "modified") or "modified",
        )


@dataclass
class Evidence(_Model):
    """Expected vs. observed, with a pointer to where it was seen."""

    summary: str = ""
    expected: str = ""
    observed: str = ""
    source: str = ""
    command: str = ""
    case_id: str = ""

    @classmethod
    def from_dict(cls, data: Any) -> "Evidence":
        data = _as_dict(data)
        return cls(
            summary=_as_str(data.get("summary")),
            expected=_as_str(data.get("expected")),
            observed=_as_str(data.get("observed")),
            source=_as_str(data.get("source")),
            command=_as_str(data.get("command")),
            case_id=_as_str(data.get("case_id")),
        )


@dataclass
class Signal(_Model):
    """One suspicious thing, with the metadata a reader needs to judge it."""

    rule_id: str = ""
    code: str = ""                        # GW-TEST-003, stable, for reports
    title: str = ""
    category: str = ""
    severity: str = Level.MEDIUM.value
    confidence: str = Level.MEDIUM.value
    explanation: str = ""
    files: list = field(default_factory=list)
    line: Optional[int] = None
    evidence: dict = field(default_factory=dict)
    remediation: str = ""
    requires_review: bool = False

    @classmethod
    def from_dict(cls, data: Any) -> "Signal":
        data = _as_dict(data)
        return cls(
            rule_id=_as_str(data.get("rule_id")),
            code=_as_str(data.get("code")),
            title=_as_str(data.get("title")),
            category=_as_str(data.get("category")),
            severity=Level.parse(data.get("severity")).value,
            confidence=Level.parse(data.get("confidence")).value,
            explanation=_as_str(data.get("explanation")),
            files=[_as_str(f) for f in _as_list(data.get("files"))],
            line=_as_int(data.get("line")),
            evidence=_as_dict(data.get("evidence")),
            remediation=_as_str(data.get("remediation")),
            requires_review=bool(data.get("requires_review", False)),
        )

    @property
    def path(self) -> str:
        return self.files[0] if self.files else ""

    def matches(self, other: "Signal") -> bool:
        return (self.rule_id, self.path, self.explanation) == (
            other.rule_id, other.path, other.explanation)


@dataclass
class VerificationResult(_Model):
    """What actually ran, and how it came out."""

    test_command: Optional[str] = None
    outcome: str = Outcome.NOT_REQUESTED.value
    tests_run: Optional[int] = None
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    duration_s: Optional[float] = None
    baseline: str = Outcome.NOT_REQUESTED.value
    baseline_detail: dict = field(default_factory=dict)
    heldout: str = Outcome.NOT_REQUESTED.value
    heldout_detail: dict = field(default_factory=dict)
    regressions: list = field(default_factory=list)
    newly_failing: list = field(default_factory=list)
    coverage: Optional[float] = None
    truncated: list = field(default_factory=list)
    redactions: int = 0
    evidence: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    harness_error: str = ""

    @classmethod
    def from_dict(cls, data: Any) -> "VerificationResult":
        data = _as_dict(data)
        return cls(
            test_command=data.get("test_command"),
            outcome=Outcome.parse(data.get("outcome")).value,
            tests_run=_as_int(data.get("tests_run")),
            tests_passed=_as_int(data.get("tests_passed")),
            tests_failed=_as_int(data.get("tests_failed")),
            duration_s=_as_float(data.get("duration_s")),
            baseline=Outcome.parse(data.get("baseline")).value,
            baseline_detail=_as_dict(data.get("baseline_detail")),
            heldout=Outcome.parse(data.get("heldout")).value,
            heldout_detail=_as_dict(data.get("heldout_detail")),
            regressions=[_as_str(r) for r in _as_list(data.get("regressions"))],
            newly_failing=[_as_str(r) for r in _as_list(data.get("newly_failing"))],
            coverage=_as_float(data.get("coverage")),
            truncated=[_as_str(t) for t in _as_list(data.get("truncated"))],
            redactions=_as_int(data.get("redactions")) or 0,
            evidence=[Evidence.from_dict(e) for e in _as_list(data.get("evidence"))],
            notes=[_as_str(n) for n in _as_list(data.get("notes"))],
            harness_error=_as_str(data.get("harness_error")),
        )

    @property
    def ran(self) -> bool:
        return self.outcome != Outcome.NOT_REQUESTED.value

    def summary_line(self) -> str:
        if not self.ran:
            return "not run"
        if self.tests_run is None:
            return self.outcome
        return f"{self.tests_passed or 0}/{self.tests_run}"


@dataclass
class Run(_Model):
    """One agent session (or one CLI invocation) that produced a claim."""

    id: str = ""
    agent: str = ""                       # "claude-code", "" when unknown
    model: str = ""
    repo: str = ""
    branch: str = ""
    base_commit: str = ""
    head_commit: str = ""
    started_at: str = ""
    ended_at: str = ""
    mode: str = "report"                  # report | enforce
    changed_files: list = field(default_factory=list)
    diff_stat: dict = field(default_factory=dict)
    claim: Optional[Claim] = None

    @classmethod
    def from_dict(cls, data: Any) -> "Run":
        data = _as_dict(data)
        return cls(
            id=_as_str(data.get("id")),
            agent=_as_str(data.get("agent")),
            model=_as_str(data.get("model")),
            repo=_as_str(data.get("repo")),
            branch=_as_str(data.get("branch")),
            base_commit=_as_str(data.get("base_commit")),
            head_commit=_as_str(data.get("head_commit")),
            started_at=_as_str(data.get("started_at")),
            ended_at=_as_str(data.get("ended_at")),
            mode=_as_str(data.get("mode"), "report") or "report",
            changed_files=[FileChange.from_dict(f) for f in _as_list(data.get("changed_files"))],
            diff_stat=_as_dict(data.get("diff_stat")),
            claim=Claim.from_dict(data["claim"]) if data.get("claim") else None,
        )

    def diff_summary(self) -> str:
        if not self.changed_files:
            return "no changes detected"
        added = sum(f.added for f in self.changed_files)
        removed = sum(f.removed for f in self.changed_files)
        count = len(self.changed_files)
        noun = "file" if count == 1 else "files"
        return f"{count} {noun} changed, +{added}/-{removed}"


@dataclass
class Confidence(_Model):
    """A score, the level it maps to, and the sentences that explain it."""

    score: int = 0
    level: str = Level.LOW.value
    reasons: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Any) -> "Confidence":
        data = _as_dict(data)
        return cls(
            score=_as_int(data.get("score")) or 0,
            level=Level.parse(data.get("level")).value,
            reasons=[_as_str(r) for r in _as_list(data.get("reasons"))],
        )

    def sentence(self) -> str:
        return f"{self.level} -- " + "; ".join(self.reasons) if self.reasons else self.level


@dataclass
class TrustReport(_Model):
    """The artifact. Everything above exists to fill this in."""

    schema_version: str = SCHEMA_VERSION
    generated_at: str = field(default_factory=utc_now)
    run: Optional[Run] = None
    verdict: str = Verdict.INCONCLUSIVE.value
    confidence: Optional[Confidence] = None
    verification: Optional[VerificationResult] = None
    signals: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    # ---- construction helpers -------------------------------------------------

    @classmethod
    def build(cls, run: Optional[Run] = None,
              signals: Optional[list] = None,
              verification: Optional[VerificationResult] = None,
              notes: Optional[list] = None) -> "TrustReport":
        from .confidence import score_signals  # local import: no import cycle

        report = cls(
            run=run or Run(),
            verification=verification or VerificationResult(),
            signals=list(signals or []),
            notes=list(notes or []),
        )
        report.confidence, report.verdict = score_signals(report)
        return report

    @classmethod
    def from_dict(cls, data: Any) -> "TrustReport":
        data = _as_dict(data)
        return cls(
            schema_version=_as_str(data.get("schema_version"), SCHEMA_VERSION) or SCHEMA_VERSION,
            generated_at=_as_str(data.get("generated_at"), utc_now()) or utc_now(),
            run=Run.from_dict(data["run"]) if data.get("run") else Run(),
            verdict=Verdict.parse(data.get("verdict")).value,
            confidence=(Confidence.from_dict(data["confidence"])
                        if data.get("confidence") else None),
            verification=(VerificationResult.from_dict(data["verification"])
                          if data.get("verification") else None),
            signals=[Signal.from_dict(s) for s in _as_list(data.get("signals"))],
            notes=[_as_str(n) for n in _as_list(data.get("notes"))],
        )

    # ---- queries -------------------------------------------------------------

    @property
    def is_clean(self) -> bool:
        return not self.signals and self.verdict == Verdict.VERIFIED.value

    def by_severity(self, severity: str) -> list:
        return [s for s in self.signals if s.severity == severity]

    @property
    def requires_review(self) -> list:
        return [s for s in self.signals if s.requires_review]

    def highlights(self) -> list:
        return [s for s in self.signals if s.severity == Level.HIGH.value]

    def to_json(self, indent: int = 2) -> str:
        payload = json.dumps(self.to_dict(), indent=indent, sort_keys=False)
        return payload
