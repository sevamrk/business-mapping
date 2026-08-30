"""Builders for the smallest map that will load, so each test changes one thing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.loader import build, load

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "harbourgate-coffee.json"


def automation(**overrides) -> dict:
    base = {
        "decision_type": "deterministic",
        "input_form": "structured",
        "interface": "api",
        "change_rate": "stable",
        "error_cost": "low",
        "reversibility": "reversible",
        "oversight": "none_needed",
    }
    base.update(overrides)
    return base


def function(function_id: str = "make-thing", **overrides) -> dict:
    base = {
        "id": function_id,
        "name": "Make the thing",
        "area": "operations",
        "description": "Makes the thing.",
        "owner": "alice",
        "performers": ["alice"],
        "trigger": "event",
        "inputs": [],
        "outputs": [],
        "volume_per_month": 10,
        "minutes_per_run": 6,
        "current_state": "manual",
        "automation": automation(),
    }
    base.update(overrides)
    return base


def actor(actor_id: str = "alice", **overrides) -> dict:
    base = {"id": actor_id, "name": "Alice", "kind": "role"}
    base.update(overrides)
    return base


def artifact(artifact_id: str = "thing", **overrides) -> dict:
    base = {"id": artifact_id, "name": "Thing", "form": "structured", "boundary": "internal"}
    base.update(overrides)
    return base


def raw_map(**overrides) -> dict:
    base = {
        "company": "Testing Ltd",
        "description": "A company that exists in one file.",
        "actors": [actor()],
        "artifacts": [],
        "functions": [function()],
    }
    base.update(overrides)
    return base


def built(**overrides):
    return build(raw_map(**overrides))


@pytest.fixture()
def example_map():
    return load(EXAMPLE)


@pytest.fixture()
def example_raw():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """No test inherits a setting from the shell that ran it."""
    for name in ("FUNCTION_MAP_PATH", "HOURS_PER_FTE_YEAR", "RANK_LIMIT"):
        monkeypatch.delenv(name, raising=False)
