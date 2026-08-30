"""Every closed vocabulary the schema uses, in one place.

Nothing else in the codebase writes an enum value as a literal. A map is
validated against these dictionaries, the readiness score is computed from the
numbers in them, and ``tests/test_docs.py`` checks that ``SCHEMA.md`` documents
every key. Adding a level anywhere means adding it here and nowhere else.

The scores attached to the four capability facts are the opinionated part of
this file. They are the answer to "how much closer to machine-executable does
this level put the function", on a 0 to 1 scale, and they are visible here
rather than buried in the scoring function so that someone who disagrees can
change one number and re-run.
"""

from __future__ import annotations

# --- What an actor is -------------------------------------------------------
ACTOR_KINDS = ("role", "team", "system", "external")

# --- What an artifact is ----------------------------------------------------
# The form of an artifact is the same vocabulary as a function's input form,
# because an artifact is exactly what a downstream function receives.
ARTIFACT_FORMS = ("structured", "semi_structured", "unstructured", "tacit")

# Where an artifact sits relative to the company boundary. This is what makes
# "nothing produces this input" a real finding instead of noise: an inbound
# artifact is supposed to have no producer.
ARTIFACT_BOUNDARIES = ("internal", "inbound", "outbound")

# --- How a function starts --------------------------------------------------
TRIGGERS = ("schedule", "event", "request", "continuous")

# --- How much of it is automated today --------------------------------------
# The fraction is how much of the function's time a machine already takes.
CURRENT_STATES = {"manual": 0.0, "assisted": 0.5, "automated": 1.0}

# --- The four capability facts, and what each level scores ------------------
# Can the rule be written down?
DECISION_TYPES = {
    "deterministic": 1.0,   # the rule is written down and has no exceptions
    "judgement": 0.6,       # a rule exists, applying it needs interpretation
    "discretionary": 0.1,   # no rule; a person weighs it each time
}

# Is the input in a form a machine can read?
INPUT_FORMS = {
    "structured": 1.0,      # fields, rows, an API response
    "semi_structured": 0.7, # documents with a stable shape: invoices, forms
    "unstructured": 0.4,    # free text, email threads, a phone call
    "tacit": 0.0,           # it is in somebody's head and written nowhere
}

# Can the systems it touches be driven by something other than a person?
INTERFACES = {
    "api": 1.0,
    "bulk_export": 0.7,     # a file drop or a scheduled export, no live calls
    "ui_only": 0.3,         # a screen a human clicks, and nothing else
    "offline": 0.0,         # paper, a phone call, a room
}

# How often the rules of the function change.
CHANGE_RATES = {
    "stable": 1.0,          # the same as last year
    "periodic": 0.7,        # revised on a season or a quarter
    "volatile": 0.3,        # changes faster than anyone can re-specify it
}

# The weights are deliberately close together. No single fact decides on its
# own; the ladder in automatability.py handles the cases where one fact should
# override the average.
READINESS_WEIGHTS = {
    "decision_type": 0.30,
    "input_form": 0.25,
    "interface": 0.25,
    "change_rate": 0.20,
}

CAPABILITY_FACTS = ("decision_type", "input_form", "interface", "change_rate")

# --- The three control facts, and the level each level carries --------------
# These are combined with max(), not an average. Averaging risk lets a cheap
# mistake cancel out an irreversible one, which is exactly the situation the
# whole exercise is supposed to catch.
ERROR_COSTS = {"low": 0, "moderate": 1, "high": 2, "severe": 3}
REVERSIBILITY = {"reversible": 0, "costly_to_reverse": 2, "irreversible": 3}
OVERSIGHT = {"none_needed": 0, "sampled": 1, "every_case": 2, "regulatory": 3}

RISK_BANDS = ("low", "moderate", "high", "critical")

CONTROL_FACTS = ("error_cost", "reversibility", "oversight")

# Every key an ``automation`` block must carry, and may not exceed.
AUTOMATION_FACTS = CAPABILITY_FACTS + CONTROL_FACTS

FACT_VALUES = {
    "decision_type": DECISION_TYPES,
    "input_form": INPUT_FORMS,
    "interface": INTERFACES,
    "change_rate": CHANGE_RATES,
    "error_cost": ERROR_COSTS,
    "reversibility": REVERSIBILITY,
    "oversight": OVERSIGHT,
}

# --- What the tool concludes ------------------------------------------------
# Not part of the input. A map that states one of these is rejected.
PATTERNS = (
    "agent_led",
    "agent_with_approval",
    "assisted",
    "instrument_first",
    "document_first",
    "keep_human",
)

# Names a well-meaning author reaches for when they want to write the answer
# down instead of the evidence. Rejected by name so the error can explain why
# rather than saying "unknown key".
DERIVED_FIELD_NAMES = (
    "automatability",
    "automatable",
    "automation_score",
    "readiness",
    "score",
    "pattern",
    "priority",
    "risk",
    "risk_band",
)

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
