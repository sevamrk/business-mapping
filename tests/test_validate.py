"""The validator, one rejection per test.

Assertions are on error codes rather than messages, so a message can be
reworded without a red suite, and on the path too where the point of the test
is that the reader is told which row to look at.
"""

from __future__ import annotations

import pytest

from src.validate import validate
from tests.conftest import actor, artifact, automation, function, raw_map


def codes(raw) -> set:
    return {e.code for e in validate(raw)}


def paths(raw, code) -> list:
    return [e.path for e in validate(raw) if e.code == code]


# --- the happy path ---------------------------------------------------------

def test_the_minimal_map_is_valid():
    assert validate(raw_map()) == []


def test_notes_are_allowed_everywhere():
    raw = raw_map(
        actors=[actor(notes="part time")],
        artifacts=[artifact(notes="a note")],
        functions=[function(notes="a note")],
    )
    assert validate(raw) == []


def test_owner_may_be_null():
    assert validate(raw_map(functions=[function(owner=None)])) == []


def test_a_function_may_have_no_performers():
    assert validate(raw_map(functions=[function(performers=[])])) == []


# --- shape ------------------------------------------------------------------

def test_a_map_that_is_not_an_object_is_rejected():
    assert codes([]) == {"wrong_type"}


def test_a_missing_top_level_key_is_reported():
    raw = raw_map()
    del raw["functions"]
    assert "missing_field" in codes(raw)


def test_an_unknown_top_level_key_is_reported():
    assert "unknown_field" in codes(raw_map(departments=[]))


def test_functions_must_be_a_list():
    assert "wrong_type" in codes(raw_map(functions={}))


def test_a_function_that_is_not_an_object_is_reported():
    assert "wrong_type" in codes(raw_map(functions=["make-thing"]))


def test_a_missing_function_field_is_reported_with_its_path():
    fn = function()
    del fn["trigger"]
    assert "$.functions[0].trigger" in paths(raw_map(functions=[fn]), "missing_field")


def test_an_unknown_function_field_is_reported():
    assert "unknown_field" in codes(raw_map(functions=[function(cost_centre="ops")]))


# --- ids --------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["Make Thing", "make_thing", "make--thing", "-thing", "thing-", ""])
def test_ids_must_be_slugs(bad):
    assert "bad_id" in codes(raw_map(functions=[function(bad)]))


@pytest.mark.parametrize("good", ["a", "make-thing", "step-2", "a1"])
def test_reasonable_ids_are_accepted(good):
    assert "bad_id" not in codes(raw_map(functions=[function(good)]))


def test_duplicate_function_ids_are_reported():
    raw = raw_map(functions=[function("same"), function("same")])
    assert "duplicate_id" in codes(raw)


def test_duplicate_actor_ids_are_reported():
    assert "duplicate_id" in codes(raw_map(actors=[actor(), actor()]))


def test_duplicate_artifact_ids_are_reported():
    raw = raw_map(artifacts=[artifact("thing"), artifact("thing")])
    assert "duplicate_id" in codes(raw)


# --- enums ------------------------------------------------------------------

def test_an_unknown_trigger_is_rejected():
    assert "bad_enum" in codes(raw_map(functions=[function(trigger="whenever")]))


def test_an_unknown_current_state_is_rejected():
    assert "bad_enum" in codes(raw_map(functions=[function(current_state="mostly")]))


def test_an_unknown_actor_kind_is_rejected():
    assert "bad_enum" in codes(raw_map(actors=[actor(kind="person")]))


def test_an_unknown_artifact_form_is_rejected():
    raw = raw_map(artifacts=[artifact(form="pdf")])
    assert "bad_enum" in codes(raw)


def test_an_unknown_artifact_boundary_is_rejected():
    raw = raw_map(artifacts=[artifact(boundary="external")])
    assert "bad_enum" in codes(raw)


@pytest.mark.parametrize(
    "fact,bad",
    [
        ("decision_type", "sometimes"),
        ("input_form", "spreadsheet"),
        ("interface", "rest"),
        ("change_rate", "sometimes"),
        ("error_cost", "bad"),
        ("reversibility", "no"),
        ("oversight", "always"),
    ],
)
def test_every_automation_fact_is_checked_against_its_vocabulary(fact, bad):
    fn = function(automation=automation(**{fact: bad}))
    errors = [e for e in validate(raw_map(functions=[fn])) if e.code == "bad_enum"]
    assert [e.path for e in errors] == [f"$.functions[0].automation.{fact}"]


def test_the_error_message_lists_what_was_allowed():
    fn = function(automation=automation(interface="rest"))
    message = next(e.message for e in validate(raw_map(functions=[fn])) if e.code == "bad_enum")
    assert "api" in message and "ui_only" in message


# --- the automation block ---------------------------------------------------

