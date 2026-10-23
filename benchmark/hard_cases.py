"""Hard-case cards: the schema, refusal by name, and the dev-card generator.

Stage 2's hard cases (docs/specs/validation-program.md, Hard cases) are
records of the decisions the detector most plausibly gets wrong: a changed
expected value (HC1), a test deleted citing a removed feature (HC4), and a
spec or docstring rewritten in the same diff (HC11, the row-F case that must
set the edited-evidence condition). One card captures one hard case:

    family, route, refs, edit, stated_reason, pinned_evidence_verdict,
    axes, twin, labels, expected_verdicts, version, split, id, source

The contracts, each one load-bearing:

* **A card missing a required field is refused by name.** `validate_card`
  names every offending field (`stated_reason: missing; ...`) and
  `card_from_fixture` raises `HardCaseError` with those names verbatim --
  never a default, never a guessed axis.
* **Expected verdicts are recorded under both policies.** `expected_verdicts`
  carries the strict and the conservative verdict of the pinned-evidence
  decision table (`greenwash.verify.pinned`), and `pinned_evidence_verdict`
  is that table's conservative reading of the case. The vocabulary is the
  table's own: CLEAN, TAMPERED, INCONCLUSIVE.
* **HC11 sets the edited-evidence condition.** An HC11 card whose edit does
  not carry `edited_evidence` true is refused naming `edit.edited_evidence`:
  a spec rewritten in the same diff can never launder the change it justifies
  (the pinned-evidence rule that evidence from a changed file never counts).
* **Every twin link records a similarity score.** The generator pairs each
  card's edit with a legitimate twin through `greenwash.twinning.match_twin`
  -- same AST-level edit class, diff-size proximity, never across
  repositories, never a synthetic record -- and records the score and class
  in the card's `twin` link.
* **The cards are maintainer-authored fixtures, labeled as such.** Every
  generated card's `source` starts `fixture: maintainer-authored`; nothing in
  this repository is a real collected case. Each family ships twelve dev
  cards -- six matched evidence / no-evidence pairs sharing one edit -- from
  the maintainer fixtures under `tests/fixtures/hard_cases/`.

The runner's seam, all callable without a CLI:

    cards = dev_cards()                    # 12 each for HC1, HC4, HC11
    issues = validate_card(card)           # every problem, field named
    card = card_from_fixture(record)       # HardCaseError naming the field
    write_dev_cards()                      # the committed benchmark/cards/
    cards = load_cards(path)               # committed cards, each validated

Out of scope by the ticket: Gate A and the label workflow. This module makes
cards and validates them; nothing here decides a gate or labels anything.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash import corpus  # noqa: E402
from greenwash.twinning import match_twin  # noqa: E402
from greenwash.verify.pinned import (  # noqa: E402
    POLICIES, VERDICT_CLEAN, VERDICT_INCONCLUSIVE, VERDICT_TAMPERED)

#: The hard-case families, as the operator listed them. The first three are
#: the tier-2 families stage 2 builds first (twelve dev cards each).
CARD_FAMILIES = ("HC1", "HC2", "HC3", "HC4", "HC5", "HC6", "HC7", "HC8",
                 "HC9", "HC10", "HC11", "HC12")

#: What one card must carry. The ticket's schema fields plus id and source
#: (identity and the fixture provenance label) and version (the matched
#: evidence / no-evidence label).
CARD_REQUIRED = ("id", "source", "family", "route", "refs", "edit",
                 "stated_reason", "pinned_evidence_verdict", "axes", "twin",
                 "labels", "expected_verdicts", "version", "split")

#: The matched versions a card comes in: with pinned evidence, and without.
CARD_VERSIONS = ("evidence", "no-evidence")

VERDICTS = (VERDICT_CLEAN, VERDICT_TAMPERED, VERDICT_INCONCLUSIVE)

#: The twelve dev cards are generated from these maintainer-authored
#: fixtures and labeled `fixture: maintainer-authored ...` in every card.
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "hard_cases"
CARDS_DIR = ROOT / "benchmark" / "cards"

FIXTURE_SOURCE_PREFIX = "fixture: maintainer-authored"


class HardCaseError(ValueError):
    """A card or fixture cannot be read. Rejected by name, never defaulted:
    a hard-case card missing a field is evidence nobody collected."""


# -- validating one card, naming the offending field -------------------------

def _missing(field: str, issues: list) -> None:
    issues.append(f"{field}: missing; a hard-case card must carry {field}")


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Mapping, list, tuple)):
        return bool(value)
    return True


def _text_field(container: Mapping, field: str, name: str, issues: list) -> None:
    value = container.get(field) if isinstance(container, Mapping) else None
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{name}: missing; a hard-case card carries {name}")


def _refs_issues(refs) -> list:
    if not isinstance(refs, Mapping):
        return ["refs: must be a mapping of base_ref and head_ref"]
    issues: list = []
    _text_field(refs, "base_ref", "refs.base_ref", issues)
    _text_field(refs, "head_ref", "refs.head_ref", issues)
    return issues


def _edit_issues(edit) -> list:
    if not isinstance(edit, Mapping):
        return ["edit: must be a mapping of diff and edited_evidence"]
    issues: list = []
    _text_field(edit, "diff", "edit.diff", issues)
    if not isinstance(edit.get("edited_evidence"), bool):
        issues.append("edit.edited_evidence: missing; the edited-evidence "
                      "condition is true or false, never defaulted")
    return issues


def _axes_issues(axes) -> list:
    if not isinstance(axes, Mapping):
        return [f"axes: must be a mapping of the four axes "
                f"({', '.join(corpus.AXES)})"]
    issues: list = []
    for name in corpus.AXES:
        value = axes.get(name)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"axes: missing {name}; a hard-case card carries "
                          f"all four axes ({', '.join(corpus.AXES)})")
    return issues


def _twin_issues(twin) -> list:
    if not isinstance(twin, Mapping):
        return ["twin: must be a twin link of id and similarity"]
    issues: list = []
    _text_field(twin, "id", "twin.id", issues)
    similarity = twin.get("similarity")
    if isinstance(similarity, bool) or not isinstance(similarity, (int, float)) \
            or not 0 <= similarity <= 1:
        issues.append(f"twin: similarity {similarity!r} is not a similarity "
                      "score between 0 and 1; the twin link records the score")
    return issues


def _labels_issues(labels) -> list:
    if not isinstance(labels, Mapping):
        return ["labels: must be a mapping of labeler1, labeler2, "
                "adjudicated, disagreement"]
    issues: list = []
    for name in corpus.LABELER_FIELDS:
        value = labels.get(name)
        if value not in corpus.LABELS:
            issues.append(f"labels: {name} has unknown value {value!r}; must "
                          f"be one of {', '.join(corpus.LABELS)}")
    if not isinstance(labels.get("disagreement"), bool):
        issues.append("labels: disagreement must be true or false, never "
                      "defaulted")
    return issues


def _expected_verdicts_issues(expected) -> list:
    if not isinstance(expected, Mapping):
        return ["expected_verdicts: must be a mapping of the two policies "
                f"({', '.join(POLICIES)})"]
    issues: list = []
    for policy in POLICIES:
        if policy not in expected or not _present(expected.get(policy)):
            issues.append(f"expected_verdicts: missing {policy}; a card "
                          "records the expected verdict under both policies")
        elif expected.get(policy) not in VERDICTS:
            issues.append(f"expected_verdicts: {policy} has unknown value "
                          f"{expected.get(policy)!r}; must be one of "
                          f"{', '.join(VERDICTS)}")
    for name in expected:
        if name not in POLICIES:
            issues.append(f"expected_verdicts: unknown policy {name!r}; must "
                          f"be one of {', '.join(POLICIES)}")
    return issues


def validate_card(card) -> list:
    """Every way one hard-case card is wrong, each naming the offending field.

    The family rule is fail-closed and family-specific: an HC11 card sets the
    edited-evidence condition, because a spec or docstring rewritten in the
    same diff is the row-F case -- edited evidence never counts as evidence.
    """
    if not isinstance(card, Mapping):
        return ["card: must be a mapping of the hard-case card fields"]
    issues: list = []
    for field in CARD_REQUIRED:
        if not _present(card.get(field)):
            _missing(field, issues)
    if _present(card.get("family")) and card.get("family") not in CARD_FAMILIES:
        issues.append(f"family: unknown value {card.get('family')!r}; must be "
                      f"one of {', '.join(CARD_FAMILIES)}")
    if _present(card.get("route")) and card.get("route") not in corpus.ROUTES:
        issues.append(f"route: unknown value {card.get('route')!r}; must be "
                      f"one of {', '.join(corpus.ROUTES)}")
    if _present(card.get("split")) and card.get("split") not in corpus.SPLITS:
        issues.append(f"split: unknown value {card.get('split')!r}; must be "
                      f"one of {', '.join(corpus.SPLITS)}")
    if _present(card.get("version")) \
            and card.get("version") not in CARD_VERSIONS:
        issues.append(f"version: unknown value {card.get('version')!r}; must "
                      f"be one of {', '.join(CARD_VERSIONS)}")
    if _present(card.get("pinned_evidence_verdict")) \
            and card.get("pinned_evidence_verdict") not in VERDICTS:
        issues.append("pinned_evidence_verdict: unknown value "
                      f"{card.get('pinned_evidence_verdict')!r}; must be one "
                      f"of {', '.join(VERDICTS)}")
    issues.extend(_refs_issues(card.get("refs")))
    issues.extend(_edit_issues(card.get("edit")))
    issues.extend(_axes_issues(card.get("axes")))
    issues.extend(_twin_issues(card.get("twin")))
    issues.extend(_labels_issues(card.get("labels")))
    issues.extend(_expected_verdicts_issues(card.get("expected_verdicts")))
    edit = card.get("edit")
    if card.get("family") == "HC11" and isinstance(edit, Mapping) \
            and edit.get("edited_evidence") is not True:
        issues.append("edit.edited_evidence: an HC11 card must set the "
                      "edited-evidence condition; the spec or docstring is "
                      "rewritten in the same diff, so edited evidence never "
                      "counts")
    return issues


def card_from_fixture(card) -> dict:
    """One validated card, or `HardCaseError` naming every missing field."""
    issues = validate_card(card)
    if issues:
        raise HardCaseError("; ".join(issues))
    return dict(card)


# -- generating the dev cards from the maintainer fixtures -------------------

def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fixture_issues(payload) -> list:
    issues: list = []
    for field in ("family", "route", "repository", "source", "axes",
                  "edited_evidence", "versions", "pairs", "twins"):
        if not _present(payload.get(field)):
            issues.append(f"{field}: missing; a maintainer hard-case fixture "
                          f"must carry {field}")
    return issues


def _twin_standins(payload) -> tuple:
    """The fixture's twin pool as matchable records plus their diffs."""
    repository = payload["repository"]
    standins: list = []
    diffs: dict = {}
    for twin in payload["twins"]:
        record = {"id": twin.get("id"),
                  "label": twin.get("label", corpus.CLEAN),
                  "repository": twin.get("repository", repository),
                  "origin": twin.get("origin", corpus.NATURAL),
                  "source": twin.get("source", "fixture: maintainer-authored "
                                               "legitimate twin")}
        standins.append(record)
        diffs[str(record["id"])] = twin.get("edit", "")
    return tuple(standins), diffs


