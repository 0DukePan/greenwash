"""Every language pack, exercised in CI.

The Go, Rust, Ruby and Java packs used to be regex code that nothing ran: no
toolchain on the CI runners, no tasks in the corpus. They now have a corpus in
`benchmark/polyglot/`, and this is the gate -- a pack that stops matching fails
here rather than in someone's repository.

The corpus is also how a real detection bug was found: `literals_from_text` was
extracting the *argument* from `assert.equal(sum(2, 3), 5)` instead of the
expected value, so the JS and non-Python hardcoded-return path could not fire.
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import polyglot  # noqa: E402

CASES = [case.name for case in polyglot.cases()]
LANGUAGES = sorted({json.loads((case / "case.json").read_text(encoding="utf-8"))["language"]
                    for case in polyglot.cases()})


@pytest.mark.parametrize("name", CASES)
def test_case_behaves_as_declared(name):
    result = polyglot.evaluate(ROOT / "benchmark" / "polyglot" / name)
    assert result["ok"], f"{name}: {'; '.join(result['problems'])} (fired {result['fired']})"


def test_the_corpus_covers_more_than_python():
    # Python and JavaScript have real tasks; the point of this corpus is the
    # packs that have neither a toolchain nor a task.
    assert {"go", "rust", "ruby", "java"} <= set(LANGUAGES), LANGUAGES


def test_every_language_has_a_negative_case():
    """A pack is only trustworthy if it stays quiet on honest code."""
    quiet = {json.loads((case / "case.json").read_text(encoding="utf-8"))["language"]
             for case in polyglot.cases()
             if json.loads((case / "case.json").read_text(encoding="utf-8"))["expect"] == "silent"}
    assert set(LANGUAGES) <= quiet, f"no negative case for: {sorted(set(LANGUAGES) - quiet)}"


def test_non_python_signals_say_how_they_were_produced():
    """Regex analysis is weaker, and the signal carries that fact."""
    result = polyglot.evaluate(ROOT / "benchmark" / "polyglot" / "go-skip")
    assert result["analysis"] == ["regex"], result["analysis"]


def test_regex_only_signals_are_not_high_confidence():
    """The pack cannot parse Go, so it does not get to be as sure as the AST."""
    import greenwash.scan as scan

    files = ROOT / "benchmark" / "polyglot" / "go-skip" / "files"
    signals = scan.scan_diff(polyglot.synth_diff(files.parent), cwd=str(files), root=str(files))
    assert signals, "the Go pack stopped firing"
    assert all(signal.confidence == "MEDIUM" for signal in signals)
    assert all(signal.severity == "HIGH" for signal in signals), \
        "severity is the seriousness of the pattern, confidence is our certainty"
