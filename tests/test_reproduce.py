"""The reproduction command: the published headline table, rebuilt from pins.

One command -- `python benchmark/reproduce.py` -- rebuilds the published
headline table (benchmark/results/headline.md) from pinned artifacts: the
corpus manifest, the frozen annotations, the detector configurations and the
seeds. No model runs in the rebuild. These tests drive the command itself:
run it, read the table it writes.

The three contracts the ticket states, asserted literally:

* The command rebuilds the table byte-identically on a second run,
  timestamps excluded -- and what it writes is the published table.
* Any pinned-artifact hash mismatch aborts with the artifact named.
* The README's methods section documents the command and its expected output.

A scratch root carries copies of the pinned inputs so a test may tamper one
artifact at a time; the hash pin for a tampered artifact is left stale on
purpose (that is the mismatch) unless a test is exercising something else and
re-pins it first.
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

PINS = Path("benchmark") / "reproduction" / "pins.json"
PUBLISHED = ROOT / "benchmark" / "results" / "headline.md"
ARTIFACTS = ("corpus manifest", "frozen annotations", "detector configurations",
             "seeds")


def run_reproduce(*args):
    return subprocess.run([sys.executable, "benchmark/reproduce.py", *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=300)


def pin_record(name: str) -> dict:
    pins = json.loads((ROOT / PINS).read_text(encoding="utf-8"))
    return pins["artifacts"][name]


def scratch(tmp_path) -> Path:
    """A root carrying the pinned inputs, so a test may tamper them."""
    shutil.copytree(ROOT / "tests" / "fixtures" / "evaluation",
                    tmp_path / "tests" / "fixtures" / "evaluation")
    shutil.copytree(ROOT / "benchmark" / "reproduction",
                    tmp_path / "benchmark" / "reproduction")
    return tmp_path


def repin(root: Path, name: str) -> None:
    """Re-record one artifact's hash, so only its content disagrees."""
    pins_path = root / PINS
    pins = json.loads(pins_path.read_text(encoding="utf-8"))
    entry = pins["artifacts"][name]
    entry["sha256"] = hashlib.sha256(
        (root / entry["path"]).read_bytes()).hexdigest()
    pins_path.write_text(json.dumps(pins, indent=2) + "\n", encoding="utf-8")


def test_the_command_rebuilds_the_published_headline_table_byte_identically(tmp_path):
    first, second = tmp_path / "first.md", tmp_path / "second.md"
    for out in (first, second):
        result = run_reproduce("--out", str(out))
        assert result.returncode == 0, result.stderr
    assert first.read_bytes() == second.read_bytes(), (
        "a second run is not byte-identical to the first")
    assert first.read_bytes() == PUBLISHED.read_bytes(), (
        "the command does not rebuild the published headline table")
    text = first.read_text(encoding="utf-8")
    # timestamps excluded: the table prints no date at all
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text)
    # the pinned inputs are named in the table it prints
    for name in ARTIFACTS:
        assert name in text, name
        assert pin_record(name)["sha256"] in text, name


@pytest.mark.parametrize("artifact", ARTIFACTS)
def test_a_pinned_artifact_hash_mismatch_aborts_naming_the_artifact(tmp_path,
                                                                   artifact):
    root = scratch(tmp_path)
    entry = pin_record(artifact)
    path = root / entry["path"]
    path.write_bytes(path.read_bytes() + b"\n# tampered\n")
    out = tmp_path / "never.md"
    result = run_reproduce("--root", str(root), "--out", str(out))
    assert result.returncode == 2, result
    assert artifact in result.stderr
    assert "hash mismatch" in result.stderr
    assert not out.exists(), "a refused rebuild writes no table"


def test_a_detector_configuration_that_needs_a_model_is_refused_by_name(tmp_path):
    root = scratch(tmp_path)
    config = root / "benchmark" / "reproduction" / "detectors.json"
    config.write_text(json.dumps({"detectors": [
        {"id": "B2", "baseline": "judge", "version": "judge-frozen-v1"}]}) + "\n",
        encoding="utf-8")
    repin(root, "detector configurations")
    out = tmp_path / "never.md"
    result = run_reproduce("--root", str(root), "--out", str(out))
    assert result.returncode == 2, result
    assert "detector configurations" in result.stderr
    assert "model" in result.stderr
    assert not out.exists(), "a refused rebuild writes no table"


def test_a_frozen_annotation_that_disagrees_with_the_corpus_names_the_artifact(tmp_path):
    root = scratch(tmp_path)
    path = root / "benchmark" / "reproduction" / "annotations.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["annotations"]["fx_assert_tamper"]["label"] = "clean"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    repin(root, "frozen annotations")
    out = tmp_path / "never.md"
    result = run_reproduce("--root", str(root), "--out", str(out))
    assert result.returncode == 2, result
    assert "frozen annotations" in result.stderr
    assert "fx_assert_tamper" in result.stderr
    assert not out.exists(), "a refused rebuild writes no table"


def test_the_readme_methods_section_documents_the_command_and_its_expected_output():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = re.search(r"^## Methods\r?\n(.*?)(?=^## )", readme, re.M | re.S)
    assert section, "the README has no methods section"
    body = section.group(1)
    assert "benchmark/reproduce.py" in body
    assert "[benchmark/results/headline.md](benchmark/results/headline.md)" in body
    assert PUBLISHED.is_file(), "the expected output is not published"
