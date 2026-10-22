#!/usr/bin/env python3
"""The claim ledger: one row per public claim, and the wording it may use.

A public sentence is a claim, and a claim is only as strong as the evidence
behind it. This module is that mapping, as data. Each row records the evidence a
stronger claim would require, what exists today, and the strongest wording
allowed today -- with every number in that wording computed from the generated
artifacts in `benchmark/results/`, never retyped from prose.

Two consumers read the same rows:

* `tests/test_claim_ledger.py` fails when a public page states more than a row
  allows (naming the claim and the page), when a row quotes a number no
  artifact backs, or when the limits page's table drifts from this data.
* `docs/what-did-not-work.md` renders its claim table from `table()`.

The gate is deliberately narrow. It catches wording no evidence can license
outright, and a claim asserted without the qualifiers its row requires. A
sentence that refuses, negates or hedges a claim is not an assertion of it, and
a section that exists to list forbidden phrasings is exempt while -- and only
while -- it exists to forbid them.

Usage:
    python benchmark/claim_ledger.py --table
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from report import wilson  # one interval implementation, in percent

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmark" / "results"

ASKING = {"mock-in-test", "swallowed-exception", "test-skipped",
          "assertion-weakened", "conftest-changed"}

# A sentence that refuses or negates a claim is not an assertion of it, and a
# promise about tomorrow is not evidence about today. `never` deliberately
# appears in neither list: "it never misses" is an over-claim, not a refusal.
NEGATION = re.compile(
    r"\bnot\b|does not|n't|cannot|nothing here|no evidence|unmeasured|unknown"
    r"|without|refus\w*|avoid\w*|barely|almost nothing", re.I)
PLAN = re.compile(
    r"\bneeds?\b|\bwill\b|\bshall\b|\bto be\b|planned|being built|\bfuture\b"
    r"|invitation|roadmap|\bnext\b|before claiming|\bpreregist\w*"
    r"|\bpre-register\w*|\baim\w*|\btbd\b", re.I)

# Headings under which phrasings are quoted in order to forbid them, and
# headings whose content is design or future work rather than a claim.
EXEMPT_HEADING = re.compile(
    r"phrases to avoid|does not (license|establish)|not establish"
    r"|do not (say|claim)|never (say|claim)", re.I)
PLAN_HEADING = re.compile(
    r"\bpreregist\w*|\bprotocol\b|roadmap|what is next|still open"
    r"|fixed conditions|registration|corpus authorship|what the result will",
    re.I)

HEADING = re.compile(r"^#{1,6}\s+(.*)$")
FENCE = re.compile(r"^\s*```")
SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Claim:
    claim: str                     # the claim, by id
    evidence: str                  # what a stronger claim would require
    status: str                    # what exists today
    allowed: str                   # strongest wording allowed today
    numbers: dict = field(default_factory=dict)  # values `allowed` quotes
    triggers: tuple = ()           # phrasings that assert this claim
    requires_any: tuple = ()       # qualifiers that must ride with them
    forbidden: tuple = ()          # phrasings no evidence can license


def _detection() -> dict:
    return json.loads((RESULTS / "detection.json").read_text(encoding="utf-8"))["summary"]


def _delta() -> dict:
    return json.loads((RESULTS / "agent-delta.json").read_text(encoding="utf-8"))


def _survey() -> dict:
    return json.loads((RESULTS / "fp-survey.json").read_text(encoding="utf-8"))


def rows() -> tuple:
    """One row per public claim the plan and the spec name in public."""
    s = _detection()
    recall_ci = wilson(s["either_caught"], s["tasks"])
    _, fp_high = wilson(s["false_positives"], s["solutions_clean"])
    d = _delta()
    survey = _survey()
    detail = [flag for repo in survey["repos"] for flag in repo["detail"]]
    asking = sum(1 for flag in detail if flag["kind"] in ASKING)

    if d.get("live"):
        lows = [row["ci"][0] for row in d["states"].values()]
        highs = [row["ci"][1] for row in d["states"].values()]
        behavioural = dict(
            numbers={"delta_points": d["delta_points"], "rows": d["rows"],
                     "ci_low": min(lows), "ci_high": max(highs),
                     "confidence": 95},
            allowed=("No measurable effect at this sample size: "
                     f"{d['delta_points']:+.1f} points over {d['rows']} scored "
                     "runs (95% CI [{:.0f}, {:.0f}] in every arm).".format(
                         min(lows), max(highs))))
    else:
        behavioural = dict(
            numbers={},
            allowed=("The behavioural effect is not measured yet; there is no "
                     "run to quote."))

    return (
        Claim(
            claim="detector-recall",
            evidence=("A frozen evaluation run on a corpus this project did "
                      "not author, at the pre-registered sample size."),
            status=("Measured on the first-party internal corpus only; the "
                    "frozen run has not happened."),
            allowed=("On a labelled corpus of {tasks} tasks with one planted "
                     "cheat each, the scanner caught {caught} of {tasks} "
                     "planted cheats (95% CI {lo}%-{hi}%).").format(
                tasks=s["tasks"], caught=s["either_caught"],
                lo=f"{recall_ci[0]:.1f}", hi=f"{recall_ci[1]:g}"),
            numbers={"caught": s["either_caught"], "tasks": s["tasks"],
                     "ci_low": round(recall_ci[0], 1),
                     "ci_high": round(recall_ci[1], 1), "confidence": 95},
            triggers=(r"100% recall", r"recall is 100",
                      r"catches every planted cheat",
                      r"caught every planted cheat", r"catches every cheat",
                      r"all planted cheats"),
            requires_any=(r"interval|\bCI\b|95%|corpus|sample",),
            forbidden=(r"always catches", r"never misses",
                       r"perfect (recall|detection)",
                       r"catches every (cheat|tamper|hack)"),
        ),
        Claim(
            claim="false-alarms",
            evidence=("A labelled sample of real code large enough for a rate, "
                      "not a hand-classified flag count."),
            status=("Measured on the recorded honest fixes of the internal "
                    "corpus only."),
            allowed=("It flagged {flagged} of {clean} recorded honest fixes "
                     "(95% upper bound {hi}% at this sample size).").format(
                flagged=s["false_positives"], clean=s["solutions_clean"],
                hi=f"{fp_high:.1f}"),
            numbers={"flagged": s["false_positives"],
                     "clean": s["solutions_clean"],
                     "ci_high": round(fp_high, 1), "confidence": 95},
            triggers=(r"0% false positives", r"no false positives",
                      r"zero false positives", r"false-positive rate is 0",
                      r"never flags", r"flagged no recorded honest fix"),
            requires_any=(r"upper bound|interval|\bCI\b|95%|sample|corpus"
                          r"|not the same",),
            forbidden=(r"no false positives at all",
                       r"never (produces|flags|raises) (a )?false",
                       r"false[- ]positive[- ]free",
                       r"eliminates false positives"),
        ),
        Claim(
            claim="behavioural-effect",
            evidence=("The pre-registered behavioural study: an independent "
                      "corpus, a pinned image, and an instrument that is not "
                      "the treatment."),
            status=("One live first-party run; the pages that quote it say it "
                    "predates the test-integrity check."),
            allowed=behavioural["allowed"],
            numbers=behavioural["numbers"],
            triggers=(r"reduces reward hacking", r"reduces cheating",
                      r"improves agent behavio", r"measurably (improves|reduces)",
                      r"cuts? cheating", r"less cheating"),
            requires_any=(r"null|no measurable effect|unmeasured|not measured"
                          r"|pilot|predates|this corpus|this sample|this model"
                          r"|interval|refus",),
            forbidden=(r"prevents reward hacking", r"stops reward hacking",
                       r"eliminates (reward hacking|cheating)"),
        ),
        Claim(
            claim="fp-survey",
            evidence=("A labelled sample of real code; classifying flags by "
                      "hand gives a number, not a population estimate."),
            status=("A survey of recent history in three repositories, "
                    "published for inspection."),
            allowed=("On the recent history of {repos} repositories "
                     "({commits} commits, {files:,} file changes) the scanner "
                     "produced {flags} flags: {asking} are the rules that "
                     "always ask for an explanation, {genuine} are genuine "
                     "false positives. This is a survey, not a rate.").format(
                repos=len(survey["totals"]["repos"]),
                commits=survey["totals"]["commits"],
                files=survey["totals"]["files"], flags=len(detail),
                asking=asking, genuine=len(detail) - asking),
            numbers={"repos": len(survey["totals"]["repos"]),
                     "commits": survey["totals"]["commits"],
                     "files": survey["totals"]["files"], "flags": len(detail),
                     "asking": asking, "genuine": len(detail) - asking},
            triggers=(r"false[- ]positive rate (is|of) [1-9]",
                      r"false positives? (is|are) \d+\s*%"),
            requires_any=(r"survey|not a rate|by hand|hand-classified"
                          r"|population|flags",),
        ),
        Claim(
            claim="first-party-corpus",
            evidence=("Corpus authorship independent of this project, with "
                      "merge authority outside it."),
            status="Not established; the governance documents are the invitation.",
            allowed=("The corpus is first-party: it measures the detector "
                     "against its own authors' idea of a cheat and cannot "
                     "establish detector quality."),
            numbers={},
            triggers=(r"independent (corpus|benchmark|evaluation)",
                      r"independently (authored|validated|verified|built)",
                      r"externally validated"),
            requires_any=(r"planned|will|being built|future|separate|invitation"
                          r"|governance|pending|did not author|pre-register",),
        ),
        Claim(
            claim="rate-claims",
            evidence=("The frozen run at the pre-registered sample size; until "
                      "then every number is a count with an interval."),
            status="Not available; the current corpus is first-party and small.",
            allowed=("Every published number is an interval-qualified count on "
                     "the internal corpus; a rate claim waits on the frozen "
                     "run."),
            numbers={},
            triggers=(r"\d+(?:\.\d+)?\s*%\s*(recall|accuracy|precision|detection)",
                      r"(recall|accuracy|precision|detection) (?:rate )?(?:is|of) \d"),
            requires_any=(r"interval|\bCI\b|bound|corpus|sample",),
        ),
        Claim(
            claim="strength-advisory",
            evidence=("The strength check's error rate, measured; promotion to "
                      "a verdict is deliberately deferred."),
            status="Ships as an advisory flag in this version.",
            allowed=("The strength check ships as an advisory flag, not a "
                     "verdict; promotion waits until its error rate is "
                     "measured."),
            numbers={},
            triggers=(r"weak[-_ ]?verifier (verdict )?(is |are )?(emitted|produced|returned|shipped)",
                      r"(emits|produces|returns|ships) (a |the )?weak[-_ ]?verifier",
                      r"strength (check|score|model) (proves|certifies|measures|detects)",
                      r"certifies (test|suite) (strength|quality)",
                      r"detects weak (tests|suites)"),
            requires_any=(r"advisory|flag|deferred|not a verdict|not promoted|wait",),
            forbidden=(r"certifies (the )?(tests?|suite)",
                       r"proves the (tests?|suite) (are|is) (strong|adequate)"),
        ),
        Claim(
            claim="verdict-vocabulary",
            evidence=("Correctness proofs, which no run of this tool produces."),
            status="A verdict reports the checks that ran and the diff's shape.",
            allowed=("A verdict reports the checks that ran; it is evidence, "
                     "not proof of correctness."),
            numbers={},
            triggers=(r"proves? (the )?(code|tests?|test suite|work|correctness)",
                      r"proof of correctness", r"guarantees? correctness"),
            requires_any=(r"\bnot\b|report|never|evidence|means",),
            forbidden=(r"proves the code is correct",
                       r"proves the tests are honest",
                       r"guarantees? correctness",
                       r"guarantees? the (code|work) is correct"),
        ),
        Claim(
            claim="scope-exclusions",
            evidence=("Retrieval and leakage detection; training-time reward "
                      "hacking; languages beyond Python and pytest."),
            status="Out of scope for this version; never claimed.",
            allowed=("What greenwash does not cover: retrieval and leakage "
                     "detection, training-time reward hacking, languages "
                     "beyond Python and pytest in this version."),
            numbers={},
            triggers=(r"(catches|detects|prevents|covers) (retrieval|leakage|training-time)",),
            requires_any=(r"out of scope|not covered|does not|never|cannot",),
            forbidden=(r"prevents training-time",
                       r"catches? (retrieval|data) leak\w*"),
        ),
    )


def table() -> str:
    """The limits page's claim table, generated from the rows above."""
    lines = ["| Claim | Evidence required | Status | Strongest wording allowed today |",
             "|---|---|---|---|"]
    for row in rows():
        lines.append(f"| {row.claim} | {row.evidence} | {row.status} "
                     f"| {row.allowed} |")
    return "\n".join(lines)


