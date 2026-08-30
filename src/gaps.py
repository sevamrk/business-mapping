"""What the map says about itself once you stop reading it row by row.

Everything here is legal input. A function with no owner validates fine, and
that is deliberate: the point of writing the map down is to find the ones
nobody owns, and a validator that refused them would push the author into
inventing an owner to make the file load.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import graph
from .automatability import assess
from .model import FunctionMap

# An actor who is the only person able to do this many functions is a holiday
# away from being the reason nothing ships.
SOLE_PERFORMER_LIMIT = 5


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str      # high, medium, low
    subject: str
    message: str


_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def find(fmap: FunctionMap) -> list:
    findings: list = []
    findings += _unowned(fmap)
    findings += _no_performer(fmap)
    findings += _artifact_gaps(fmap)
    findings += _idle_actors(fmap)
    findings += _sole_performers(fmap)
    findings += _state_conflicts(fmap)
    findings += _loops(fmap)
    return sorted(findings, key=lambda f: (_SEVERITY_ORDER[f.severity], f.code, f.subject))


def _unowned(fmap: FunctionMap) -> list:
    return [
        Finding(
            "unowned_function",
            "high",
            fn.id,
            f"'{fn.name}' has no owner, and it is {fn.hours_per_year:.0f} hours a year of work",
        )
        for fn in fmap.functions
        if fn.owner is None
    ]


def _no_performer(fmap: FunctionMap) -> list:
    return [
        Finding(
            "no_performer",
            "medium",
            fn.id,
            f"'{fn.name}' has nobody listed as doing it",
        )
        for fn in fmap.functions
        if not fn.performers
    ]


def _artifact_gaps(fmap: FunctionMap) -> list:
    findings: list = []
    for artifact in fmap.artifacts:
        made_by = graph.producers(fmap, artifact.id)
        used_by = graph.consumers(fmap, artifact.id)
        if not made_by and not used_by:
            findings.append(
                Finding(
                    "unused_artifact",
                    "low",
                    artifact.id,
                    f"'{artifact.name}' is declared and no function touches it",
                )
            )
            continue
        if artifact.boundary == "internal" and not made_by:
            findings.append(
                Finding(
                    "unsourced_input",
                    "high",
                    artifact.id,
                    f"'{artifact.name}' is used by {len(used_by)} function(s) and nothing in "
                    "the map produces it. Either a step is missing or it arrives from outside",
                )
            )
        if artifact.boundary == "internal" and not used_by:
            findings.append(
                Finding(
                    "orphan_output",
                    "medium",
                    artifact.id,
                    f"'{artifact.name}' is produced by {len(made_by)} function(s) and nothing "
                    "reads it. Work is being done for nobody, or the reader is unmapped",
                )
            )
    return findings


def _idle_actors(fmap: FunctionMap) -> list:
    busy: set = set()
    for fn in fmap.functions:
        if fn.owner:
            busy.add(fn.owner)
        busy.update(fn.performers)
    # External actors are context rather than capacity. A carrier that performs
    # no mapped function is not a finding, it is a boundary being drawn.
    return [
        Finding(
            "idle_actor",
            "low",
            actor.id,
            f"'{actor.name}' is declared and owns or performs nothing",
        )
        for actor in fmap.actors
        if actor.id not in busy and actor.kind != "external"
    ]


def _sole_performers(fmap: FunctionMap) -> list:
    counts: dict = {}
    for fn in fmap.functions:
        if len(fn.performers) == 1:
            counts.setdefault(fn.performers[0], []).append(fn)
    findings: list = []
    for actor_id, functions in counts.items():
        if len(functions) < SOLE_PERFORMER_LIMIT:
            continue
        actor = fmap.actor(actor_id)
        if actor is not None and actor.kind == "system":
            continue
        hours = sum(fn.hours_per_year for fn in functions)
        name = actor.name if actor else actor_id
        findings.append(
            Finding(
                "single_point_of_failure",
                "medium",
                actor_id,
                f"'{name}' is the only person on {len(functions)} functions, "
                f"{hours:.0f} hours a year between them",
            )
        )
    return findings


def _state_conflicts(fmap: FunctionMap) -> list:
    """A function claimed as automated whose own facts say it cannot be.

    Usually one of two things: the automation covers a narrower job than the
    function description does, or somebody ticked a box.
    """
    findings: list = []
    for fn in fmap.functions:
        verdict = assess(fn)
        if fn.current_state == "automated" and verdict.pattern in ("keep_human", "document_first"):
            findings.append(
                Finding(
                    "state_conflicts_with_facts",
                    "high",
                    fn.id,
                    f"'{fn.name}' is recorded as automated, but its facts read as "
                    f"{verdict.pattern.replace('_', ' ')}: {verdict.reason}",
                )
            )
        if fn.current_state == "manual" and verdict.pattern == "agent_led":
            findings.append(
                Finding(
                    "ready_and_untouched",
                    "medium",
                    fn.id,
                    f"'{fn.name}' is done by hand and nothing about it is blocking: "
                    f"{verdict.recoverable_hours:.0f} hours a year",
                )
            )
    return findings


def _loops(fmap: FunctionMap) -> list:
    findings: list = []
    for loop in graph.cycles(fmap):
        findings.append(
            Finding(
                "dependency_loop",
                "low",
                loop[0],
                "these functions feed each other: " + " -> ".join([*loop, loop[0]]),
            )
        )
    return findings
