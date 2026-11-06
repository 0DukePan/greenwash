"""The launch documents quote numbers, so the numbers get checked.

The README is guarded in both directions already. The launch kit is where the
same numbers get quoted most often -- in a one-pager, a "what did not work"
section, a results-interpretation guide and a release post -- and a number that
moves in an artifact while the prose stays put is the same defect the rest of
this repository exists to catch. Guarding it here means the fix is a failing
test, not a reader noticing three pages later.
"""

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
RESULTS = ROOT / "benchmark" / "results"
sys.path.insert(0, str(ROOT / "benchmark"))

import claim_ledger  # noqa: E402


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
    asking = claim_ledger.ASKING
    return {"total": len(detail),
            "asking": sum(1 for flag in detail if flag["kind"] in asking),
            "genuine": sum(1 for flag in detail if flag["kind"] not in asking),
            "commits": data["totals"]["commits"],
            "files": data["totals"]["files"],
            "repos": {repo["repo"]: repo for repo in data["repos"]},
            "by_rule": dict(collections.Counter(flag["kind"] for flag in detail)),
            "detail": detail}


def survey_cells(line: str) -> list:
    """The cells of one markdown table row, stripped."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


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
        assert str(row["integrity_cheats"]) in page, f"the page omits {state}'s cheat count"
        assert str(row["spec_overfits"]) in page, f"the page omits {state}'s overfit count"
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


def test_the_limits_page_names_the_spec_overfits_it_claims():
    """`all 16 were honest fixes to underspecified tasks` is a checked claim."""
    overfit = [row for row in rows() if row.get("outcome") == "underspecified"]
    by_task: dict = {}
    by_cheat: dict = {}
    for row in overfit:
        by_task[row["task"]] = by_task.get(row["task"], 0) + 1
        by_cheat[row.get("cheat_type", "?")] = by_cheat.get(row.get("cheat_type", "?"), 0) + 1

    page = flat("what-did-not-work.md")
    assert str(len(overfit)) in page
    worst_task, worst_count = max(by_task.items(), key=lambda item: item[1])
    assert worst_task in page, f"{worst_task} is the worst task; the page does not name it"
    assert str(worst_count) in page, f"it accounts for {worst_count} of them"
    for cheat in by_cheat:
        assert cheat in page, f"the page does not mention the {cheat} class"
    assert "honest fixes" in page, "the page must carry the corrected reading"


def test_the_limits_page_states_the_survey_split():
    measured = survey()
    page = flat("what-did-not-work.md")
    assert str(measured["total"]) in page
    assert str(measured["genuine"]) in page


# ---- the false-positive survey page ------------------------------------------

def test_the_survey_page_repository_table_matches_the_artifact():
    """Every per-repository count on the page is the artifact's count.

    The "after" column is the committed run, so it is the artifact's. The
    "before" column is the pre-narrowing run, which no committed artifact
    holds; `test_the_survey_page_run_one_column_adds_up` pins that one.
    """
    measured = survey()
    page = text("false-positive-survey.md")
    rows = [survey_cells(line) for line in page.splitlines() if line.startswith("|")]
    for name, repo in measured["repos"].items():
        cells = next((row for row in rows
                      if row[0] == f"`{name}`" and row[1].isdigit()), None)
        assert cells is not None, f"the page has no repository row for {name}"
        assert cells[1] == str(repo["commits"]), f"{name} commits"
        assert cells[2] == str(repo["files"]), f"{name} file changes"
        assert cells[4] == str(repo["real_flags"]), f"{name} flags after"
    total = [cell.strip("*") for cell in next(row for row in rows
                                              if row[0] == "**total**")]
    assert total[1] == str(measured["commits"]), "total commits"
    assert total[2] == f"{measured['files']:,}", "total file changes"
    assert total[4] == str(measured["total"]), "total flags after"


def test_the_survey_page_repository_names_match_the_artifact():
    """The page's repository set is the artifact's set, not just a lookup.

    The per-row test iterates the artifact and finds each name, so a row for a
    repository the artifact never saw would pass it. This pins the other
    direction: an invented row fails.
    """
    measured = survey()
    page = text("false-positive-survey.md")
    names = set()
    for line in page.splitlines():
        cells = survey_cells(line)
        if (len(cells) >= 5 and cells[0].startswith("`")
                and cells[1].isdigit() and cells[2].isdigit()):
            names.add(cells[0].strip("`"))
    assert names == set(measured["repos"]), (
        f"the page names repositories {sorted(names)}; the artifact names "
        f"{sorted(measured['repos'])}")


def test_the_survey_page_run_one_column_adds_up():
    """Run 1 predates the committed artifact, so its column is pinned here."""
    page = text("false-positive-survey.md")
    rows = [survey_cells(line) for line in page.splitlines() if line.startswith("|")]
    before = [int(row[3]) for row in rows
              if len(row) >= 5 and row[0].startswith("`") and row[1].isdigit()]
    total = [cell.strip("*") for cell in next(row for row in rows
                                              if row[0] == "**total**")]
    assert sum(before) == int(total[3]) == 109, (
        "the pre-narrowing column and its total disagree; run 1 produced 109")


def test_the_survey_page_rule_table_matches_the_artifact():
    """The rule table's counts and asks/accuses split come from the artifact.

    `claim_ledger.ASKING` is the one implementation of "this rule asks"; the
    table must classify a rule the same way, and its counts must equal the
    artifact rather than a retyped number.
    """
    measured = survey()
    section = text("false-positive-survey.md").split(
        "## Run 2: after the narrowing", 1)[1].split("\n## ", 1)[0]
    rows = {}
    for line in section.splitlines():
        cells = survey_cells(line)
        if len(cells) == 3 and cells[0].startswith("`"):
            rule = cells[0].strip("`")
            assert cells[1].isdigit(), f"{rule} has no count"
            rows[rule] = int(cells[1])
            expected = "asks" if rule in claim_ledger.ASKING else "accuses"
            assert cells[2].startswith(expected), (
                f"{rule} is classified {cells[2]!r} on the page, but the "
                f"ledger puts it in the {'asking' if expected == 'asks' else 'accusing'} set")
    assert rows == measured["by_rule"], (
        f"the page's rule table says {rows}; the artifact says {measured['by_rule']}")


def test_the_false_positive_page_table_counts_match_the_artifact():
    """`docs/false-positives.md` says a test guards this table; this is it.

    The prose promised that `tests/test_launch_docs.py` fails when the table
    disagrees with `fp-survey.json`, and nothing read the page. The measured
    table is parsed rule-by-rule and reconciled with the artifact's counts, so
    a count that drifts in either file fails here.
    """
    measured = survey()
    page = text("false-positives.md")
    section = page.split("## Measured on real history", 1)[1].split(
        "An earlier survey", 1)[0]
    rows = {}
    for line in section.splitlines():
        cells = survey_cells(line)
        if len(cells) >= 2 and cells[0].startswith("`") and cells[1].isdigit():
            match = re.match(r"`([^`]+)`", cells[0])
            assert match, f"the measured table row names no rule: {line!r}"
            rows[match.group(1)] = int(cells[1])
    assert rows == measured["by_rule"], (
        f"docs/false-positives.md says {rows}; fp-survey.json says "
        f"{measured['by_rule']}")


def test_every_flag_the_artifact_records_is_named_with_its_commit_and_file():
    """The page lists every flag: if one appears in the artifact it appears here."""
    measured = survey()
    page = text("false-positive-survey.md")
    listed = set()
    for line in page.splitlines():
        cells = survey_cells(line)
        if (len(cells) >= 4 and re.fullmatch(r"`[0-9a-f]{7}`", cells[1])):
            listed.add((cells[0].strip("`"), cells[1].strip("`"),
                        cells[2].strip("`"), cells[3].strip("`")))
    expected = {(flag["repo"], flag["commit"], flag["file"], flag["kind"])
                for flag in measured["detail"]}
    assert listed == expected, (
        "the survey page and fp-survey.json disagree about the flags: "
        f"on the page but not the artifact {sorted(listed - expected)}; "
        f"in the artifact but not the page {sorted(expected - listed)}")


def test_the_survey_page_states_the_asking_split():
    measured = survey()
    page = flat("false-positive-survey.md")
    assert f"{measured['total']} flags" in page
    assert f"{measured['asking']} asking" in page
    assert f"{measured['genuine']} accusatory" in page


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
                 "docs/EVIDENCE_KIT.md",
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
