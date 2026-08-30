"""The command line end to end, including the exit codes and the JSON."""

from __future__ import annotations

import io
import json

import pytest

from src.cli import CANNOT_RUN, FOUND_PROBLEMS, OK, main
from tests.conftest import EXAMPLE


def run(*argv):
    out = io.StringIO()
    code = main(list(argv), stdout=out)
    return code, out.getvalue()


@pytest.fixture()
def broken_map(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text(json.dumps({"company": "X"}), encoding="utf-8")
    return str(path)


# --- validate ---------------------------------------------------------------

def test_validating_the_example_succeeds():
    code, output = run("--map", str(EXAMPLE), "validate")
    assert code == OK
    assert "No problems" in output


def test_validating_a_broken_map_exits_one(broken_map):
    code, output = run("--map", broken_map, "validate")
    assert code == FOUND_PROBLEMS
    assert "missing_field" in output


def test_a_broken_map_reports_every_problem_not_the_first(broken_map):
    _, output = run("--map", broken_map, "validate")
    assert output.count("missing_field") >= 4


def test_validate_json_says_it_is_valid():
    code, output = run("--map", str(EXAMPLE), "--json", "validate")
    assert code == OK
    assert json.loads(output)["valid"] is True


def test_validate_json_carries_the_errors(broken_map):
    _, output = run("--map", broken_map, "--json", "validate")
    payload = json.loads(output)
    assert payload["valid"] is False
    assert {"code", "path", "message"} <= set(payload["errors"][0])


def test_a_missing_file_is_reported_rather_than_crashing(tmp_path):
    code, output = run("--map", str(tmp_path / "nope.json"), "validate")
    assert code == FOUND_PROBLEMS
    assert "no such file" in output


def test_a_file_that_is_not_json_is_reported(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    code, output = run("--map", str(path), "validate")
    assert code == FOUND_PROBLEMS
    assert "invalid_json" in output


# --- the other commands refuse to run on a broken map -----------------------

@pytest.mark.parametrize("command", ["rank", "gaps", "report"])
def test_no_command_pretends_a_broken_map_is_readable(command, broken_map):
    code, output = run("--map", broken_map, command)
    assert code == FOUND_PROBLEMS
    assert "missing_field" in output


# --- rank -------------------------------------------------------------------

def test_rank_prints_a_table():
    code, output = run("--map", str(EXAMPLE), "rank")
    assert code == OK
    assert "pattern" in output and "recover" in output


def test_rank_respects_the_limit():
    _, output = run("--map", str(EXAMPLE), "rank", "--limit", "3")
    rows = [line for line in output.splitlines() if line.startswith(("roast", "dtc", "deliv"))]
    assert len(rows) == 3


def test_rank_limit_zero_shows_everything():
    _, output = run("--map", str(EXAMPLE), "--json", "rank", "--limit", "0")
    assert len(json.loads(output)) == 50


def test_rank_says_how_many_it_left_out():
    _, output = run("--map", str(EXAMPLE), "rank", "--limit", "3")
    assert "47 more" in output


def test_rank_can_be_filtered_to_one_pattern():
    _, output = run("--map", str(EXAMPLE), "--json", "rank", "--pattern", "keep_human")
    assert {row["pattern"] for row in json.loads(output)} == {"keep_human"}


def test_rank_json_carries_the_working_not_just_the_answer():
    _, output = run("--map", str(EXAMPLE), "--json", "rank", "--limit", "1")
    row = json.loads(output)[0]
    expected = {"readiness", "axis_scores", "limiting_fact", "risk_band", "reason", "next_step"}
    assert expected <= set(row)


# --- trace ------------------------------------------------------------------

def test_trace_follows_an_artifact_back_to_what_produces_it():
    code, output = run("--map", str(EXAMPLE), "trace", "sales-invoice")
    assert code == OK
    assert "Issue wholesale invoices" in output


def test_trace_downstream_finds_the_consumers():
    _, output = run("--map", str(EXAMPLE), "trace", "green-contract", "--downstream")
    assert "Book green coffee in" in output


def test_tracing_an_inbound_artifact_says_where_it_stops():
    _, output = run("--map", str(EXAMPLE), "trace", "bank-statement")
    assert "declared inbound" in output


def test_tracing_an_unknown_artifact_cannot_run():
    code, output = run("--map", str(EXAMPLE), "trace", "nonsense")
    assert code == CANNOT_RUN
    assert "no artifact" in output


def test_trace_json_is_a_tree():
    _, output = run("--map", str(EXAMPLE), "--json", "trace", "sales-invoice", "--depth", "2")
    root = json.loads(output)
    assert root["kind"] == "artifact"
    assert root["children"][0]["kind"] == "function"


# --- gaps -------------------------------------------------------------------

def test_gaps_lists_findings_and_still_exits_zero():
    code, output = run("--map", str(EXAMPLE), "gaps")
    assert code == OK
    assert "unowned_function" in output


def test_strict_gaps_exits_one():
    code, _ = run("--map", str(EXAMPLE), "gaps", "--strict")
    assert code == FOUND_PROBLEMS


def test_gaps_json_is_a_list_of_findings():
    _, output = run("--map", str(EXAMPLE), "--json", "gaps")
    assert {"code", "severity", "subject", "message"} <= set(json.loads(output)[0])


# --- report -----------------------------------------------------------------

def test_report_names_the_company_and_the_totals():
    code, output = run("--map", str(EXAMPLE), "report")
    assert code == OK
    assert "Harbourgate Coffee Roasters" in output
    assert "recoverable hours a year" in output


def test_report_json_and_report_text_agree_on_the_totals():
    _, text = run("--map", str(EXAMPLE), "report")
    _, raw = run("--map", str(EXAMPLE), "--json", "report")
    payload = json.loads(raw)
    assert f"{payload['recoverable_hours']:,.0f} recoverable hours" in text


def test_report_json_carries_a_verdict_for_every_function():
    _, raw = run("--map", str(EXAMPLE), "--json", "report")
    payload = json.loads(raw)
    assert len(payload["functions_detail"]) == payload["functions"]


# --- settings ---------------------------------------------------------------

def test_the_map_defaults_to_the_bundled_example():
    code, output = run("validate")
    assert code == OK
    assert "Harbourgate" in output


def test_the_map_can_be_set_from_the_environment(monkeypatch):
    monkeypatch.setenv("FUNCTION_MAP_PATH", str(EXAMPLE))
    code, output = run("validate")
    assert code == OK
    assert "Harbourgate" in output


def test_an_unusable_setting_stops_the_run_rather_than_guessing(monkeypatch):
    monkeypatch.setenv("RANK_LIMIT", "loads")
    code, output = run("--map", str(EXAMPLE), "rank")
    assert code == CANNOT_RUN
    assert "RANK_LIMIT" in output


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        main([], stdout=io.StringIO())