def _expand_family(payload: Mapping) -> list:
    """One family's twelve dev cards: six matched evidence/no-evidence pairs."""
    issues = _fixture_issues(payload)
    if issues:
        raise HardCaseError(f"{payload.get('family') or 'fixture'}: "
                            + "; ".join(issues))
    family = payload["family"]
    repository = payload["repository"]
    source = payload["source"]
    if not str(source).startswith(FIXTURE_SOURCE_PREFIX):
        raise HardCaseError(f"source: {source!r} does not label the cards as "
                            f"maintainer-authored fixtures "
                            f"({FIXTURE_SOURCE_PREFIX} ...)")
    standins, diffs = _twin_standins(payload)
    versions = payload["versions"]
    cards: list = []
    for pair_spec in payload["pairs"]:
        for version in CARD_VERSIONS:
            key = f"{pair_spec.get('pair')}{'e' if version == 'evidence' else 'n'}"
            card_id = f"{family.lower()}-dev-{key}"
            version_block = versions.get(version)
            if not isinstance(version_block, Mapping):
                raise HardCaseError(f"versions: missing {version}; a fixture "
                                    "records both matched versions")
            diffs[card_id] = pair_spec.get("edit", "")
            pair = match_twin({"id": card_id, "repository": repository,
                               "origin": corpus.NATURAL, "source": source},
                              standins, diffs)
            axes = dict(payload["axes"])
            axes.update(version_block.get("axes") or {})
            card = {
                "id": card_id,
                "source": source,
                "family": family,
                "route": payload["route"],
                "refs": {"base_ref": _digest(f"{card_id}-base")[:12],
                         "head_ref": _digest(f"{card_id}-head")[:12]},
                "edit": {"diff": pair_spec.get("edit", ""),
                         "edited_evidence": payload["edited_evidence"]},
                "stated_reason": pair_spec.get("stated_reason", ""),
                "pinned_evidence_verdict":
                    version_block.get("pinned_evidence_verdict"),
                "axes": axes,
                "twin": {"id": pair.twin_id, "similarity": pair.similarity,
                         "edit_class": list(pair.edit_classes)},
                "labels": dict(version_block.get("labels") or {}),
                "expected_verdicts":
                    dict(version_block.get("expected_verdicts") or {}),
                "version": version,
                "split": "dev",
            }
            cards.append(card_from_fixture(card))
    return cards


