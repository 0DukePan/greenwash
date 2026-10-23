"""The hard-case card seam: schema, refusal by name, and the dev cards.

One seam, `benchmark/hard_cases.py`, driven at its public functions with the
maintainer-authored fixtures under `tests/fixtures/hard_cases/` and the
generated dev cards under `benchmark/cards/`. The acceptance criteria asserted
here are the ticket's, literally: a card missing a required field is refused
by name, twelve dev cards exist for each of HC1, HC4 and HC11 and validate,
every HC11 card sets the edited-evidence condition, and each card's twin link
records the similarity score of the paired legitimate edit.

Every card below is generated from maintainer-authored fixtures and labeled
as such in its `source`; nothing here is a real collected case. Everything is
offline: plain dicts and JSON files, no network.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark"))

import hard_cases  # noqa: E402, F401  (imported for its module docstring seam)
from greenwash.twinning import (  # noqa: E402
    diff_size, edit_classes, size_similarity)
from hard_cases import (  # noqa: E402
    CARD_REQUIRED, HardCaseError, card_from_fixture, dev_cards, load_cards,
    validate_card, write_dev_cards)

FAMILIES = ("HC1", "HC4", "HC11")
FIXTURES = HERE / "fixtures" / "hard_cases"
CARDS_DIR = ROOT / "benchmark" / "cards"
VERDICTS = ("CLEAN", "INCONCLUSIVE", "TAMPERED")


def _twin_edits(family: str) -> dict:
    """{twin id: twin edit diff} from the family's maintainer fixture."""
    import json
    payload = json.loads((FIXTURES / f"{family.lower()}.json")
                         .read_text(encoding="utf-8"))
    return {twin["id"]: twin["edit"] for twin in payload["twins"]}


def _by_family(cards: list, family: str) -> list:
    return [card for card in cards if card["family"] == family]


# -- a card missing a required field is refused by name ----------------------

@pytest.mark.parametrize("field", CARD_REQUIRED)
def test_a_card_missing_a_required_field_is_rejected_by_name(field):
    card = copy.deepcopy(dev_cards()[0])
    card.pop(field)
    issues = validate_card(card)
    assert any(issue.startswith(f"{field}:") for issue in issues), issues
    with pytest.raises(HardCaseError) as excinfo:
        card_from_fixture(card)
    assert f"{field}:" in str(excinfo.value)


def test_an_unknown_enumerated_value_is_refused_by_name():
    for field, value in (("family", "HC99"), ("route", "R9"),
                         ("split", "holdout"), ("version", "maybe"),
                         ("pinned_evidence_verdict", "YES")):
        card = copy.deepcopy(dev_cards()[0])
        card[field] = value
        issues = validate_card(card)
        assert any(issue.startswith(f"{field}:") for issue in issues), issues


def test_expected_verdicts_are_refused_when_a_policy_is_missing():
    card = copy.deepcopy(dev_cards()[0])
    card["expected_verdicts"] = {"strict": "CLEAN"}
    issues = validate_card(card)
    assert any(issue.startswith("expected_verdicts:") for issue in issues), \
        issues


# -- twelve dev cards each for HC1, HC4 and HC11, all validating -------------

def test_twelve_dev_cards_exist_for_each_family_and_validate():
    cards = load_cards(CARDS_DIR)
    assert len(cards) == 36
    for family in FAMILIES:
        assert len(_by_family(cards, family)) == 12
    for card in cards:
        assert validate_card(card) == []
        assert card["split"] == "dev"


def test_generated_cards_are_labeled_maintainer_fixtures():
    for card in dev_cards():
        assert card["source"].startswith("fixture: maintainer-authored")


def test_written_dev_cards_reproduce_byte_for_byte(tmp_path):
    write_dev_cards(tmp_path)
    written = sorted(path.name for path in tmp_path.glob("*.json"))
    committed = sorted(path.name for path in CARDS_DIR.glob("*.json"))
    assert written == committed
    for name in written:
        assert ((tmp_path / name).read_bytes()
                == (CARDS_DIR / name).read_bytes())


# -- HC11 sets the edited-evidence condition ---------------------------------

def test_every_hc11_card_sets_the_edited_evidence_condition():
    cards = _by_family(load_cards(CARDS_DIR), "HC11")
    assert len(cards) == 12
    for card in cards:
        assert card["edit"]["edited_evidence"] is True


def test_an_hc11_card_without_the_edited_evidence_condition_is_refused():
    card = copy.deepcopy(dev_cards(family="HC11")[0])
    card["edit"]["edited_evidence"] = False
    issues = validate_card(card)
    assert any("edited_evidence" in issue for issue in issues), issues


# -- matched evidence and no-evidence versions --------------------------------

def test_each_family_ships_matched_evidence_and_no_evidence_versions():
    for family in FAMILIES:
        cards = _by_family(load_cards(CARDS_DIR), family)
        pairs: dict = {}
        for card in cards:
            pairs.setdefault(card["edit"]["diff"], []).append(card["version"])
        assert len(pairs) == 6, family
        for versions in pairs.values():
            assert sorted(versions) == ["evidence", "no-evidence"]


# -- the twin link records the similarity score per pair ---------------------

def test_card_twin_links_record_a_similarity_score_per_pair():
    for card in load_cards(CARDS_DIR):
        twin = card["twin"]
        twin_edit = _twin_edits(card["family"])[twin["id"]]
        score = round(size_similarity(diff_size(card["edit"]["diff"]),
                                      diff_size(twin_edit)), 4)
        assert twin["similarity"] == score
        assert 0 <= twin["similarity"] <= 1
        assert tuple(twin["edit_class"]) == edit_classes(card["edit"]["diff"])


def test_expected_verdicts_cover_both_policies():
    for card in load_cards(CARDS_DIR):
        assert set(card["expected_verdicts"]) == {"strict", "conservative"}
        assert set(card["expected_verdicts"].values()) <= set(VERDICTS)
        assert card["pinned_evidence_verdict"] in VERDICTS
