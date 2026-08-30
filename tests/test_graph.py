"""Following artifacts: producers, consumers, tracing, and loops."""

from __future__ import annotations

import pytest

from src import graph
from tests.conftest import artifact, built, function


def chain():
    """order -> pick -> parcel -> ship -> shipment."""
    return built(
        artifacts=[
            artifact("order", boundary="inbound"),
            artifact("parcel"),
            artifact("shipment", boundary="outbound"),
        ],
        functions=[
            function("pick", inputs=["order"], outputs=["parcel"]),
            function("ship", inputs=["parcel"], outputs=["shipment"]),
        ],
    )


def loop():
    """Two functions that feed each other, which is legal and worth knowing."""
    return built(
        artifacts=[artifact("plan"), artifact("forecast")],
        functions=[
            function("plan-it", inputs=["forecast"], outputs=["plan"]),
            function("forecast-it", inputs=["plan"], outputs=["forecast"]),
        ],
    )


# --- producers and consumers ------------------------------------------------

def test_the_producer_of_an_artifact_is_found():
    assert [f.id for f in graph.producers(chain(), "parcel")] == ["pick"]


def test_the_consumer_of_an_artifact_is_found():
    assert [f.id for f in graph.consumers(chain(), "parcel")] == ["ship"]


def test_an_inbound_artifact_has_no_producer():
    assert graph.producers(chain(), "order") == []


def test_an_outbound_artifact_has_no_consumer():
    assert graph.consumers(chain(), "shipment") == []


def test_an_artifact_can_have_several_producers():
    fmap = built(
        artifacts=[artifact("book")],
        functions=[
            function("typed", outputs=["book"]),
            function("standing", outputs=["book"]),
        ],
    )
    assert len(graph.producers(fmap, "book")) == 2


# --- tracing ----------------------------------------------------------------

def test_tracing_upstream_reaches_the_function_that_produces_it():
    root = graph.trace(chain(), "shipment", "upstream", depth=2)
    assert [c.id for c in root.children] == ["ship"]


def test_tracing_upstream_keeps_going_through_the_inputs():
    root = graph.trace(chain(), "shipment", "upstream", depth=4)
    ids = [node.id for _, node in graph.flatten(root)]
    assert ids == ["shipment", "ship", "parcel", "pick", "order"]


def test_tracing_downstream_follows_the_consumers():
    root = graph.trace(chain(), "order", "downstream", depth=4)
    ids = [node.id for _, node in graph.flatten(root)]
    assert ids == ["order", "pick", "parcel", "ship", "shipment"]


def test_the_depth_limit_marks_where_it_stopped():
    root = graph.trace(chain(), "shipment", "upstream", depth=1)
    assert root.children[0].truncated is True


def test_nothing_is_truncated_when_the_depth_is_enough():
    root = graph.trace(chain(), "shipment", "upstream", depth=6)
    assert not any(node.truncated for _, node in graph.flatten(root))


def test_a_loop_does_not_trace_forever():
    root = graph.trace(loop(), "plan", "upstream", depth=10)
    assert any(node.repeated for _, node in graph.flatten(root))


def test_tracing_carries_the_owner_so_the_reader_knows_who_to_ask():
    root = graph.trace(chain(), "parcel", "upstream", depth=1)
    assert root.children[0].detail == "Alice"


def test_tracing_an_unowned_function_says_so():
    fmap = built(
        artifacts=[artifact("thing")],
        functions=[function("make", owner=None, performers=[], outputs=["thing"])],
    )
    root = graph.trace(fmap, "thing", "upstream", depth=1)
    assert root.children[0].detail == "no owner"


def test_tracing_an_unknown_artifact_raises():
    with pytest.raises(KeyError):
        graph.trace(chain(), "nope", "upstream", 2)


def test_an_unknown_direction_raises():
    with pytest.raises(ValueError):
        graph.trace(chain(), "parcel", "sideways", 2)


# --- dependency edges and loops --------------------------------------------

def test_edges_run_from_producer_to_consumer():
    assert graph.dependency_edges(chain())["pick"] == ["ship"]


def test_a_function_is_not_its_own_dependency():
    fmap = built(
        artifacts=[artifact("thing")],
        functions=[function("update", inputs=["thing"], outputs=["thing"])],
    )
    assert graph.dependency_edges(fmap)["update"] == []


def test_a_straight_chain_has_no_loops():
    assert graph.cycles(chain()) == []


def test_two_functions_feeding_each_other_are_reported_once():
    assert graph.cycles(loop()) == [["forecast-it", "plan-it"]]


def test_a_longer_loop_is_reported_as_a_path():
    fmap = built(
        artifacts=[artifact("a"), artifact("b"), artifact("c")],
        functions=[
            function("one", inputs=["c"], outputs=["a"]),
            function("two", inputs=["a"], outputs=["b"]),
            function("three", inputs=["b"], outputs=["c"]),
        ],
    )
    assert graph.cycles(fmap) == [["one", "two", "three"]]


def test_strongly_connected_groups_separate_the_loop_from_the_rest():
    fmap = built(
        artifacts=[artifact("plan"), artifact("forecast"), artifact("report", boundary="outbound")],
        functions=[
            function("plan-it", inputs=["forecast"], outputs=["plan"]),
            function("forecast-it", inputs=["plan"], outputs=["forecast"]),
            function("report-it", inputs=["plan"], outputs=["report"]),
        ],
    )
    groups = graph.strongly_connected(fmap)
    assert ["forecast-it", "plan-it"] in groups
    assert ["report-it"] in groups


def test_a_deep_chain_does_not_exhaust_the_stack():
    # Iterative on purpose; a map written by people has no depth limit.
    artifacts = [artifact(f"a{i}") for i in range(600)]
    functions = [
        function(f"step-{i}", inputs=[f"a{i}"], outputs=[f"a{i + 1}"]) for i in range(599)
    ]
    fmap = built(artifacts=artifacts, functions=functions)
    assert graph.cycles(fmap) == []