def public_pages() -> tuple:
    """The pages a reader meets: the README, the benchmark page, the docs.

    `docs/specs/` is excluded on purpose -- specifications are internal plans,
    not published claims.
    """
    pages = ["README.md", "BENCHMARK.md"]
    pages += [path.relative_to(ROOT).as_posix()
              for path in sorted((ROOT / "docs").rglob("*.md"))
              if "specs" not in path.relative_to(ROOT).parts]
    return tuple(pages)


def check_pages(pages: dict) -> list:
    """Every way `pages` states more than the ledger allows, named."""
    violations = []
    for name, text in pages.items():
        violations.extend(_page_violations(name, text))
    return sorted(set(violations))


def _page_violations(name: str, text: str) -> list:
    """Scan a page sentence by sentence.

    Wrapped prose lines are joined before splitting, because a claim sentence
    may wrap; a markdown table row is its own unit, because a row is its own
    claim. Fenced blocks are receipts and transcripts, not claims.
    """
    out, block = [], []
    heading = title = ""
    in_fence = False

    def flush():
        if block:
            out.extend(_unit_violations(name, " ".join(block), heading, title))
            block.clear()

    for line in text.splitlines():
        if FENCE.match(line):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if match:
            flush()
            heading = match.group(1)
            title = title or heading
            continue
        if not line.strip():
            flush()
            continue
        if line.lstrip().startswith("|"):
            flush()
            out.extend(_unit_violations(name, line.strip(), heading, title))
            continue
        block.append(line.strip())
    flush()
    return out


