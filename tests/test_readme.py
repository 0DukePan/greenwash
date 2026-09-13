"""The README states numbers, so the numbers get checked.

Two published counts drifted before this file existed: the suite grew 52 -> 56
while the README kept saying 52 in its headline, and the demo's output changed
while the transcript stayed put. A published number or receipt that drifts is
the same defect the rest of this repo exists to catch, so it is a test now.
"""

import collections
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ASK_FOR_EXPLANATION = {"mock-in-test", "swallowed-exception", "test-skipped",
                       "assertion-weakened", "conftest-changed"}


def collected() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
        capture_output=True, text=True, cwd=ROOT)
    return sum(1 for line in proc.stdout.splitlines() if "::" in line)


def readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def flat_readme() -> str:
    return " ".join(readme().split())


def test_readme_test_count_matches_the_suite():
    # a digit is required: `says "done, tests pass"` is prose, not a claim
    claimed = set(re.findall(r"(\d[\d,]*) tests", readme()))
    actual = collected()
    assert claimed == {str(actual)}, (
        f"README claims {sorted(claimed)} tests; the suite collects {actual}")


def test_readme_headline_matches_the_detection_results():
    summary = json.loads(
        (ROOT / "benchmark" / "results" / "detection.json").read_text(encoding="utf-8")
    )["summary"]
    headline = next(line for line in readme().splitlines()
                    if "planted cheats caught" in line)
    assert f"{summary['either_caught']}/{summary['tasks']} planted cheats caught" in headline
    assert (f"{summary['false_positives']} false positives on "
            f"{summary['solutions_clean']} real fixes") in headline


def test_readme_false_positive_split_matches_the_survey():
    survey = json.loads(
        (ROOT / "benchmark" / "results" / "fp-survey.json").read_text(encoding="utf-8"))
    rows = [flag for repo in survey["repos"] for flag in repo["detail"]]
    counts = collections.Counter(flag["kind"] for flag in rows)
    asked = sum(n for kind, n in counts.items() if kind in ASK_FOR_EXPLANATION)
    genuine = sum(n for kind, n in counts.items() if kind not in ASK_FOR_EXPLANATION)

    text = flat_readme()
    assert f"{len(rows)} flags" in text, f"README does not state the {len(rows)} flags"
    assert f"{asked} are the rules that always ask for an explanation" in text
    assert f"{genuine} are genuine false positives" in text


def test_readme_transcript_is_the_demo_output():
    """The block under "What the report looks like" is a receipt, so it is checked.

    It is the demo's stdout, verbatim -- including the wrapping, which is why
    the demo pins COLUMNS. If the report changes, this fails before the
    README can go stale.
    """
    proc = subprocess.run([sys.executable, str(ROOT / "demo" / "run_demo.py"), "--terse"],
                          capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    demo = proc.stdout.replace("\r\n", "\n").rstrip("\n")

    blocks = re.findall(r"```[a-z]*\r?\n(.*?)\r?\n```", readme(), re.S)
    transcripts = [block.replace("\r\n", "\n").rstrip("\n") for block in blocks
                   if "GREENWASH TRUST REPORT" in block]
    assert transcripts, "the README has no transcript of the demo's output"
    assert transcripts[0] == demo, (
        "the README transcript is not what `demo/run_demo.py --terse` prints")
