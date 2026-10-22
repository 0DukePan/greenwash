"""The technique taxonomy: what a diff can do to fake a pass, and what catches it.

One versioned table, as data. Every tampering technique the tool knows is one
row, with the mechanism that catches it, whether catching it needs the replay
pipeline (the pinned original tests run against the agent's code), and its
current status. The coverage matrix `greenwash rules` prints is generated from
this table; the corpus names techniques from it; the docs pin `TAXONOMY_VERSION`
so coverage can be diffed between releases.

The honesty rule the rows follow: a technique either names a mechanism that
exists today, or it says `not covered`. A row may say `partial` where a
mechanism only surfaces the technique (an ask, not a conviction). Nothing here
grades the future -- the status column is what the tool does right now.

`validate_technique` is the seam other tickets call: a record naming a
technique this table does not know is rejected with the offending field named,
so a corpus case cannot cite a technique the detector never heard of.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

TAXONOMY_VERSION = "1"

COVERED = "covered"
PARTIAL = "partial"
NOT_COVERED = "not covered"
STATUSES = (COVERED, PARTIAL, NOT_COVERED)


@dataclass(frozen=True)
class Technique:
    id: str
    name: str
    mechanisms: tuple = ()        # rule or signal ids that catch it today
    replay: bool = False          # catching it needs the pinned original tests
    status: str = NOT_COVERED     # covered | partial | not covered


TECHNIQUES = (
    Technique(
        id="skip-or-xfail",
        name="a test disabled rather than fixed: skip, xfail, ignore, pending",
        mechanisms=("test-skipped",),
        replay=False,
        status=COVERED,
    ),
    Technique(
        id="deleted-test",
        name="a test deleted rather than fixed",
        mechanisms=("test-file-deleted", "test-weakened"),
        replay=True,
        status=COVERED,
    ),
    Technique(
        id="assertion-weakened",
        name="assertions removed or replaced with ones that cannot fail",
        mechanisms=("assertion-weakened", "test-weakened"),
        replay=True,
        status=COVERED,
    ),
    Technique(
        id="expected-value-change",
        name="an expected value inside a test changed to match the code",
        mechanisms=("test-weakened",),
        replay=True,
        status=PARTIAL,
    ),
    Technique(
        id="narrowed-parametrization",
        name="failing cases dropped from a parametrized test",
        mechanisms=("tests-not-run", "test-weakened"),
        replay=True,
        status=COVERED,
    ),
    Technique(
        id="mocked-unit",
        name="the unit under test mocked away so the test checks the mock",
        mechanisms=("mock-in-test", "test-weakened"),
        replay=True,
        status=COVERED,
    ),
    Technique(
        id="swallowed-exception",
        name="an exception caught and dropped so nothing fails",
        mechanisms=("swallowed-exception",),
        replay=False,
        status=COVERED,
    ),
    Technique(
        id="error-path-default",
        name="an error path turned into a default value nothing tests",
        mechanisms=("error-path-default",),
        replay=False,
        status=COVERED,
    ),
    Technique(
        id="harness-exit",
        name="the harness exits zero before the work runs",
        mechanisms=("known-exploit-pattern",),
        replay=False,
        status=COVERED,
    ),
    Technique(
        id="always-equal",
        name="an unconditional equality that makes any assertion pass",
        mechanisms=("known-exploit-pattern",),
        replay=False,
        status=COVERED,
    ),
    Technique(
        id="special-cased-input",
        name="a hardcoded return for the exact input a test asserts",
        mechanisms=("hardcoded-return",),
        replay=False,
        status=COVERED,
    ),
    Technique(
        id="conftest-edit",
        name="conftest.py edited to change what runs or what may pass",
        mechanisms=("conftest-changed",),
        replay=False,
        status=COVERED,
    ),
    Technique(
        id="spec-docstring-fixture-rewrite",
        name="the stated contract rewritten to match wrong behavior: a spec, "
             "docstring or fixture",
        status=NOT_COVERED,
    ),
    Technique(
        id="runner-config-tamper",
        name="runner or plugin configuration tampered so less runs or nothing "
             "fails -- verifier-config-changed only asks when a watched config "
             "file is touched",
        mechanisms=("verifier-config-changed",),
        replay=False,
        status=PARTIAL,
    ),
    Technique(
        id="report-tamper",
        name="the report or verdict edited after the fact",
        status=NOT_COVERED,
    ),
    Technique(
        id="gate-hook-tamper",
        name="the gate or hook tampered so the check never blocks -- "
             "verifier-config-changed only asks when a watched path is touched",
        mechanisms=("verifier-config-changed",),
        replay=False,
        status=PARTIAL,
    ),
)

BY_ID = {technique.id: technique for technique in TECHNIQUES}


def validate_technique(record, field: str = "technique") -> list:
    """The technique named by a record, checked against this table.

    Accepts the record itself (a mapping, read at `field`) or the name, so a
    caller validating a corpus case can extend its own issues with these
    verbatim. Every issue names the offending field: a record that names a
    technique this table does not know is rejected, never silently passed.
    """
    value = record.get(field) if isinstance(record, Mapping) else record
    name = value.strip() if isinstance(value, str) else ""
    if not name:
        return [f"{field}: missing; a record must name one technique from "
                f"taxonomy v{TAXONOMY_VERSION}"]
    if name not in BY_ID:
        known = ", ".join(BY_ID)
        return [f"{field}: unknown technique {name!r}; taxonomy "
                f"v{TAXONOMY_VERSION} knows: {known}"]
    return []
