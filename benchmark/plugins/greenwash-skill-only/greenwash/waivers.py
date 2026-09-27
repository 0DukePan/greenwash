"""Waivers: a written, bounded decision that a finding is not going to be fixed.

Strict mode blocks on a suspicious finding unless someone with a name decided
otherwise -- in writing, for a bounded time, against the exact finding the
scanner produced. That decision is a waiver, and it is committed next to the
code it excuses:

    .greenwash/waivers.json

Four properties make it auditable rather than an ignore list:

* a waiver binds **one rule, one path, and one fingerprint** -- the fingerprint
  is taken over the signal's code, path, line and evidence, so editing the line
  it was written for invalidates it;
* it carries a **reviewer** (`@name`) and a **reason**, both required, so
  "waived" always has an answer to "by whom, and why";
* it **expires**: 30 days is the ceiling, and an expired waiver stays in the
  report as an expired waiver rather than disappearing;
* a valid waiver is reported as **waived with review**, never as clean.

Nothing here decides anything. `apply` annotates signals and returns the rows
that strict mode then reads -- the waiver is data, and the gate is policy, so
one file can be audited without reading the other.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

MAX_LIFETIME_DAYS = 30
MIN_REASON_CHARS = 20
DIR = ".greenwash"
FILE = "waivers.json"
VERSION = 1

#: A waiver's lifecycle. Only ACTIVE permits anything.
ACTIVE = "active"
EXPIRED = "expired"
STALE = "stale"          # rule and path match, the finding itself changed
UNMATCHED = "unmatched"  # nothing in this diff matches it at all
MALFORMED = "malformed"  # unreadable or invalid: it cannot be honoured

REVIEWER_PATTERN = re.compile(r"^@[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})$")
FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

#: Rows that strict mode refuses to run past.
BLOCKING = (EXPIRED, STALE, MALFORMED)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_time(value) -> Optional[datetime]:
    """A date or an ISO timestamp, as UTC. None when it cannot be read."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def fingerprint(signal) -> str:
    """`sha256:...` over what makes a finding that finding.

    Rule, path, line and the rule's own evidence go in. The line number is the
    point: a waiver is written against a specific place in a specific revision,
    and the next commit that moves it produces a different digest, which is
    what makes a stale waiver visible instead of silently permissive.
    """
    payload = {
        "code": signal.code or signal.rule_id,
        "path": signal.path,
        "line": signal.line,
        "evidence": {k: signal.evidence[k] for k in sorted(signal.evidence)},
    }
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class Waiver:
    """One committed decision."""

    id: str = ""
    rule_id: str = ""
    signal_fingerprint: str = ""
    path: str = ""
    reason: str = ""
    reviewer: str = ""
    created_at: str = ""
    expires_at: str = ""
    problem: str = ""          # set when the entry itself could not be read

    @classmethod
    def from_dict(cls, data) -> "Waiver":
        if not isinstance(data, dict):
            return cls(problem="entry is not a JSON object")
        return cls(
            id=str(data.get("id") or "").strip(),
            rule_id=str(data.get("rule_id") or "").strip(),
            signal_fingerprint=str(data.get("signal_fingerprint") or "").strip(),
            path=str(data.get("path") or "").strip().replace("\\", "/"),
            reason=str(data.get("reason") or "").strip(),
            reviewer=str(data.get("reviewer") or "").strip(),
            created_at=str(data.get("created_at") or "").strip(),
            expires_at=str(data.get("expires_at") or "").strip(),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "signal_fingerprint": self.signal_fingerprint,
            "path": self.path,
            "reason": self.reason,
            "reviewer": self.reviewer,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }

    # ---- validation ----------------------------------------------------------

    def problems(self, rules: Optional[dict] = None) -> list:
        """Everything wrong with this entry, in the order a reviewer reads it."""
        found: list[str] = []
        if self.problem:
            return [self.problem]

        if not self.id:
            found.append("id is required")
        if not self.rule_id:
            found.append("rule_id is required")
        elif rules is not None and self.rule_id not in rules:
            known = ", ".join(sorted(rules))
            found.append(f"unknown rule {self.rule_id!r} (known: {known})")
        if not FINGERPRINT_PATTERN.match(self.signal_fingerprint):
            found.append("signal_fingerprint must be sha256:<64 hex characters>")

        if not self.path:
            found.append("path is required")
        elif self.path.startswith("/") or ".." in self.path.split("/"):
            found.append("path must be repository-relative")

        if len(self.reason) < MIN_REASON_CHARS:
            found.append("reason must be a sentence, not a word "
                         f"(at least {MIN_REASON_CHARS} characters)")
        if not REVIEWER_PATTERN.match(self.reviewer):
            found.append("reviewer must be a handle like @maintainer")

        created, expires = parse_time(self.created_at), parse_time(self.expires_at)
        if created is None:
            found.append("created_at must be a date or an ISO timestamp")
        if expires is None:
            found.append("expires_at must be a date or an ISO timestamp")
        if created and expires:
            if expires <= created:
                found.append("expires_at must be after created_at")
            elif expires - created > timedelta(days=MAX_LIFETIME_DAYS):
                found.append(f"lifetime exceeds the {MAX_LIFETIME_DAYS}-day maximum")
        return found

    # ---- queries -------------------------------------------------------------

    def expiry(self) -> Optional[datetime]:
        return parse_time(self.expires_at)

    def status(self, now: Optional[datetime] = None) -> str:
        if self.problems():
            return MALFORMED
        moment = now or utc_now()
        expiry = self.expiry()
        return ACTIVE if expiry and expiry > moment else EXPIRED

    def matches_rule(self, signal) -> bool:
        """The rule may be named by its id or by its report code."""
        return self.rule_id in (signal.code, signal.rule_id)

    def summary(self) -> str:
        return (f"{self.id} [{self.rule_id}] {self.path} by {self.reviewer}, "
                f"expires {self.expires_at[:10]}")


