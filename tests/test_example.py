"""The worked example is part of the deliverable, so it is tested like one.

Two jobs here. One is that the example stays valid. The other is that it stays
*varied*: an example where every function is deterministic and structured makes
the model look better than it is and teaches a reader nothing.
"""

from __future__ import annotations

import pytest

from src import gaps, vocab
from src.automatability import assess

VOCABULARIES = {
    "kind": vocab.ACTOR_KINDS,
    "form": vocab.ARTIFACT_FORMS,
    "boundary": vocab.ARTIFACT_BOUNDARIES,
    "trigger": vocab.TRIGGERS,
    "current_state": tuple(vocab.CURRENT_STATES),
}


def test_the_example_loads(example_map):
    assert example_map.company == "Harbourgate Coffee Roasters"


def test_the_example_says_it_is_invented(example_map):
    assert "invented" in example_map.description


def test_the_example_is_big_enough_to_be_worth_reading(example_map):
    assert len(example_map.functions) >= 40
    assert len(example_map.artifacts) >= 40
    assert len(example_map.actors) >= 15


def test_the_example_covers_more_than_one_department(example_map):
    assert len(example_map.areas) >= 6


@pytest.mark.parametrize("field,values", sorted(VOCABULARIES.items()))
def test_the_example_uses_every_level_of_every_vocabulary(field, values, example_raw):
    used = set()
    for collection in ("actors", "artifacts", "functions"):
        for row in example_raw[collection]:
            if field in row:
                used.add(row[field])
    assert set(values) <= used, f"{field}: never used {sorted(set(values) - used)}"


@pytest.mark.parametrize("fact", vocab.AUTOMATION_FACTS)
def test_the_example_uses_every_level_of_every_automation_fact(fact, example_raw):
    used = {fn["automation"][fact] for fn in example_raw["functions"]}
    missing = set(vocab.FACT_VALUES[fact]) - used
    assert not missing, f"{fact}: never used {sorted(missing)}"


@pytest.mark.parametrize("pattern", vocab.PATTERNS)
def test_every_pattern_is_reachable_from_the_example(pattern, example_map):
    reached = {assess(fn).pattern for fn in example_map.functions}
    assert pattern in reached


def test_the_example_is_plain_ascii(example_raw):
    # A stray smart quote or a name in another alphabet is worth noticing.
    import json

    json.dumps(example_raw, ensure_ascii=True).encode("ascii")


# --- the defects it carries on purpose --------------------------------------
# The example is not a clean map. A clean map would prove the checks compile
# and nothing else, so a handful of real problems are written into it.

@pytest.mark.parametrize(
    "code",
    [
        "unowned_function",
        "no_performer",
        "unsourced_input",
        "orphan_output",
        "idle_actor",
        "single_point_of_failure",
        "ready_and_untouched",
        "dependency_loop",
    ],
)
def test_the_example_exercises_each_check(code, example_map):
    assert code in {f.code for f in gaps.find(example_map)}


def test_the_one_unowned_function_is_the_one_meant_to_be_unowned(example_map):
    unowned = [f.subject for f in gaps.find(example_map) if f.code == "unowned_function"]
    assert unowned == ["onboarding-new-starter"]


def test_the_example_has_no_contradictions_between_state_and_facts(example_map):
    codes = {f.code for f in gaps.find(example_map)}
    assert "state_conflicts_with_facts" not in codes


def test_the_biggest_block_of_hours_is_physical_work(example_map):
    # The point the example is making: the largest number on the page is not a
    # software problem, and a model that scored it as one would be wrong.
    worst = max(example_map.functions, key=lambda fn: fn.hours_per_year)
    assert worst.id == "dtc-order-picking"
    assert assess(worst).pattern == "instrument_first"


def test_a_perfectly_ready_function_can_still_be_barred_from_running_alone(example_map):
    payment_run = example_map.function("payment-run")
    verdict = assess(payment_run)
    assert verdict.readiness == 1.0
    assert verdict.pattern == "agent_with_approval"


def test_the_vat_return_is_ready_and_still_signed_by_a_person(example_map):
    verdict = assess(example_map.function("vat-return"))
    assert verdict.readiness_band == "ready"
    assert verdict.pattern == "keep_human"


def test_the_thing_blocking_production_cupping_is_that_nobody_wrote_it_down(example_map):
    verdict = assess(example_map.function("production-cupping"))
    assert verdict.pattern == "document_first"
    assert verdict.limiting_fact == "input_form"
