"""Findings: things that are legal to write down and worth someone's attention."""

from __future__ import annotations

from src import gaps
from tests.conftest import actor, artifact, automation, built, function


def find(**overrides) -> dict:
    findings = gaps.find(built(**overrides))
    return {f.code: f for f in findings}


def test_a_map_with_nothing_to_say_produces_nothing():
    assert gaps.find(built(functions=[function(current_state="automated")])) == []


def test_a_function_with_no_owner_is_reported():
    assert "unowned_function" in find(functions=[function(owner=None)])


def test_an_unowned_function_is_high_severity():
    assert find(functions=[function(owner=None)])["unowned_function"].severity == "high"


def test_the_unowned_message_carries_the_hours_so_it_can_be_prioritised():
    finding = find(functions=[function(owner=None, volume_per_month=100, minutes_per_run=30)])
    assert "600 hours" in finding["unowned_function"].message


def test_a_function_nobody_performs_is_reported():
    assert "no_performer" in find(functions=[function(performers=[])])


def test_an_internal_artifact_nothing_produces_is_reported():
    result = find(
        artifacts=[artifact("thing")],
        functions=[function(inputs=["thing"])],
    )
    assert "unsourced_input" in result


def test_an_inbound_artifact_nothing_produces_is_not_reported():
    result = find(
        artifacts=[artifact("thing", boundary="inbound")],
        functions=[function(inputs=["thing"])],
    )
    assert "unsourced_input" not in result


def test_an_internal_artifact_nothing_reads_is_reported():
    result = find(
        artifacts=[artifact("thing")],
        functions=[function(outputs=["thing"])],
    )
    assert "orphan_output" in result


def test_an_outbound_artifact_nothing_reads_is_not_reported():
    result = find(
        artifacts=[artifact("thing", boundary="outbound")],
        functions=[function(outputs=["thing"])],
    )
    assert "orphan_output" not in result


def test_an_artifact_nothing_touches_at_all_is_reported_once():
    result = find(artifacts=[artifact("stray")])
    assert "unused_artifact" in result
    assert "orphan_output" not in result
    assert "unsourced_input" not in result


def test_an_actor_who_does_nothing_is_reported():
    result = find(actors=[actor(), actor("bob", name="Bob")])
    assert result["idle_actor"].subject == "bob"


def test_an_external_actor_who_does_nothing_is_context_not_a_finding():
    result = find(actors=[actor(), actor("carrier", name="Carrier", kind="external")])
    assert "idle_actor" not in result


def test_being_the_only_person_on_five_functions_is_reported():
    fns = [function(f"job-{i}", performers=["alice"]) for i in range(gaps.SOLE_PERFORMER_LIMIT)]
    assert "single_point_of_failure" in find(functions=fns)


def test_four_is_not_yet_a_single_point_of_failure():
    fns = [function(f"job-{i}", performers=["alice"]) for i in range(4)]
    assert "single_point_of_failure" not in find(functions=fns)


def test_sharing_the_work_with_a_second_person_clears_it():
    actors = [actor(), actor("bob", name="Bob")]
    fns = [
        function(f"job-{i}", performers=["alice", "bob"])
        for i in range(gaps.SOLE_PERFORMER_LIMIT)
    ]
    assert "single_point_of_failure" not in find(actors=actors, functions=fns)


def test_a_system_doing_five_things_alone_is_not_a_holiday_risk():
    actors = [actor(), actor("erp", name="ERP", kind="system")]
    fns = [function(f"job-{i}", performers=["erp"]) for i in range(gaps.SOLE_PERFORMER_LIMIT)]
    assert "single_point_of_failure" not in find(actors=actors, functions=fns)


def test_claiming_a_discretionary_function_is_automated_is_a_contradiction():
    fn = function(
        current_state="automated", automation=automation(decision_type="discretionary")
    )
    assert "state_conflicts_with_facts" in find(functions=[fn])


def test_the_contradiction_is_high_severity():
    fn = function(current_state="automated", automation=automation(input_form="tacit"))
    assert find(functions=[fn])["state_conflicts_with_facts"].severity == "high"


def test_a_ready_function_still_done_by_hand_is_reported():
    assert "ready_and_untouched" in find(functions=[function(current_state="manual")])


def test_a_ready_function_already_automated_is_not_reported():
    assert "ready_and_untouched" not in find(functions=[function(current_state="automated")])


def test_a_blocked_function_done_by_hand_is_not_reported_as_untouched():
    fn = function(current_state="manual", automation=automation(interface="offline"))
    assert "ready_and_untouched" not in find(functions=[fn])


def test_a_dependency_loop_is_reported():
    result = find(
        artifacts=[artifact("plan"), artifact("forecast")],
        functions=[
            function("plan-it", inputs=["forecast"], outputs=["plan"]),
            function("forecast-it", inputs=["plan"], outputs=["forecast"]),
        ],
    )
    assert "dependency_loop" in result


def test_the_loop_message_names_every_function_in_it():
    result = find(
        artifacts=[artifact("plan"), artifact("forecast")],
        functions=[
            function("plan-it", inputs=["forecast"], outputs=["plan"]),
            function("forecast-it", inputs=["plan"], outputs=["forecast"]),
        ],
    )
    message = result["dependency_loop"].message
    assert "plan-it" in message and "forecast-it" in message


def test_findings_come_back_worst_first():
    fmap = built(
        actors=[actor(), actor("bob", name="Bob")],
        artifacts=[artifact("stray")],
        functions=[function(owner=None)],
    )
    severities = [f.severity for f in gaps.find(fmap)]
    assert severities == sorted(severities, key=["high", "medium", "low"].index)
