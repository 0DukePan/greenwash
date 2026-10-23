"""The claim ledger gates public wording.

Every public claim gets a row in `benchmark/claim_ledger.py`: the evidence a
stronger claim would require, what exists today, and the strongest wording
allowed today. Prose that outruns its evidence is the same defect the docs-pin
tests catch for numbers -- a sentence that was true once, or was never measured
at all -- so it is a test now.

The over-claim check is proved against a planted fixture rather than a real
page: `tests/fixtures/over-claimed-page.md` over-claims on purpose, and the
very assertion the docs test makes must fail on it, naming the claim and the
page. That fixture is why a real page can never over-claim unnoticed.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmark" / "results"
sys.path.insert(0, str(ROOT / "benchmark"))

import claim_ledger  # noqa: E402
from report import wilson  # noqa: E402  one interval implementation

ASKING = {"mock-in-test", "swallowed-exception", "test-skipped",
          "assertion-weakened", "conftest-changed"}

# Every claim the positioning plan and the spec name in public. One ledger row
# each; a claim here without a row is a claim nobody is gating.
PLAN_CLAIMS = {
    # Further Notes: "Eleven detections in eleven cases has a lower bound..."
    "detector-recall",
    # Further Notes: "zero false alarms ... has an upper bound..."
    "false-alarms",
    # Further Notes: "The three-run behavioral pilot says almost nothing."
    "behavioural-effect",
    # Further Notes / the survey pages: a flag count is not a rate.
    "fp-survey",
    # Further Notes and the limits page: the corpus is first-party.
    "first-party-corpus",
    # Further Notes: "The claim ledger must keep those intervals in every
    # public sentence until the frozen run lands." + the sample-size floors.
    "rate-claims",
    # Open decision D4: the strength check ships advisory, never a verdict.
    "strength-advisory",
    # User story 17: a suspicious pattern alone never becomes a tampering
    # claim; the vocabulary table says what a verdict does not mean.
    "verdict-vocabulary",
    # User story 8 / Out of Scope: retrieval leaks and training-time reward
    # hacking are explicitly not covered.
    "scope-exclusions",
}

# A digit is required: "near the bound" is prose, "86.2" is a number.
NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")


def assert_within_ledger(pages: dict) -> None:
    """The docs assertion itself: no page may state more than the ledger."""
    violations = claim_ledger.check_pages(pages)
    assert violations == [], (
        "public pages state more than the ledger allows:\n" + "\n".join(violations))


def renderings(values) -> set:
    """Every form a value may legitimately take inside allowed wording."""
    out = set()
    for value in values:
        if isinstance(value, float):
            out.update({str(value), f"{value:g}", f"{value:.1f}", f"{value:.0f}"})
            if value.is_integer():
                out.add(str(int(value)))
        else:
            out.update({str(value), f"{value:,}", f"{value:g}"})
    return out


def expected_numbers(claim: str) -> dict:
    """Recomputed here from the generated artifacts, never from the ledger."""
    if claim == "detector-recall":
        s = json.loads((RESULTS / "detection.json").read_text(encoding="utf-8"))["summary"]
        low, high = wilson(s["either_caught"], s["tasks"])
        return {"caught": s["either_caught"], "tasks": s["tasks"],
                "ci_low": round(low, 1), "ci_high": round(high, 1),
                "confidence": 95}
    if claim == "false-alarms":
        s = json.loads((RESULTS / "detection.json").read_text(encoding="utf-8"))["summary"]
        _, high = wilson(s["false_positives"], s["solutions_clean"])
        return {"flagged": s["false_positives"], "clean": s["solutions_clean"],
                "ci_high": round(high, 1), "confidence": 95}
    if claim == "behavioural-effect":
        d = json.loads((RESULTS / "agent-delta.json").read_text(encoding="utf-8"))
        if not d.get("live"):
            return {}
        lows = [row["ci"][0] for row in d["states"].values()]
        highs = [row["ci"][1] for row in d["states"].values()]
        return {"delta_points": d["delta_points"], "rows": d["rows"],
                "ci_low": min(lows), "ci_high": max(highs), "confidence": 95}
    if claim == "fp-survey":
        data = json.loads((RESULTS / "fp-survey.json").read_text(encoding="utf-8"))
        detail = [flag for repo in data["repos"] for flag in repo["detail"]]
        asking = sum(1 for flag in detail if flag["kind"] in ASKING)
        return {"repos": len(data["totals"]["repos"]), "commits": data["totals"]["commits"],
                "files": data["totals"]["files"], "flags": len(detail),
                "asking": asking, "genuine": len(detail) - asking}
    return {}


def test_every_claim_in_the_positioning_plan_has_a_ledger_row():
    rows = {row.claim: row for row in claim_ledger.rows()}
    for claim in sorted(PLAN_CLAIMS):
        assert claim in rows, f"the ledger has no row for the {claim} claim"
        row = rows[claim]
        assert row.evidence, f"{claim} does not say what evidence it requires"
        assert row.status, f"{claim} does not say what exists today"
        assert row.allowed, f"{claim} has no strongest allowed wording"


def test_a_planted_over_claim_fails_the_docs_assertion_naming_the_claim_and_page():
    """The proof that the over-claim test can fail.

    The fixture plants one over-claim per measured claim. The assertion below
    is the exact assertion `test_public_pages_state_no_more_than_the_ledger_
    allows` makes; here it must raise, and its message must name each claim
    and the page. If the gate ever stops noticing, this test fails instead.
    """
    name = "tests/fixtures/over-claimed-page.md"
    planted = {name: (ROOT / name).read_text(encoding="utf-8")}
    with pytest.raises(AssertionError) as raised:
        assert_within_ledger(planted)
    message = str(raised.value)
    assert name in message, f"the failure does not name the page {name}"
    for claim in ("detector-recall", "false-alarms", "behavioural-effect",
                  "strength-advisory"):
        assert claim in message, f"the failure does not name the {claim} claim"


def test_public_pages_state_no_more_than_the_ledger_allows():
    pages = {name: (ROOT / name).read_text(encoding="utf-8")
             for name in claim_ledger.public_pages()}
    assert pages, "no public pages found to gate"
    assert_within_ledger(pages)


def test_the_limits_page_renders_its_claim_table_from_the_ledger():
    page = (ROOT / "docs" / "what-did-not-work.md").read_text(encoding="utf-8")
    rendered = re.search(
        r"<!-- claim-ledger:begin -->\n(.*?)\n<!-- claim-ledger:end -->", page, re.S)
    assert rendered, "the limits page has no generated claim table"
    assert rendered.group(1).strip() == claim_ledger.table().strip(), (
        "the limits-page table is not the ledger verbatim; regenerate it with "
        "python benchmark/claim_ledger.py --table")


def test_allowed_wording_numbers_come_from_generated_artifacts():
    for row in claim_ledger.rows():
        expected = expected_numbers(row.claim)
        assert row.numbers == expected, (
            f"{row.claim} quotes {row.numbers} but the artifacts say {expected}")
        quoted = set(NUMBER.findall(row.allowed))
        backed = renderings(row.numbers.values())
        assert quoted <= backed, (
            f"{row.claim} quotes {sorted(quoted - backed)} in its allowed "
            "wording without an artifact behind it")


def test_every_claim_has_a_source_type_and_limitation():
    claims = {row.claim for row in claim_ledger.rows()}
    assert claims == set(claim_ledger.SOURCE_TYPES), (
        "a claim has no source type, or a source row has no claim")
    for claim, (source, limitation) in claim_ledger.SOURCE_TYPES.items():
        assert source in claim_ledger.SOURCE_VOCABULARY, (claim, source)
        assert len(limitation) > 20, f"{claim} has no real limitation sentence"


def test_the_claim_matrix_is_generated_not_typed():
    committed = (ROOT / "docs" / "claim-matrix.md").read_text(encoding="utf-8").strip()
    assert committed == claim_ledger.matrix().strip(), (
        "docs/claim-matrix.md is stale; regenerate it with "
        "python benchmark/claim_ledger.py --matrix")