def _unit_violations(name: str, unit: str, heading: str, title: str) -> list:
    out = []
    section_exempt = bool(EXEMPT_HEADING.search(f"{title} {heading}"))
    plan_context = bool(PLAN_HEADING.search(f"{title} {heading}"))
    for sentence in SENTENCE.split(unit):
        sentence = sentence.strip()
        if not sentence or section_exempt:
            continue
        negated = bool(NEGATION.search(sentence))
        planned = plan_context or bool(PLAN.search(sentence))
        for row in rows():
            if not negated and any(re.search(p, sentence, re.I)
                                   for p in row.forbidden):
                out.append(_violation(name, row, sentence,
                                      "uses wording no evidence licenses"))
            if negated or planned:
                continue
            if any(re.search(p, sentence, re.I) for p in row.triggers):
                if not any(re.search(p, sentence, re.I) for p in row.requires_any):
                    out.append(_violation(name, row, sentence,
                                          "claims more than the ledger allows"))
    return out


def _violation(name: str, row: Claim, sentence: str, why: str) -> str:
    return (f"{name}: claim '{row.claim}' {why}: {sentence!r} -- "
            f"strongest wording allowed today: {row.allowed}")


if __name__ == "__main__":
    if "--table" in sys.argv:
        print(table())
    else:
        print(__doc__)