def test_a_missing_automation_fact_is_reported():
    block = automation()
    del block["oversight"]
    fn = function(automation=block)
    assert "$.functions[0].automation.oversight" in paths(raw_map(functions=[fn]), "missing_field")


def test_an_unknown_automation_fact_is_reported():
    fn = function(automation=automation(vibe="good"))
    assert "unknown_field" in codes(raw_map(functions=[fn]))


@pytest.mark.parametrize(
    "name", ["automatability", "automation_score", "readiness", "score", "pattern", "priority"]
)
def test_stating_the_conclusion_is_refused_by_name(name):
    fn = function(automation=automation(**{name: 0.8}))
    assert "derived_field" in codes(raw_map(functions=[fn]))


def test_the_refusal_explains_why_rather_than_saying_unknown_key():
    fn = function(automation=automation(automatability=0.9))
    errors = validate(raw_map(functions=[fn]))
    message = next(e.message for e in errors if e.code == "derived_field")
    assert "worked out from the seven facts" in message


def test_a_derived_field_is_not_also_reported_as_an_unknown_field():
    fn = function(automation=automation(readiness=1))
    reported = [e for e in validate(raw_map(functions=[fn])) if e.path.endswith(".readiness")]
    assert [e.code for e in reported] == ["derived_field"]


# --- numbers ----------------------------------------------------------------

def test_a_negative_volume_is_rejected():
    assert "out_of_range" in codes(raw_map(functions=[function(volume_per_month=-1)]))


def test_a_zero_volume_is_allowed_because_a_dormant_function_is_a_real_thing():
    assert "out_of_range" not in codes(raw_map(functions=[function(volume_per_month=0)]))


def test_a_zero_duration_is_rejected():
    assert "out_of_range" in codes(raw_map(functions=[function(minutes_per_run=0)]))


def test_a_boolean_does_not_pass_as_a_number():
    assert "wrong_type" in codes(raw_map(functions=[function(volume_per_month=True)]))


def test_a_string_volume_is_rejected():
    assert "wrong_type" in codes(raw_map(functions=[function(volume_per_month="ten")]))


# --- references -------------------------------------------------------------

def test_an_owner_who_is_not_an_actor_is_reported():
    assert "unknown_actor" in codes(raw_map(functions=[function(owner="nobody")]))


def test_a_performer_who_is_not_an_actor_is_reported():
    raw = raw_map(functions=[function(performers=["alice", "ghost"])])
    assert paths(raw, "unknown_actor") == ["$.functions[0].performers[1]"]


def test_an_input_that_is_not_an_artifact_is_reported():
    assert "unknown_artifact" in codes(raw_map(functions=[function(inputs=["nothing"])]))


def test_an_output_that_is_not_an_artifact_is_reported():
    assert "unknown_artifact" in codes(raw_map(functions=[function(outputs=["nothing"])]))


def test_the_same_input_listed_twice_is_reported():
    raw = raw_map(artifacts=[artifact()], functions=[function(inputs=["thing", "thing"])])
    assert "duplicate_reference" in codes(raw)


def test_a_non_string_in_a_reference_list_is_reported():
    assert "wrong_type" in codes(raw_map(functions=[function(inputs=[7])]))


# --- boundaries -------------------------------------------------------------

def test_producing_an_inbound_artifact_contradicts_its_declaration():
    raw = raw_map(
        artifacts=[artifact("thing", boundary="inbound")],
        functions=[function(outputs=["thing"])],
    )
    assert "boundary_conflict" in codes(raw)


def test_consuming_an_outbound_artifact_contradicts_its_declaration():
    raw = raw_map(
        artifacts=[artifact("thing", boundary="outbound")],
        functions=[function(inputs=["thing"])],
    )
    assert "boundary_conflict" in codes(raw)


def test_consuming_an_inbound_artifact_is_the_normal_case():
    raw = raw_map(
        artifacts=[artifact("thing", boundary="inbound")],
        functions=[function(inputs=["thing"])],
    )
    assert validate(raw) == []


# --- collecting -------------------------------------------------------------

def test_every_problem_is_reported_not_just_the_first():
    raw = raw_map(
        functions=[
            function("Bad Id", trigger="whenever", owner="nobody", volume_per_month=-3),
        ]
    )
    assert codes(raw) >= {"bad_id", "bad_enum", "unknown_actor", "out_of_range"}


def test_a_second_broken_function_is_reported_as_well():
    raw = raw_map(functions=[function("a", trigger="x"), function("b", trigger="y")])
    assert sorted(paths(raw, "bad_enum")) == ["$.functions[0].trigger", "$.functions[1].trigger"]


def test_an_error_renders_as_path_then_message():
    error = next(e for e in validate(raw_map(functions=[function(trigger="x")])))
    assert str(error).startswith("$.functions[0].trigger: ")
