"""The derivation: seven facts in, a verdict out.

The tests that matter here are the ones where a fact overrides the average,
because that is the whole argument for not letting the author write a number.
"""

from __future__ import annotations

import pytest

from src import vocab
from src.automatability import (
    BLOCKED_CEILING,
    assess,
    axis_scores,
    blockers,
    limiting_fact,
    rank,
    readiness,
    risk_band,
    risk_level,
)
from src.model import Automation
from tests.conftest import automation, built, function


def auto(**overrides) -> Automation:
    return Automation.from_dict(automation(**overrides))


def verdict(**overrides):
    fn = function(automation=automation(**overrides))
    return assess(built(functions=[fn]).functions[0])


# --- readiness --------------------------------------------------------------

def test_the_best_possible_answers_score_one():
    assert readiness(auto()) == 1.0


def test_the_weights_add_up_to_one():
    assert sum(vocab.READINESS_WEIGHTS.values()) == pytest.approx(1.0)


def test_readiness_uses_only_the_capability_facts():
    strict = auto(error_cost="severe", reversibility="irreversible", oversight="regulatory")
    assert readiness(strict) == readiness(auto())


def test_a_weaker_level_lowers_the_score():
    assert readiness(auto(decision_type="judgement")) < readiness(auto())


def test_each_capability_fact_moves_the_score_on_its_own():
    for fact, levels in (
        ("decision_type", "judgement"),
        ("input_form", "semi_structured"),
        ("interface", "bulk_export"),
        ("change_rate", "periodic"),
    ):
        assert readiness(auto(**{fact: levels})) < 1.0, fact


def test_axis_scores_name_all_four_capability_facts():
    assert set(axis_scores(auto())) == set(vocab.CAPABILITY_FACTS)


# --- the blocker cap --------------------------------------------------------

def test_a_zero_on_one_axis_caps_the_whole_score():
    # Deterministic, structured, stable, and it happens in a room. Picking
    # parcels off a shelf scores 0.75 on an average and cannot be handed over.
    assert readiness(auto(interface="offline")) == BLOCKED_CEILING


def test_tacit_input_caps_the_score_too():
    assert readiness(auto(input_form="tacit")) == BLOCKED_CEILING


def test_the_cap_is_a_ceiling_not_a_value():
    weak = auto(
        interface="offline",
        decision_type="discretionary",
        input_form="unstructured",
        change_rate="volatile",
    )
    assert readiness(weak) < BLOCKED_CEILING


def test_blockers_names_the_axis_that_is_zero():
    assert blockers(auto(interface="offline")) == ["interface"]


def test_a_map_with_no_zero_has_no_blockers():
    assert blockers(auto(interface="ui_only")) == []


def test_the_limiting_fact_is_the_weakest_axis():
    assert limiting_fact(auto(input_form="unstructured")) == "input_form"


def test_the_limiting_fact_of_a_perfect_function_is_still_reported():
    assert limiting_fact(auto()) in vocab.CAPABILITY_FACTS


# --- risk -------------------------------------------------------------------

def test_risk_is_the_highest_of_the_three_not_their_average():
    # One irreversible action beside two harmless ones is an irreversible one.
    assert risk_level(auto(reversibility="irreversible")) == 3


def test_a_severe_error_cost_alone_reaches_critical():
    assert risk_band(auto(error_cost="severe")) == "critical"


def test_regulatory_oversight_alone_reaches_critical():
    assert risk_band(auto(oversight="regulatory")) == "critical"


def test_the_gentlest_answers_are_low_risk():
    assert risk_band(auto()) == "low"


@pytest.mark.parametrize("level,band", list(enumerate(vocab.RISK_BANDS)))
def test_every_risk_level_has_a_band(level, band):
    assert vocab.RISK_BANDS[level] == band


# --- the pattern ladder -----------------------------------------------------

def test_a_clean_deterministic_function_is_agent_led():
    assert verdict().pattern == "agent_led"


def test_discretionary_judgement_stays_with_a_person():
    assert verdict(decision_type="discretionary").pattern == "keep_human"


def test_a_regulatory_signature_stays_with_a_person():
    assert verdict(oversight="regulatory").pattern == "keep_human"


def test_a_perfect_function_with_a_regulatory_signature_still_stays_with_a_person():
    # Everything about the VAT return is machine-readable. It is still signed.
    assert verdict(oversight="regulatory").readiness == 1.0
    assert verdict(oversight="regulatory").pattern == "keep_human"


def test_an_input_that_lives_in_somebodys_head_needs_writing_down_first():
    assert verdict(input_form="tacit").pattern == "document_first"


def test_work_that_happens_offline_needs_a_system_before_anything_else():
    assert verdict(interface="offline").pattern == "instrument_first"


