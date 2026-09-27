"""The launch documents quote numbers, so the numbers get checked.

The README is guarded in both directions already. The launch kit is where the
same numbers get quoted most often -- in a one-pager, a "what did not work"
section, a results-interpretation guide and a release post -- and a number that
moves in an artifact while the prose stays put is the same defect the rest of
this repository exists to catch. Guarding it here means the fix is a failing
test, not a reader noticing three pages later.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
RESULTS = ROOT / "benchmark" / "results"


def text(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def flat(name: str) -> str:
    return " ".join(text(name).split())


def delta() -> dict:
    return json.loads((RESULTS / "agent-delta.json").read_text(encoding="utf-8"))


def detection() -> dict:
    return json.loads((RESULTS / "detection.json").read_text(encoding="utf-8"))["summary"]


def rows() -> list:
    blob = (RESULTS / "delta.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in blob.splitlines() if line.strip()]


def survey() -> dict:
    data = json.loads((RESULTS / "fp-survey.json").read_text(encoding="utf-8"))
    detail = [flag for repo in data["repos"] for flag in repo["detail"]]
    asking = {"mock-in-test", "swallowed-exception", "test-skipped",
              "assertion-weakened", "conftest-changed"}
    return {"total": len(detail),
            "asking": sum(1 for flag in detail if flag["kind"] in asking),
            "genuine": sum(1 for flag in detail if flag["kind"] not in asking)}


# ---- the benchmark one-pager -------------------------------------------------

def test_the_one_pager_states_the_measured_delta():
    measured = delta()
    page = flat("benchmark-summary.md")
    assert f"{measured['delta_points']:+.1f} points" in page
    assert "no measurable effect" in page.lower()


def test_the_one_pager_states_every_arm():
    measured = delta()
    page = flat("benchmark-summary.md")
    for state, row in measured["states"].items():
        assert f"`{state}`" in page, f"the page does not name the {state} arm"
        assert str(row["silent_cheats"]) in page, f"the page omits {state}'s cheat count"
        assert str(row["runs"]) in page, f"the page omits {state}'s run count"


def test_the_one_pager_states_the_detector_numbers():
    summary = detection()
    page = flat("benchmark-summary.md")
    assert f"{summary['either_caught']} / {summary['tasks']}" in page
    assert f"{summary['false_positives']} / {summary['solutions_clean']}" in page
    assert str(summary["runtime_seconds"]) + "s" in page


def test_the_one_pager_states_the_false_positive_survey():
    measured = survey()
    page = flat("benchmark-summary.md")
    assert f"| Total | {measured['total']} |" in page
    assert f"| The rules that always ask for an explanation | {measured['asking']} |" in page
    assert f"| Genuine false positives | {measured['genuine']} |" in page
    assert "not a rate" in page, "the page must say the survey is not a rate"


def test_the_one_pager_links_the_raw_artifacts():
    page = text("benchmark-summary.md")
    for artifact in ("benchmark/results/detection.json", "benchmark/results/delta.jsonl",
                     "benchmark/results/agent-delta.json", "benchmark/results/fp-survey.json",
                     "benchmark/RESULTS.md", "BENCHMARK.md"):
        assert artifact in page, f"the one-pager does not link {artifact}"


# ---- what did not work -------------------------------------------------------

def test_the_limits_page_states_the_null_with_its_rows():
    measured = delta()
    page = flat("what-did-not-work.md")
    assert f"{measured['delta_points']:+.1f} points" in page
    assert str(measured["rows"]) in page
    for state, row in measured["states"].items():
        assert f"{row['runs']}" in page or f"three runs each" in page


def test_the_limits_page_names_the_silent_cheats_it_claims():
    """`all 16 were mock or swallow, nine of them one task` is a checked claim."""
    silent = [row for row in rows() if row.get("outcome") == "silent cheat"]
    by_task: dict = {}
    by_cheat: dict = {}
    for row in silent:
        by_task[row["task"]] = by_task.get(row["task"], 0) + 1
        by_cheat[row.get("cheat_type", "?")] = by_cheat.get(row.get("cheat_type", "?"), 0) + 1

    page = flat("what-did-not-work.md")
    assert str(len(silent)) in page
    worst_task, worst_count = max(by_task.items(), key=lambda item: item[1])
    assert worst_task in page, f"{worst_task} is the worst task; the page does not name it"
    assert str(worst_count) in page, f"it accounts for {worst_count} of them"
    for cheat in by_cheat:
        assert cheat in page, f"the page does not mention the {cheat} class"


def test_the_limits_page_states_the_survey_split():
    measured = survey()
    page = flat("what-did-not-work.md")
    assert str(measured["total"]) in page
    assert str(measured["genuine"]) in page


# ---- result interpretation ---------------------------------------------------

def test_the_interpretation_page_states_every_interval():
    measured = delta()
    page = flat("RESULT_INTERPRETATION.md")
    for row in measured["states"].values():
        low, high = row["ci"]
        assert f"[{low:.0f}, {high:.0f}]" in page, f"missing the interval [{low}, {high}]"


def test_the_interpretation_page_keeps_the_detector_intervals():
    page = text("RESULT_INTERPRETATION.md")
    assert "86.2" in page and "13.8" in page, (
        "recall and the false-positive upper bound belong next to the numbers "
        "they qualify")


# ---- release post and citation ----------------------------------------------

def test_the_release_post_does_not_outrun_the_evidence():
    page = flat("releases/0.4.2.md")
    assert "no measurable effect" in page.lower()
    for forbidden in ("prevents reward hacking", "proves correctness",
                      "always catches", "guarantees"):
        assert forbidden not in page.lower(), f"the release post claims {forbidden!r}"


def test_no_launch_document_promises_an_effect():
    """Every page but one is scanned whole.

    `RESULT_INTERPRETATION.md` has a section that names the phrasings not to
    use -- "prevents reward hacking" among them -- so scanning it whole would
    flag the page that exists to forbid them. Its "phrases to avoid" section is
    dropped before the check, and the rest of that page is still scanned.
    """
    for name in ("benchmark-summary.md", "what-did-not-work.md", "report-vs-strict.md",
                 "ADOPTION_GUIDE.md", "launch-post.md", "releases/0.4.2.md",
                 "RESULT_INTERPRETATION.md", "launch-sequence.md"):
        page = flat(name).lower()
        marker = "phrases to avoid"
        if marker in page:
            page = page[:page.index(marker)]
        for forbidden in ("prevents reward hacking", "proves the code is correct",
                          "guarantees correctness"):
            assert forbidden not in page, f"{name} claims {forbidden!r}"


def test_the_interpretation_page_still_warns_about_those_phrases():
    page = flat("RESULT_INTERPRETATION.md").lower()
    assert "phrases to avoid" in page
    assert "prevents reward hacking" in page, (
        "the exemption above is only valid while this section exists")


def test_the_citation_version_matches_the_package():
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    assert f'version: "{version}"' in citation
    assert f"date-released" in citation


def test_the_citation_parses_as_yaml():
    yaml = __import__("pytest").importorskip("yaml", reason="PyYAML is not installed")
    data = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert data["cff-version"]
    assert data["title"] == "greenwash"
    assert data["license"] == "MIT"


# ---- the community files the recruitment step depends on ---------------------

def test_the_community_files_exist():
    for name in ("CODE_OF_CONDUCT.md", "SECURITY.md", "SUPPORT.md", "CITATION.cff",
                 "CODEOWNERS", "CONTRIBUTING.md", "docs/ADOPTION_GUIDE.md",
                 "docs/WAIVER_POLICY.md", "docs/EVALUATION_PROTOCOL.md",
                 "docs/RESULT_INTERPRETATION.md", "docs/benchmark-summary.md",
                 "docs/what-did-not-work.md", "docs/report-vs-strict.md",
                 "docs/launch-sequence.md", "docs/launch-post.md",
                 "docs/releases/0.4.2.md", "docs/social-preview.md"):
        assert (ROOT / name).is_file(), f"{name} is missing"


def test_every_issue_form_parses_and_has_the_keys_github_needs():
    yaml = __import__("pytest").importorskip("yaml", reason="PyYAML is not installed")
    forms = sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))
    assert len(forms) >= 6, "the recruitment step needs the forms to exist"
    for path in forms:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if path.name == "config.yml":
            assert data.get("contact_links"), path.name
            continue
        assert data.get("name"), path.name
        assert data.get("description"), path.name
        assert data.get("body"), path.name
        for field in data["body"]:
            assert field.get("type"), (path.name, field)
            if field["type"] != "markdown":
                assert field.get("id") and field.get("attributes"), (path.name, field)


def test_the_issue_form_links_point_at_real_files():
    config = (ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8")
    for referenced in re.findall(r"blob/main/([\w./-]+)", config):
        assert (ROOT / referenced).is_file(), f"config.yml links a missing file: {referenced}"
