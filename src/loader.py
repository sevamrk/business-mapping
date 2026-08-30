"""Reading a map off disk: parse, validate, then build. Never two of those at once."""

from __future__ import annotations

import json
from pathlib import Path

from .model import Actor, Artifact, Automation, Function, FunctionMap
from .validate import Error, validate


class MapError(Exception):
    """The file could not become a map. Carries every reason, not the first."""

    def __init__(self, path, errors) -> None:
        self.path = path
        self.errors = list(errors)
        super().__init__(f"{path}: {len(self.errors)} problem(s)")


def load_text(text: str, path: str = "<string>") -> FunctionMap:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MapError(path, [Error("invalid_json", "$", str(exc))]) from exc
    return build(raw, path)


def load(path) -> FunctionMap:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise MapError(str(path), [Error("missing_file", "$", "no such file")]) from exc
    return load_text(text, str(path))


def build(raw, path: str = "<memory>") -> FunctionMap:
    """Validate first, and only construct once there is nothing left to report."""
    errors = validate(raw)
    if errors:
        raise MapError(path, errors)

    actors = tuple(
        Actor(a["id"], a["name"], a["kind"], a.get("notes", "")) for a in raw["actors"]
    )
    artifacts = tuple(
        Artifact(a["id"], a["name"], a["form"], a["boundary"], a.get("notes", ""))
        for a in raw["artifacts"]
    )
    functions = tuple(
        Function(
            id=f["id"],
            name=f["name"],
            area=f["area"],
            description=f["description"],
            owner=f["owner"],
            performers=tuple(f["performers"]),
            trigger=f["trigger"],
            inputs=tuple(f["inputs"]),
            outputs=tuple(f["outputs"]),
            volume_per_month=float(f["volume_per_month"]),
            minutes_per_run=float(f["minutes_per_run"]),
            current_state=f["current_state"],
            automation=Automation.from_dict(f["automation"]),
            notes=f.get("notes", ""),
        )
        for f in raw["functions"]
    )
    return FunctionMap(
        company=raw["company"],
        description=raw["description"],
        actors=actors,
        artifacts=artifacts,
        functions=functions,
    )
