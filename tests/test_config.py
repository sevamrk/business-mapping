"""Settings. A clone with an empty environment has to work, and a typo has to be loud."""

from __future__ import annotations

import pytest

from src import config


def test_the_default_map_is_the_bundled_example():
    assert config.map_path().name == "harbourgate-coffee.json"


def test_the_default_map_exists_in_a_fresh_clone():
    assert config.map_path().is_file()


def test_a_relative_path_resolves_against_the_repository_not_the_shell(monkeypatch):
    monkeypatch.setenv("FUNCTION_MAP_PATH", "examples/harbourgate-coffee.json")
    assert config.map_path().is_file()


def test_an_absolute_path_is_left_alone(monkeypatch, tmp_path):
    monkeypatch.setenv("FUNCTION_MAP_PATH", str(tmp_path / "map.json"))
    assert config.map_path() == tmp_path / "map.json"


def test_an_empty_setting_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("FUNCTION_MAP_PATH", "   ")
    assert config.map_path().name == "harbourgate-coffee.json"


def test_the_working_year_has_a_default():
    assert config.hours_per_fte_year() == 1600.0


def test_the_working_year_can_be_argued_with(monkeypatch):
    monkeypatch.setenv("HOURS_PER_FTE_YEAR", "1840")
    assert config.hours_per_fte_year() == 1840.0


def test_a_working_year_of_zero_is_refused(monkeypatch):
    monkeypatch.setenv("HOURS_PER_FTE_YEAR", "0")
    with pytest.raises(config.ConfigError):
        config.hours_per_fte_year()


def test_a_working_year_that_is_not_a_number_is_refused(monkeypatch):
    monkeypatch.setenv("HOURS_PER_FTE_YEAR", "a lot")
    with pytest.raises(config.ConfigError):
        config.hours_per_fte_year()


def test_the_rank_limit_has_a_default():
    assert config.rank_limit() == 15


def test_the_rank_limit_can_be_set(monkeypatch):
    monkeypatch.setenv("RANK_LIMIT", "40")
    assert config.rank_limit() == 40


def test_a_rank_limit_of_zero_means_all_of_them(monkeypatch):
    monkeypatch.setenv("RANK_LIMIT", "0")
    assert config.rank_limit() == 0


def test_a_negative_rank_limit_is_refused(monkeypatch):
    monkeypatch.setenv("RANK_LIMIT", "-1")
    with pytest.raises(config.ConfigError):
        config.rank_limit()


def test_a_rank_limit_that_is_not_a_number_is_refused(monkeypatch):
    monkeypatch.setenv("RANK_LIMIT", "twelve")
    with pytest.raises(config.ConfigError):
        config.rank_limit()


def test_settings_are_read_when_asked_for_not_when_imported(monkeypatch):
    before = config.hours_per_fte_year()
    monkeypatch.setenv("HOURS_PER_FTE_YEAR", "1000")
    assert config.hours_per_fte_year() != before