def test_a_screen_only_system_needs_an_interface_before_anything_else():
    assert verdict(interface="ui_only").pattern == "instrument_first"


def test_an_irreversible_action_gets_a_human_release_even_when_ready():
    result = verdict(reversibility="irreversible")
    assert result.readiness == 1.0
    assert result.pattern == "agent_with_approval"


def test_a_severe_error_cost_gets_a_human_release():
    assert verdict(error_cost="severe").pattern == "agent_with_approval"


def test_rules_that_change_constantly_cap_out_at_assisted():
    assert verdict(change_rate="volatile").pattern == "assisted"


def test_a_partly_readable_function_is_assisted():
    assert verdict(decision_type="judgement", input_form="unstructured").pattern == "assisted"


def test_capability_blockers_are_decided_before_control_questions():
    # There is no point discussing who approves a thing nobody can do yet.
    assert verdict(interface="ui_only", error_cost="severe").pattern == "instrument_first"


def test_discretion_beats_every_other_blocker():
    result = verdict(decision_type="discretionary", input_form="tacit", interface="offline")
    assert result.pattern == "keep_human"


def test_every_pattern_carries_a_reason_and_a_next_step():
    for overrides in (
        {},
        {"decision_type": "discretionary"},
        {"input_form": "tacit"},
        {"interface": "offline"},
        {"error_cost": "severe"},
        {"change_rate": "volatile"},
        {"decision_type": "judgement", "input_form": "unstructured"},
    ):
        result = verdict(**overrides)
        assert result.reason and result.next_step, overrides


def test_the_ladder_only_ever_returns_a_known_pattern():
    for decision in vocab.DECISION_TYPES:
        for form in vocab.INPUT_FORMS:
            for interface in vocab.INTERFACES:
                result = verdict(decision_type=decision, input_form=form, interface=interface)
                assert result.pattern in vocab.PATTERNS


# --- bands and hours --------------------------------------------------------

@pytest.mark.parametrize(
    "overrides,band",
    [
        ({}, "ready"),
        ({"decision_type": "judgement", "input_form": "unstructured"}, "partial"),
        ({"interface": "offline"}, "weak"),
        (
            {"decision_type": "discretionary", "input_form": "tacit", "interface": "offline"},
            "blocked",
        ),
    ],
)
def test_readiness_bands(overrides, band):
    assert verdict(**overrides).readiness_band == band


def test_hours_come_from_volume_and_duration():
    fn = built(functions=[function(volume_per_month=100, minutes_per_run=30)]).functions[0]
    assert assess(fn).hours_per_year == pytest.approx(600.0)


def test_a_function_already_automated_recovers_nothing():
    fn = built(functions=[function(current_state="automated")]).functions[0]
    assert assess(fn).recoverable_hours == 0.0


def test_a_half_automated_function_recovers_half():
    manual = built(functions=[function(current_state="manual")]).functions[0]
    assisted = built(functions=[function(current_state="assisted")]).functions[0]
    assert assess(assisted).recoverable_hours == pytest.approx(
        assess(manual).recoverable_hours / 2
    )


def test_work_the_verdict_leaves_with_a_person_recovers_nothing():
    fn = function(automation=automation(decision_type="discretionary"), volume_per_month=500)
    result = assess(built(functions=[fn]).functions[0])
    assert result.pattern == "keep_human"
    assert result.recoverable_hours == 0.0


# --- ranking ----------------------------------------------------------------

def test_ranking_puts_the_most_recoverable_hours_first():
    small = function("small", volume_per_month=1, minutes_per_run=5)
    large = function("large", volume_per_month=100, minutes_per_run=60)
    ordered = rank(built(functions=[small, large]).functions)
    assert [fn.id for fn, _ in ordered] == ["large", "small"]


def test_ranking_prefers_hours_over_readiness():
    # A perfectly automatable twenty minutes a year is not where to start.
    tiny_perfect = function("tiny", volume_per_month=1, minutes_per_run=2)
    big_partial = function(
        "big",
        volume_per_month=200,
        minutes_per_run=30,
        automation=automation(decision_type="judgement", input_form="unstructured"),
    )
    ordered = rank(built(functions=[tiny_perfect, big_partial]).functions)
    assert [fn.id for fn, _ in ordered] == ["big", "tiny"]


def test_ranking_can_be_filtered_to_one_pattern():
    keep = function("keep", automation=automation(decision_type="discretionary"))
    ready = function("ready")
    ordered = rank(built(functions=[keep, ready]).functions, pattern="agent_led")
    assert [fn.id for fn, _ in ordered] == ["ready"]


def test_ranking_is_stable_when_everything_ties():
    fns = [function("b"), function("a"), function("c")]
    ordered = rank(built(functions=fns).functions)
    assert [fn.id for fn, _ in ordered] == ["a", "b", "c"]
