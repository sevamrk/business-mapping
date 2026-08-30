"""Validation of a raw function map, before anything is built from it.

Two properties matter here and both cost something to get right.

**Every error is reported, not the first one.** A map is written by a person
working through a company one department at a time. Handing back one error per
run turns an afternoon's work into a week of it, so the validator walks the
whole document and collects.

**Every error carries a path and a code.** The path is where in the document to
look. The code is what the tests assert on, so that rewording a message for
clarity does not break the suite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import vocab

_SLUG = re.compile(vocab.SLUG_PATTERN)

_TOP_LEVEL = {
    "company": str,
    "description": str,
    "actors": list,
    "artifacts": list,
    "functions": list,
}

_ACTOR_FIELDS = {"id": str, "name": str, "kind": str}
_ARTIFACT_FIELDS = {"id": str, "name": str, "form": str, "boundary": str}
_FUNCTION_FIELDS = {
    "id": str,
    "name": str,
    "area": str,
    "description": str,
    "owner": (str, type(None)),
    "performers": list,
    "trigger": str,
    "inputs": list,
    "outputs": list,
    "volume_per_month": (int, float),
    "minutes_per_run": (int, float),
    "current_state": str,
    "automation": dict,
}


@dataclass(frozen=True)
class Error:
    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _type_name(expected) -> str:
    if isinstance(expected, tuple):
        names = [t.__name__ for t in expected]
        return " or ".join("null" if n == "NoneType" else n for n in names)
    return expected.__name__


def _allowed(values) -> str:
    return ", ".join(sorted(values))


class _Collector:
    def __init__(self) -> None:
        self.errors: list[Error] = []

    def add(self, code: str, path: str, message: str) -> None:
        self.errors.append(Error(code, path, message))

    def check_type(self, value, expected, path: str, code: str = "wrong_type") -> bool:
        # bool is an int in Python, and "volume_per_month": true should not pass
        # a numeric check just because of that.
        if expected in ((int, float), float) and isinstance(value, bool):
            self.add(code, path, f"expected {_type_name(expected)}, found bool")
            return False
        if not isinstance(value, expected):
            found = type(value).__name__
            self.add(code, path, f"expected {_type_name(expected)}, found {found}")
            return False
        return True

    def check_slug(self, value: str, path: str) -> None:
        if not _SLUG.match(value):
            self.add(
                "bad_id",
                path,
                f"'{value}' is not a valid id; use lowercase words joined by hyphens",
            )

    def check_enum(self, value, allowed, path: str, code: str) -> None:
        if value not in allowed:
            self.add(code, path, f"'{value}' is not one of: {_allowed(allowed)}")

    def check_keys(self, raw: dict, required: dict, optional: set, path: str) -> None:
        for key in required:
            if key not in raw:
                self.add("missing_field", f"{path}.{key}", "required field is missing")
        for key in raw:
            if key not in required and key not in optional:
                self.add("unknown_field", f"{path}.{key}", "is not part of the schema")


def validate(raw) -> list[Error]:
    """Return every problem with ``raw``. An empty list means it will load."""
    c = _Collector()

    if not isinstance(raw, dict):
        c.add("wrong_type", "$", f"the map must be an object, found {type(raw).__name__}")
        return c.errors

    c.check_keys(raw, _TOP_LEVEL, set(), "$")
    for key, expected in _TOP_LEVEL.items():
        if key in raw:
            c.check_type(raw[key], expected, f"$.{key}")

    actor_ids = _validate_collection(c, raw.get("actors"), "actors", _validate_actor)
    artifact_ids = _validate_collection(c, raw.get("artifacts"), "artifacts", _validate_artifact)
    function_ids = _validate_collection(c, raw.get("functions"), "functions", _validate_function)

    _validate_references(c, raw, actor_ids, artifact_ids)
    _validate_boundaries(c, raw, artifact_ids)

    del function_ids
    return c.errors


def _validate_collection(c: _Collector, items, name: str, each) -> set[str]:
    ids: set[str] = set()
    if not isinstance(items, list):
        return ids
    for index, item in enumerate(items):
        path = f"$.{name}[{index}]"
        if not c.check_type(item, dict, path):
            continue
        each(c, item, path)
        item_id = item.get("id")
        if isinstance(item_id, str):
            if item_id in ids:
                c.add("duplicate_id", f"{path}.id", f"'{item_id}' is already used in {name}")
            ids.add(item_id)
    return ids


def _validate_actor(c: _Collector, raw: dict, path: str) -> None:
    c.check_keys(raw, _ACTOR_FIELDS, {"notes"}, path)
    for key, expected in _ACTOR_FIELDS.items():
        if key in raw:
            c.check_type(raw[key], expected, f"{path}.{key}")
    if isinstance(raw.get("id"), str):
        c.check_slug(raw["id"], f"{path}.id")
    if isinstance(raw.get("kind"), str):
        c.check_enum(raw["kind"], vocab.ACTOR_KINDS, f"{path}.kind", "bad_enum")


def _validate_artifact(c: _Collector, raw: dict, path: str) -> None:
    c.check_keys(raw, _ARTIFACT_FIELDS, {"notes"}, path)
    for key, expected in _ARTIFACT_FIELDS.items():
        if key in raw:
            c.check_type(raw[key], expected, f"{path}.{key}")
    if isinstance(raw.get("id"), str):
        c.check_slug(raw["id"], f"{path}.id")
    if isinstance(raw.get("form"), str):
        c.check_enum(raw["form"], vocab.ARTIFACT_FORMS, f"{path}.form", "bad_enum")
    if isinstance(raw.get("boundary"), str):
        c.check_enum(raw["boundary"], vocab.ARTIFACT_BOUNDARIES, f"{path}.boundary", "bad_enum")


def _validate_function(c: _Collector, raw: dict, path: str) -> None:
    c.check_keys(raw, _FUNCTION_FIELDS, {"notes"}, path)
    for key, expected in _FUNCTION_FIELDS.items():
        if key in raw:
            c.check_type(raw[key], expected, f"{path}.{key}")

    if isinstance(raw.get("id"), str):
        c.check_slug(raw["id"], f"{path}.id")
    if isinstance(raw.get("trigger"), str):
        c.check_enum(raw["trigger"], vocab.TRIGGERS, f"{path}.trigger", "bad_enum")
    if isinstance(raw.get("current_state"), str):
        c.check_enum(
            raw["current_state"], vocab.CURRENT_STATES, f"{path}.current_state", "bad_enum"
        )

    volume = raw.get("volume_per_month")
    if isinstance(volume, (int, float)) and not isinstance(volume, bool) and volume < 0:
        c.add("out_of_range", f"{path}.volume_per_month", "must not be negative")
    minutes = raw.get("minutes_per_run")
    if isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and minutes <= 0:
        c.add("out_of_range", f"{path}.minutes_per_run", "must be greater than zero")

    for key in ("performers", "inputs", "outputs"):
        values = raw.get(key)
        if not isinstance(values, list):
            continue
        seen: set[str] = set()
        for i, value in enumerate(values):
            item_path = f"{path}.{key}[{i}]"
            if not c.check_type(value, str, item_path):
                continue
            if value in seen:
                c.add("duplicate_reference", item_path, f"'{value}' is listed twice")
            seen.add(value)

    if isinstance(raw.get("automation"), dict):
        _validate_automation(c, raw["automation"], f"{path}.automation")


def _validate_automation(c: _Collector, raw: dict, path: str) -> None:
    for name in raw:
        if name in vocab.DERIVED_FIELD_NAMES:
            c.add(
                "derived_field",
                f"{path}.{name}",
                "automatability is worked out from the seven facts below, never stated. "
                "Remove this field and let the tool draw the conclusion",
            )

    for fact in vocab.AUTOMATION_FACTS:
        if fact not in raw:
            c.add("missing_field", f"{path}.{fact}", "required field is missing")
    for name in raw:
        if name not in vocab.AUTOMATION_FACTS and name not in vocab.DERIVED_FIELD_NAMES:
            c.add("unknown_field", f"{path}.{name}", "is not part of the schema")

    for fact, allowed in vocab.FACT_VALUES.items():
        if fact not in raw:
            continue
        value = raw[fact]
        if not c.check_type(value, str, f"{path}.{fact}"):
            continue
        c.check_enum(value, allowed, f"{path}.{fact}", "bad_enum")


def _validate_references(c: _Collector, raw: dict, actors: set, artifacts: set) -> None:
    functions = raw.get("functions")
    if not isinstance(functions, list):
        return
    for index, fn in enumerate(functions):
        if not isinstance(fn, dict):
            continue
        path = f"$.functions[{index}]"
        owner = fn.get("owner")
        if isinstance(owner, str) and owner not in actors:
            c.add("unknown_actor", f"{path}.owner", f"no actor with id '{owner}'")
        for i, performer in enumerate(fn.get("performers") or []):
            if isinstance(performer, str) and performer not in actors:
                c.add(
                    "unknown_actor",
                    f"{path}.performers[{i}]",
                    f"no actor with id '{performer}'",
                )
        for key in ("inputs", "outputs"):
            for i, artifact_id in enumerate(fn.get(key) or []):
                if isinstance(artifact_id, str) and artifact_id not in artifacts:
                    c.add(
                        "unknown_artifact",
                        f"{path}.{key}[{i}]",
                        f"no artifact with id '{artifact_id}'",
                    )


def _validate_boundaries(c: _Collector, raw: dict, artifacts: set) -> None:
    """A boundary declaration is a claim, and a claim can contradict the graph.

    Saying an artifact arrives from outside the company and then naming a
    function that produces it is not a style question. One of the two is wrong,
    and the map is unusable until the author says which.
    """
    by_id = {
        a["id"]: a
        for a in (raw.get("artifacts") or [])
        if isinstance(a, dict) and isinstance(a.get("id"), str)
    }
    functions = raw.get("functions")
    if not isinstance(functions, list):
        return
    for index, fn in enumerate(functions):
        if not isinstance(fn, dict):
            continue
        path = f"$.functions[{index}]"
        for i, artifact_id in enumerate(fn.get("outputs") or []):
            artifact = by_id.get(artifact_id)
            if artifact and artifact.get("boundary") == "inbound":
                c.add(
                    "boundary_conflict",
                    f"{path}.outputs[{i}]",
                    f"'{artifact_id}' is declared inbound, so nothing inside the company "
                    "produces it",
                )
        for i, artifact_id in enumerate(fn.get("inputs") or []):
            artifact = by_id.get(artifact_id)
            if artifact and artifact.get("boundary") == "outbound":
                c.add(
                    "boundary_conflict",
                    f"{path}.inputs[{i}]",
                    f"'{artifact_id}' is declared outbound, so nothing inside the company "
                    "consumes it",
                )