@dataclass
class Ledger:
    """`.greenwash/waivers.json` as loaded."""

    path: str = ""
    waivers: list = field(default_factory=list)
    problems: list = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.waivers) or bool(self.problems)


@dataclass
class Row:
    """One waiver's fate against one diff."""

    waiver: Waiver
    status: str
    note: str = ""

    @property
    def blocking(self) -> bool:
        return self.status in BLOCKING

    def line(self) -> str:
        suffix = f" -- {self.note}" if self.note else ""
        return f"{self.waiver.summary()}{suffix}"

    def to_dict(self) -> dict:
        entry = self.waiver.to_dict()
        entry["status"] = self.status
        entry["note"] = self.note
        return entry


@dataclass
class Application:
    """Signals annotated, plus the rows strict mode reads."""

    rows: list = field(default_factory=list)
    signals: list = field(default_factory=list)

    @property
    def blocking(self) -> list:
        return [row for row in self.rows if row.blocking]

    @property
    def active(self) -> list:
        return [row for row in self.rows if row.status == ACTIVE]


def ledger_path(root=".") -> Path:
    return Path(root) / DIR / FILE


def load(root=".") -> Ledger:
    """Read the ledger. A broken file is a problem, never an exception.

    A waiver file that cannot be parsed must not stop a report: it is recorded
    as malformed, and strict mode refuses to pass on it. Silence would be the
    one unacceptable outcome, because it would read as "nothing to declare".
    """
    path = ledger_path(root)
    ledger = Ledger(path=str(path))
    if not path.is_file():
        return ledger
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        ledger.problems.append(f"could not read {path} ({exc})")
        return ledger
    if not isinstance(data, dict) or not isinstance(data.get("waivers"), list):
        ledger.problems.append(f"{path} has no \"waivers\" list")
        return ledger
    ledger.waivers = [Waiver.from_dict(entry) for entry in data["waivers"]]
    seen: set = set()
    for waiver in ledger.waivers:
        if waiver.id and waiver.id in seen and not waiver.problem:
            waiver.problem = f"duplicate id {waiver.id}"
        seen.add(waiver.id)
    return ledger


def next_id(waivers: Iterable[Waiver], year: Optional[int] = None) -> str:
    """`GW-YYYY-NNNN`, counting up from what the ledger already holds."""
    year = year or utc_now().year
    used = 0
    for waiver in waivers:
        parts = waiver.id.split("-")
        if len(parts) == 3 and parts[0] == "GW" and parts[1] == str(year):
            try:
                used = max(used, int(parts[2]))
            except ValueError:
                continue
    return f"GW-{year}-{used + 1:04d}"


def save(ledger: Ledger, root=".") -> str:
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": VERSION,
               "waivers": [waiver.to_dict() for waiver in ledger.waivers]}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(path)


def record(waiver: Waiver, root=".") -> Ledger:
    """Append to the ledger and write it back. Returns the new ledger."""
    ledger = load(root)
    ledger.waivers.append(waiver)
    ledger.problems = []
    save(ledger, root)
    return ledger


def known_rules() -> dict:
    """Rule ids and codes -> the code, from the one source of truth.

    A waiver may name either form; `GW-DIV-002` is what a report prints, and
    `error-path-default` is what `.greenwash/config.json` uses, so both resolve.
    """
    from . import scan as scan_mod
    from .verify import signals as verify_signals

    rules = [*scan_mod.RULES,
             *(getattr(verify_signals, name) for name in verify_signals.__all__)]
    table: dict = {}
    for rule in rules:
        table[rule.id] = rule.code
        table[rule.code] = rule.code
    return table


def apply(signals: Iterable, ledger: Ledger,
          now: Optional[datetime] = None) -> Application:
    """Annotate every signal a waiver covers, and classify every waiver.

    Signatures are matched on rule and path first, then confirmed by
    fingerprint -- so a waiver whose finding still exists but has changed is
    reported as `stale` rather than quietly failing to match.
    """
    signals = list(signals)
    moment = now or utc_now()
    application = Application(signals=signals)

    for waiver in ledger.waivers:
        status = waiver.status(moment)
        note = ""
        if status == MALFORMED:
            reason = "; ".join(waiver.problems()[:2])
            note = f"not honoured ({reason})"
        else:
            same_rule = [s for s in signals if waiver.matches_rule(s)]
            exact = [s for s in same_rule
                     if waiver.path == s.path
                     and waiver.signal_fingerprint == fingerprint(s)]
            if exact:
                if status == ACTIVE:
                    note = "waived with review"
                else:
                    note = (f"waiver expired {waiver.expires_at[:10]} -- "
                            "the finding is unwaived again")
                for signal in exact:
                    signal.waiver = {"id": waiver.id, "reviewer": waiver.reviewer,
                                     "reason": waiver.reason,
                                     "expires_at": waiver.expires_at,
                                     "status": status}
            elif any(waiver.path == s.path for s in same_rule):
                status = STALE
                note = ("the finding on this path changed since the waiver was "
                        "written, so it no longer applies")
            else:
                status = UNMATCHED
                note = "nothing in this diff matches it"
        application.rows.append(Row(waiver=waiver, status=status, note=note))

    return application
