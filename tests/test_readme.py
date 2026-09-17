"""The README states numbers, so the numbers get checked.

Two published counts drifted before this file existed: the suite grew 52 -> 56
while the README kept saying 52 in its headline, and the demo's output changed
while the transcript stayed put. A published number or receipt that drifts is
the same defect the rest of this repo exists to catch, so it is a test now.
"""

import collections
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from greenwash.report import terminal  # noqa: E402

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


def test_readme_corpus_size_matches_the_detector_run():
    """The sentence around the detector table states what ran and what did not.

    `detection.py` records a task whose toolchain is missing as skipped rather
    than scoring it, so the README has to say how much of the corpus its table
    covers -- otherwise a shrunken run reads as a full one.
    """
    summary = json.loads(
        (ROOT / "benchmark" / "results" / "detection.json").read_text(encoding="utf-8")
    )["summary"]
    text = flat_readme()
    assert f"{summary['corpus']} tasks across six languages" in text, (
        f"the corpus holds {summary['corpus']} tasks; the README does not say so")
    assert f"{summary['tasks']} of the {summary['corpus']} scored" in text, (
        f"{summary['tasks']} of {summary['corpus']} scored; the README does not say so")


def test_readme_runtime_matches_the_detection_run():
    """The runtime row quotes a measurement, so the artifact is the source.

    It was the one number in the README with no receipt behind it;
    `detection.py` records the elapsed seconds in its summary now, and this
    makes the README state the measured value.
    """
    summary = json.loads(
        (ROOT / "benchmark" / "results" / "detection.json").read_text(encoding="utf-8")
    )["summary"]
    runtime = summary.get("runtime_seconds")
    if runtime is None:
        return
    assert (f"{runtime}s for {summary['tasks']} scored tasks x 3 variants"
            in flat_readme()), (
        f"detection.json records {runtime}s for {summary['tasks']} scored tasks; "
        "the README does not state it")


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

    It is the demo's stdout, verbatim -- including the wrapping, which is why the
    demo pins COLUMNS. If the report changes, this fails before the README can go
    stale.

    One documented difference is normalised away: the renderer degrades its
    decoration to ASCII when the stream cannot encode it (a default Windows
    console is cp1252), so a transcript captured on Windows has `+`/`x` where a
    UTF-8 terminal prints `✓`/`✗`. That fallback is behaviour, not content, and
    the test should not care which platform it runs on.

    The child's encoding is pinned so the *capture* is deterministic too:
    decoding a UTF-8 child with the locale codec is how this compares mojibake.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, str(ROOT / "demo" / "run_demo.py"), "--terse"],
                          capture_output=True, cwd=ROOT, env=env,
                          encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr

    def normalise(text: str) -> str:
        text = text.replace("\r\n", "\n").rstrip("\n")
        for fancy, plain in terminal.ASCII_FALLBACKS:
            text = text.replace(fancy, plain)
        return text

    blocks = re.findall(r"```[a-z]*\r?\n(.*?)\r?\n```", readme(), re.S)
    transcripts = [block for block in blocks if "GREENWASH TRUST REPORT" in block]
    assert transcripts, "the README has no transcript of the demo's output"
    assert normalise(transcripts[0]) == normalise(proc.stdout), (
        "the README transcript is not what `demo/run_demo.py --terse` prints")


def test_readme_language_coverage_matches_the_corpus():
    """The README quotes the polyglot corpus, so the corpus is the source."""
    sys.path.insert(0, str(ROOT / "benchmark"))
    import polyglot

    summary = polyglot.run()
    text = flat_readme()
    assert f"{summary['total']} cases" in text, (
        f"the corpus has {summary['total']} cases; the README does not say so")
    assert f"{summary['passed']}/{summary['total']} behaving as declared" in text, (
        f"the corpus reports {summary['passed']}/{summary['total']}; the README does not")
    for language in summary["by_language"]:
        assert f"`{language}`" in text or language in text.lower(), \
            f"the README does not mention {language}"


def test_readme_delta_matches_the_measured_agent_delta():
    """The headline claim, guarded in both directions.

    If a live run exists, the README must state the delta it produced. If it does
    not, the README must say so -- rather than keeping a favourable sentence that
    was true once.
    """
    path = ROOT / "benchmark" / "results" / "agent-delta.json"
    text = flat_readme()
    delta = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    if not delta.get("live"):
        assert "not measured yet" in text.lower(), (
            "no live agent run exists, so the README must say the delta is unmeasured")
        assert "Delta (off" not in text, (
            "the README claims a measured delta but results/agent-delta.json is not live")
        return

    assert f"{delta['delta_points']:+.1f} points" in text, (
        f"a live run measured {delta['delta_points']:+.1f} points; "
        "the README does not state it")
    for state, row in delta["states"].items():
        assert str(row["runs"]) in text, f"the README omits the {state} run count"


def test_results_md_delta_matches_the_measured_agent_delta():
    """RESULTS.md prints the same delta as every other channel, to one decimal.

    It used to round to whole points -- the file said "-1 points" while the
    README, the generated BENCHMARK block and `agent-delta.json` all said
    "-1.4". Nothing guarded RESULTS.md, so the drift sat there: the one blind
    spot in an otherwise two-way-guarded README.
    """
    delta = json.loads(
        (ROOT / "benchmark" / "results" / "agent-delta.json").read_text(encoding="utf-8"))
    if "delta_points" not in delta:
        return
    results = (ROOT / "benchmark" / "RESULTS.md").read_text(encoding="utf-8")
    assert f"Delta (off -> full): {delta['delta_points']:+.1f} points" in results, (
        f"agent-delta.json says {delta['delta_points']:+.1f} points; "
        "benchmark/RESULTS.md does not")
