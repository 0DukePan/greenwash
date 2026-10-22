"""The technique taxonomy: one versioned table, and the matrix it generates.

The table is the source of truth for what this tool claims to catch. The
coverage matrix `greenwash rules` prints is generated from it -- never
hand-maintained prose -- and a record naming a technique the table does not
know is rejected with the offending field named, so a corpus cannot cite a
technique the detector never heard of.

The honesty rule is executable here: a technique either names a mechanism that
exists, or it says `not covered`. A row that claims coverage by nothing is the
kind of drift this repository exists to fail on.
"""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from greenwash import cli, taxonomy  # noqa: E402
from greenwash.scan import BY_ID as SCAN_RULES  # noqa: E402
from greenwash.verify import signals as verify_signals  # noqa: E402

README = HERE.parent / "README.md"

GAPS = {"spec-docstring-fixture-rewrite", "runner-config-tamper",
        "report-tamper", "gate-hook-tamper"}


def _run(monkeypatch, capsys, argv):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _matrix(out):
    """The coverage matrix section, split into one block per technique."""
    assert "Coverage matrix" in out, "greenwash rules prints no coverage matrix"
    section = out.split("Coverage matrix", 1)[1]
    return [block for block in section.split("\n\n") if block.strip()]


def _block_for(out, technique_id):
    matches = [" ".join(block.split()) for block in _matrix(out)
               if technique_id in block]
    assert len(matches) == 1, f"{technique_id} appears in {len(matches)} matrix blocks"
    return matches[0]


# -- the matrix is generated from the table -----------------------------------

def test_the_matrix_is_generated_from_the_table(monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, ["rules"])
    assert code == 0
    blocks = _matrix(out)
    assert len(blocks) == len(taxonomy.TECHNIQUES) + 1  # + the header block
    for technique in taxonomy.TECHNIQUES:
        block = _block_for(out, technique.id)
        assert f"[{technique.status}]" in block, block
        assert ("replay: needed" in block) is technique.replay, block
        if technique.mechanisms:
            for mechanism in technique.mechanisms:
                assert mechanism in block, block
        else:
            assert "nothing catches this yet" in block, block


def test_the_matrix_survives_a_terminal_width(monkeypatch, capsys):
    for columns in ("80", "48"):
        monkeypatch.setenv("COLUMNS", columns)
        _, out, _ = _run(monkeypatch, capsys, ["rules"])
        section = out.split("Coverage matrix", 1)[1].splitlines()
        too_wide = [line for line in section if len(line) > int(columns)]
        assert too_wide == [], f"at COLUMNS={columns}: {too_wide}"


def test_the_matrix_says_plainly_what_is_not_covered(monkeypatch, capsys):
    _, out, _ = _run(monkeypatch, capsys, ["rules"])
    for technique_id in GAPS:
        block = _block_for(out, technique_id)
        assert "[covered]" not in block, block
    assert "not covered" in _block_for(out, "spec-docstring-fixture-rewrite")
    assert "not covered" in _block_for(out, "report-tamper")


# -- the table itself ---------------------------------------------------------

def test_a_technique_names_a_mechanism_that_exists_or_says_not_covered():
    mechanisms = set(SCAN_RULES) | {
        getattr(verify_signals, name).id for name in verify_signals.__all__}
    seen = set()
    for technique in taxonomy.TECHNIQUES:
        assert technique.id not in seen, f"{technique.id} is listed twice"
        seen.add(technique.id)
        assert technique.name, f"{technique.id} has no name"
        assert technique.status in taxonomy.STATUSES
        assert isinstance(technique.replay, bool)
        if technique.status == "not covered":
            assert not technique.mechanisms, (
                f"{technique.id} claims a mechanism but reports not covered")
        else:
            assert technique.mechanisms, (
                f"{technique.id} claims {technique.status} by nothing")
            for mechanism in technique.mechanisms:
                assert mechanism in mechanisms, (
                    f"{technique.id} names unknown mechanism {mechanism}")


def test_the_taxonomy_carries_a_version():
    assert taxonomy.TAXONOMY_VERSION
    assert str(taxonomy.TAXONOMY_VERSION)[0].isdigit()


# -- the validation function, as callers will use it --------------------------

def test_an_unknown_technique_is_rejected_with_the_field_named():
    issues = taxonomy.validate_technique({"technique": "made-up-technique"})
    assert issues, "an unknown technique must be rejected"
    assert issues[0].startswith("technique:"), issues[0]
    assert "made-up-technique" in issues[0], issues[0]


def test_every_known_technique_validates_clean():
    for technique in taxonomy.TECHNIQUES:
        assert taxonomy.validate_technique({"technique": technique.id}) == []
        assert taxonomy.validate_technique(technique.id) == []


def test_a_record_with_no_technique_is_rejected():
    issues = taxonomy.validate_technique({})
    assert issues and issues[0].startswith("technique:"), issues


def test_the_offending_field_is_named_as_the_record_spells_it():
    issues = taxonomy.validate_technique({"tamper": "made-up-technique"},
                                         field="tamper")
    assert issues and issues[0].startswith("tamper:"), issues
    assert "made-up-technique" in issues[0], issues[0]


# -- the docs pin the version -------------------------------------------------

def test_the_docs_pin_the_taxonomy_version(monkeypatch, capsys):
    pin = f"technique taxonomy v{taxonomy.TAXONOMY_VERSION}"
    assert pin in README.read_text(encoding="utf-8"), (
        f"the README does not pin {pin}")
    _, out, _ = _run(monkeypatch, capsys, ["rules"])
    assert pin in out
