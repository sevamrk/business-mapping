"""The in-memory shape of a function map.

These are plain frozen dataclasses with no behaviour beyond lookups. Every
rule about what is allowed lives in ``validate.py``; every conclusion drawn
from a map lives in ``automatability.py`` and ``graph.py``. Keeping the three
apart is what makes the validator testable without building a map and the
scoring testable without parsing a file.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Actor:
    id: str
    name: str
    kind: str
    notes: str = ""


@dataclass(frozen=True)
class Artifact:
    id: str
    name: str
    form: str
    boundary: str
    notes: str = ""


@dataclass(frozen=True)
class Automation:
    """The seven declared facts. No conclusion, only evidence."""

    decision_type: str
    input_form: str
    interface: str
    change_rate: str
    error_cost: str
    reversibility: str
    oversight: str

    @classmethod
    def from_dict(cls, raw: dict) -> Automation:
        return cls(**{k: raw[k] for k in cls.__dataclass_fields__})


@dataclass(frozen=True)
class Function:
    id: str
    name: str
    area: str
    description: str
    owner: str | None
    performers: tuple[str, ...]
    trigger: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    volume_per_month: float
    minutes_per_run: float
    current_state: str
    automation: Automation
    notes: str = ""

    @property
    def hours_per_year(self) -> float:
        return self.volume_per_month * self.minutes_per_run * 12.0 / 60.0


@dataclass(frozen=True)
class FunctionMap:
    company: str
    description: str
    actors: tuple[Actor, ...]
    artifacts: tuple[Artifact, ...]
    functions: tuple[Function, ...]
    _actors_by_id: dict = field(default_factory=dict, repr=False, compare=False)
    _artifacts_by_id: dict = field(default_factory=dict, repr=False, compare=False)
    _functions_by_id: dict = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._actors_by_id.update({a.id: a for a in self.actors})
        self._artifacts_by_id.update({a.id: a for a in self.artifacts})
        self._functions_by_id.update({f.id: f for f in self.functions})

    def actor(self, actor_id: str) -> Actor | None:
        return self._actors_by_id.get(actor_id)

    def artifact(self, artifact_id: str) -> Artifact | None:
        return self._artifacts_by_id.get(artifact_id)

    def function(self, function_id: str) -> Function | None:
        return self._functions_by_id.get(function_id)

    @property
    def areas(self) -> tuple[str, ...]:
        seen: list[str] = []
        for fn in self.functions:
            if fn.area not in seen:
                seen.append(fn.area)
        return tuple(seen)
