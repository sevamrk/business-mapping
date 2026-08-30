"""The spec and the code have to agree.

A vocabulary is only useful if the document somebody reads before writing a map
lists the same values the validator accepts. These tests fail when a level is
added in one place and not the other.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src import validate, vocab

SCHEMA_DOC = Path(__file__).resolve().parent.parent / "SCHEMA.md"
TEXT = SCHEMA_DOC.read_text(encoding="utf-8")
QUOTED = set(re.findall(r"`([^`\n]+)`", TEXT))

VOCABULARIES = {
    "ACTOR_KINDS": vocab.ACTOR_KINDS,
    "ARTIFACT_FORMS": vocab.ARTIFACT_FORMS,
    "ARTIFACT_BOUNDARIES": vocab.ARTIFACT_BOUNDARIES,
    "TRIGGERS": vocab.TRIGGERS,
    "CURRENT_STATES": tuple(vocab.CURRENT_STATES),
    "DECISION_TYPES": tuple(vocab.DECISION_TYPES),
    "INPUT_FORMS": tuple(vocab.INPUT_FORMS),
    "INTERFACES": tuple(vocab.INTERFACES),
    "CHANGE_RATES": tuple(vocab.CHANGE_RATES),
    "ERROR_COSTS": tuple(vocab.ERROR_COSTS),
    "REVERSIBILITY": tuple(vocab.REVERSIBILITY),
    "OVERSIGHT": tuple(vocab.OVERSIGHT),
    "PATTERNS": vocab.PATTERNS,
    "AUTOMATION_FACTS": vocab.AUTOMATION_FACTS,
}

FIELDS = (
    set(validate._TOP_LEVEL)
    | set(validate._ACTOR_FIELDS)
    | set(validate._ARTIFACT_FIELDS)
    | set(validate._FUNCTION_FIELDS)
    | {"notes"}
)


@pytest.mark.parametrize(
    "value", sorted({v for values in VOCABULARIES.values() for v in values})
)
def test_every_vocabulary_value_is_documented(value):
    assert value in QUOTED, f"SCHEMA.md never mentions `{value}`"


@pytest.mark.parametrize("field", sorted(FIELDS))
def test_every_field_is_documented(field):
    assert field in QUOTED, f"SCHEMA.md never mentions `{field}`"


def test_the_blocker_rule_is_explained_where_someone_will_read_it():
    assert "caps the whole readiness" in TEXT


def test_the_ladder_is_written_out_in_order():
    positions = [TEXT.index(f"`{p}`") for p in ("keep_human", "document_first")]
    assert positions == sorted(positions)


def test_the_refusal_to_state_a_conclusion_is_documented():
    assert "automatability" in QUOTED or '"automatability": 0.8' in TEXT
