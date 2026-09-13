"""Ambiguous changes must be asked about, never convicted.

The corpus in `benchmark/inconclusive/` holds six changes a reasonable reviewer
would accept but a naive scanner would flag: a lookup table, a skipped flaky
test, a network mock, a new fixture, a CLI that exits 0, and documentation that
quotes an exploit.

Each case declares which rules *may* fire and which must stay silent. The
property under test is the one the whole design turns on: a pattern match can
make a report suspicious, but only evidence can make it `NOT_VERIFIED`.
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash.confidence import verdict_for  # noqa: E402
from greenwash.domain import Signal, Verdict, VerificationResult  # noqa: E402
from greenwash.scan import scan_diff  # noqa: E402

CORPUS = ROOT / "benchmark" / "inconclusive"
CASES = sorted(path.name for path in CORPUS.iterdir() if (path / "case.json").is_file())


def synth_diff(case_dir: Path) -> str:
    """Every file in the case is new, so every line is an addition."""
    chunks = []
    for path in sorted((case_dir / "files").rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(case_dir / "files").as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        local = case_dir / "files"
        body = "".join(f"+{line}\n" for line in lines)
        chunks.append(
            f"diff --git a/{rel} b/{rel}\nnew file mode 100644\n--- /dev/null\n+++ b/{rel}\n"
            f"@@ -0,0 +1,{len(lines)} @@\n{body}")
        assert local.is_dir()
    return "".join(chunks)


def load(name: str):
    case_dir = CORPUS / name
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    files = case_dir / "files"
    # `root` is explicit: these paths are relative to the case directory, not to
    # the greenwash checkout that happens to contain it.
    signals = scan_diff(synth_diff(case_dir), cwd=str(files), root=str(files))
    return case, signals


def test_the_corpus_is_actually_there():
    assert CASES, "no inconclusive cases found"


@pytest.mark.parametrize("name", CASES)
def test_an_ambiguous_change_is_never_convicted(name):
    case, signals = load(name)
    verdict = verdict_for(VerificationResult(), signals)
    assert verdict is not Verdict.NOT_VERIFIED, (
        f"{name} was convicted on patterns alone: {[s.rule_id for s in signals]}")
    assert verdict is not Verdict.VERIFICATION_FAILED


@pytest.mark.parametrize("name", CASES)
def test_only_the_declared_rules_fire(name):
    case, signals = load(name)
    fired = {signal.rule_id for signal in signals}
    assert fired <= set(case["may_fire"]), (
        f"{name}: unexpected rules fired: {sorted(fired - set(case['may_fire']))}")
    assert not (fired & set(case["must_not_fire"])), (
        f"{name}: rules that must stay silent fired: "
        f"{sorted(fired & set(case['must_not_fire']))}")


@pytest.mark.parametrize("name", CASES)
def test_every_case_explains_itself(name):
    case, _ = load(name)
    assert len(case["why"]) > 40, f"{name} does not explain why it is ambiguous"
    assert case["may_fire"] or case["must_not_fire"]


def test_the_corpus_covers_both_outcomes():
    """Some cases must fire (and only ask); at least one must fire nothing at all."""
    fired = {name: {s.rule_id for s in load(name)[1]} for name in CASES}
    assert any(signals for signals in fired.values()), "no case exercises a rule"
    assert any(not signals for signals in fired.values()), \
        "no case exercises the quiet path"


def test_ambiguity_survives_the_report():
    """The report says 'suspicious' out loud, and says why, rather than hedging quietly."""
    case, signals = load("legit-constant")
    assert any(signal.rule_id == "hardcoded-return" for signal in signals)
    assert any(signal.remediation for signal in signals), \
        "a signal that asks a question must also say what the answer looks like"
    assert isinstance(signals[0], Signal)