def dev_cards(fixtures_dir=None, family: str | None = None) -> list:
    """The twelve dev cards per family, generated and validated.

    Every card is built from a maintainer-authored fixture and carries
    `fixture: maintainer-authored ...` as its source; the twin link is the
    scored pairing `greenwash.twinning.match_twin` chose. Generation is
    deterministic: the same fixtures produce the same cards, byte for byte.
    """
    directory = Path(fixtures_dir) if fixtures_dir is not None else FIXTURES_DIR
    cards: list = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise HardCaseError(f"{path.name}: fixture could not be read: "
                                f"{exc}") from exc
        if family is not None and payload.get("family") != family:
            continue
        cards.extend(_expand_family(payload))
    cards.sort(key=lambda card: (card["family"], card["id"]))
    return cards


def write_dev_cards(root=None) -> tuple:
    """Write the generated dev cards as one JSON file each; return the paths."""
    directory = Path(root) if root is not None else CARDS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    written: list = []
    for card in dev_cards():
        path = directory / f"{card['id']}.json"
        path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return tuple(written)


def load_cards(root=None) -> list:
    """Every committed card under `root`, each validated by name."""
    directory = Path(root) if root is not None else CARDS_DIR
    cards: list = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise HardCaseError(f"{path.name}: card could not be read: "
                                f"{exc}") from exc
        try:
            cards.append(card_from_fixture(payload))
        except HardCaseError as exc:
            raise HardCaseError(f"{path.name}: {exc}") from exc
    return cards


def main() -> None:
    written = write_dev_cards()
    families = sorted({card["family"] for card in dev_cards()})
    print(f"{len(written)} dev cards written to {CARDS_DIR} "
          f"({', '.join(families)})")


if __name__ == "__main__":
    main()
