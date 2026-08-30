"""Rendering, and the promise that the text and the JSON come from one place."""

from __future__ import annotations

from src import report
from tests.conftest import artifact, automation, built, function


def test_a_table_lines_up_under_its_headers():
    out = report.table(["id", "n"], [["a", "1"], ["longer", "2"]])
    lines = out.splitlines()
    assert lines[1].startswith("------")
    assert lines[2].startswith("a     ")


def test_a_table_with_no_rows_is_still_a_header():
    assert report.table(["id"], []).splitlines()[0] == "id"


def test_the_summary_and_the_report_agree_on_recoverable_hours():
    fmap = built()
    data = report.summarise(fmap)
    assert f"{data['recoverable_hours']:,.0f} recoverable hours" in report.render_report(fmap)


def test_the_summary_totals_the_hours_across_functions():
    fmap = built(
        functions=[
            function("a", volume_per_month=10, minutes_per_run=60),
            function("b", volume_per_month=10, minutes_per_run=60),
        ]
    )
    assert report.summarise(fmap)["hours_per_year"] == 240.0


def test_hours_already_automated_are_counted_separately():
    fmap = built(
        functions=[
            function("a", volume_per_month=10, minutes_per_run=60, current_state="automated"),
            function("b", volume_per_month=10, minutes_per_run=60, current_state="manual"),
        ]
    )
    data = report.summarise(fmap)
    assert data["hours_already_automated"] == 120.0
    assert data["hours_per_year"] == 240.0


def test_the_headcount_figure_uses_the_configured_working_year(monkeypatch):
    fmap = built(functions=[function(volume_per_month=100, minutes_per_run=60)])
    monkeypatch.setenv("HOURS_PER_FTE_YEAR", "1200")
    assert report.summarise(fmap)["recoverable_fte"] == 1.0


def test_areas_are_broken_out():
    fmap = built(
        functions=[function("a", area="finance"), function("b", area="operations")]
    )
    assert set(report.summarise(fmap)["by_area"]) == {"finance", "operations"}


def test_unowned_functions_are_counted_per_area():
    fmap = built(functions=[function("a", area="finance", owner=None)])
    assert report.summarise(fmap)["by_area"]["finance"]["unowned"] == 1


def test_a_pattern_nobody_landed_on_is_left_out_of_the_table():
    out = report.render_report(built())
    assert "keep_human" not in out


def test_the_trace_renderer_marks_the_depth_limit():
    fmap = built(
        artifacts=[artifact("a"), artifact("b"), artifact("c")],
        functions=[
            function("one", inputs=["a"], outputs=["b"]),
            function("two", inputs=["b"], outputs=["c"]),
        ],
    )
    out = report.render_trace(fmap, "c", "upstream", depth=1)
    assert "raise --depth" in out


def test_the_trace_renderer_uses_the_direction_arrow():
    fmap = built(
        artifacts=[artifact("a"), artifact("b")],
        functions=[function("one", inputs=["a"], outputs=["b"])],
    )
    assert "<- Thing" in report.render_trace(fmap, "b", "upstream", depth=3)
    assert "-> Thing" in report.render_trace(fmap, "a", "downstream", depth=3)


def test_rendering_no_gaps_says_so():
    assert report.render_gaps([]) == "No gaps found."


def test_the_validation_summary_counts_everything():
    out = report.render_validation_ok(built())
    assert "1 functions, 1 actors, 0 artifacts" in out


def test_a_keep_human_function_shows_no_recoverable_hours():
    fn = function(
        automation=automation(decision_type="discretionary"),
        volume_per_month=100,
        minutes_per_run=60,
    )
    data = report.summarise(built(functions=[fn]))
    assert data["by_pattern"]["keep_human"]["hours"] == 1200.0
    assert data["by_pattern"]["keep_human"]["recoverable"] == 0.0
