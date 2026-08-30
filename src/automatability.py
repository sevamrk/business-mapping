"""Turning seven declared facts into a verdict.

The reason this module exists at all is that "how automatable is this?" is the
question everybody answers with a number they made up. A map that carries such
a number tells you what its author felt on the day they wrote it, and there is
no way to argue with it and no way to check it.

So the map never carries the number. It carries seven facts, each of which is a
question about the function that a person who does the work can answer, and
each of which somebody else can check:

    can the rule be written down          decision_type
    is the input machine-readable         input_form
    can the systems be driven             interface
    do the rules hold still               change_rate
    what does a wrong answer cost         error_cost
    can a wrong answer be undone          reversibility
    must a person look at each case       oversight

The first four say whether a machine *can*. The last three say whether it is
allowed to without a person in the loop. They are different questions with
different remedies, so they stay on separate axes and are never averaged into
one score.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import vocab
from .model import Automation, Function


@dataclass(frozen=True)
class Assessment:
    readiness: float
    axis_scores: dict[str, float]
    limiting_fact: str
    risk_level: int
    risk_band: str
    pattern: str
    reason: str
    next_step: str
    hours_per_year: float
    recoverable_hours: float

    @property
    def readiness_band(self) -> str:
        if self.readiness >= 0.75:
            return "ready"
        if self.readiness >= 0.50:
            return "partial"
        if self.readiness >= 0.25:
            return "weak"
        return "blocked"


def axis_scores(automation: Automation) -> dict[str, float]:
    return {
        fact: vocab.FACT_VALUES[fact][getattr(automation, fact)]
        for fact in vocab.CAPABILITY_FACTS
    }


# A capability fact scoring zero is not a low score, it is a stop. Averaging
# lets three good answers hide one impossible one: picking parcels off a shelf
# is deterministic, structured and stable, and no amount of that makes a robot.
BLOCKED_CEILING = 0.25


def blockers(automation: Automation) -> list:
    """Capability facts scoring zero. Any one of them caps the whole score."""
    scores = axis_scores(automation)
    return [fact for fact in vocab.CAPABILITY_FACTS if scores[fact] == 0.0]


def readiness(automation: Automation) -> float:
    """The weighted mean of the four capability facts, capped by any blocker."""
    scores = axis_scores(automation)
    total = sum(scores[fact] * vocab.READINESS_WEIGHTS[fact] for fact in scores)
    if blockers(automation):
        total = min(total, BLOCKED_CEILING)
    return round(total, 3)


def limiting_fact(automation: Automation) -> str:
    """The capability fact holding the function back. Ties break on weight."""
    scores = axis_scores(automation)
    return min(scores, key=lambda fact: (scores[fact], -vocab.READINESS_WEIGHTS[fact], fact))


def risk_level(automation: Automation) -> int:
    """The highest of the three control facts, never their average.

    An average lets a cheap, frequent mistake pull down the score of something
    irreversible, and the irreversible one is the whole reason anybody asked.
    """
    return max(
        vocab.ERROR_COSTS[automation.error_cost],
        vocab.REVERSIBILITY[automation.reversibility],
        vocab.OVERSIGHT[automation.oversight],
    )


def risk_band(automation: Automation) -> str:
    return vocab.RISK_BANDS[risk_level(automation)]


def _pattern(automation: Automation, score: float) -> tuple[str, str, str]:
    """The ladder. First match wins, so it reads top to bottom as a decision.

    Returns the pattern, why it landed there, and what to do about it.
    """
    if automation.decision_type == "discretionary":
        return (
            "keep_human",
            "nobody has written down the rule, because there isn't one",
            "leave it with a person; automate what feeds the decision instead",
        )
    if automation.oversight == "regulatory":
        return (
            "keep_human",
            "a person is required to sign each case",
            "automate the preparation, keep the signature",
        )
    if automation.input_form == "tacit":
        return (
            "document_first",
            "the input only exists in somebody's head",
            "write down what they use to decide, then look at this again",
        )
    if automation.interface == "offline":
        return (
            "instrument_first",
            "the work happens somewhere no software can reach",
            "put the step into a system, or accept that only the paperwork "
            "around it can be handed over",
        )
    if automation.interface == "ui_only":
        return (
            "instrument_first",
            "the only way in is a screen a person clicks",
            "ask the vendor for an API or a scheduled export",
        )
    if risk_level(automation) >= vocab.RISK_BANDS.index("high"):
        return (
            "agent_with_approval",
            "a wrong answer is expensive or hard to undo",
            "let an agent prepare the whole thing and have a named person release it",
        )
    if automation.change_rate == "volatile":
        return (
            "assisted",
            "the rules move faster than an automation can be kept up to date",
            "give the person a tool, not a replacement",
        )
    if score >= 0.75:
        return (
            "agent_led",
            "machine-readable input, a written rule, and a way in",
            "hand it over and sample the output",
        )
    return (
        "assisted",
        "parts of it are machine-readable and parts are not",
        "automate the machine-readable parts and leave the decision",
    )


def assess(function: Function) -> Assessment:
    """Everything the tool concludes about one function."""
    automation = function.automation
    scores = axis_scores(automation)
    score = readiness(automation)
    pattern, reason, next_step = _pattern(automation, score)

    hours = function.hours_per_year
    already = vocab.CURRENT_STATES[function.current_state]
    # A function the verdict says to leave with a person recovers nothing. Any
    # other reading of "keep_human" is the number arguing with the conclusion.
    recoverable = 0.0 if pattern == "keep_human" else round(hours * score * (1.0 - already), 1)

    return Assessment(
        readiness=score,
        axis_scores=scores,
        limiting_fact=limiting_fact(automation),
        risk_level=risk_level(automation),
        risk_band=risk_band(automation),
        pattern=pattern,
        reason=reason,
        next_step=next_step,
        hours_per_year=round(hours, 1),
        recoverable_hours=recoverable,
    )


def assess_all(functions) -> dict[str, Assessment]:
    return {fn.id: assess(fn) for fn in functions}


def rank(functions, pattern: str | None = None) -> list[tuple[Function, Assessment]]:
    """Functions worth doing something about, most hours first.

    The ordering key is recoverable hours rather than readiness, because a
    perfectly automatable job that takes twenty minutes a year is not the one
    to start with. Ties break on readiness, then on id so the output is stable.
    """
    pairs = [(fn, assess(fn)) for fn in functions]
    if pattern:
        pairs = [p for p in pairs if p[1].pattern == pattern]
    return sorted(pairs, key=lambda p: (-p[1].recoverable_hours, -p[1].readiness, p[0].id))
