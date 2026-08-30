# The function map format

A function map is one JSON document describing what a company does. It has three lists in it:
the people and systems that do the work (`actors`), the things the work moves around
(`artifacts`), and the work itself (`functions`).

The format exists to answer one question that spreadsheets of processes never answer: which of
these could an agent actually drive, and what has to change first for the rest. So the schema
asks about evidence rather than about conclusions, and the tool draws the conclusion.

Everything below is enforced by `src/validate.py`. The vocabularies live in `src/vocab.py` and
nowhere else.

## The document

```json
{
  "company": "Harbourgate Coffee Roasters",
  "description": "One paragraph. What the company is, and what this map covers.",
  "actors": [],
  "artifacts": [],
  "functions": []
}
```

| Field | |
|---|---|
| `company` | The name at the top of the report |
| `description` | What the company is, and what this map covers |
| `actors` | Who and what does the work |
| `artifacts` | What the work moves around |
| `functions` | The work |

All five keys are required. Anything else at the top level is an error, because a key the tool
ignores is a key that quietly does nothing.

Ids everywhere are lowercase words joined by hyphens: `green-intake`, `sales-invoice`. They are
the only thing that ties the three lists together, so they have to be typed the same way twice.

## Actors

Who or what does the work.

```json
{ "id": "bookkeeper", "name": "Bookkeeper", "kind": "role", "notes": "Part time, three days" }
```

| Field | |
|---|---|
| `id` | Unique among actors |
| `name` | What people call them |
| `kind` | One of the four below |
| `notes` | Optional, free text |

| `kind` | Means |
|---|---|
| `role` | One named job, whoever holds it |
| `team` | A group doing the same work |
| `system` | Software that performs a function without a person |
| `external` | Someone outside the company: a carrier, a supplier, a customer |

Naming a `system` as a performer is how a map says "this already runs on its own". An `external`
actor is context, not capacity, and the gap checks treat it that way.

## Artifacts

The things functions consume and produce. Anything with an id can be traced.

```json
{ "id": "sales-invoice", "name": "Sales invoice", "form": "structured", "boundary": "internal" }
```

| `form` | Means |
|---|---|
| `structured` | Fields and rows. A machine can read it today |
| `semi_structured` | A document with a stable shape: an invoice, a form, a delivery note |
| `unstructured` | Free text, an email thread, a phone call |
| `tacit` | Not written down anywhere. It is in somebody's head |

| `boundary` | Means |
|---|---|
| `internal` | Produced and consumed inside the map |
| `inbound` | Arrives from outside the map |
| `outbound` | Leaves the map |

The boundary is relative to the map, not to the company, and that matters. Every real map is
partial. Declaring an artifact `inbound` is how you say "I know nothing here produces this, and
that is on purpose", which is what stops the gap report drowning in false alarms. It is also a
claim the validator checks: if a function produces something declared `inbound`, one of the two
is wrong and the map will not load until you say which.

## Functions

The unit of work. One function is one thing the company does, repeatedly, that somebody could
be handed.

```json
{
  "id": "payment-matching",
  "name": "Match payments to invoices",
  "area": "finance",
  "description": "Work out which invoice each incoming payment is for.",
  "owner": "finance-manager",
  "performers": ["bookkeeper"],
  "trigger": "schedule",
  "inputs": ["bank-statement", "sales-invoice"],
  "outputs": ["payment-allocation"],
  "volume_per_month": 400,
  "minutes_per_run": 2,
  "current_state": "manual",
  "automation": { }
}
```

| Field | |
|---|---|
| `id` | Unique among functions |
| `name` | A verb phrase. What gets done |
| `area` | Free text grouping. Departments, usually |
| `description` | One or two sentences, in the words the people doing it would use |
| `owner` | Actor id, or `null`. Who is accountable |
| `performers` | Actor ids. Who or what actually does it |
| `trigger` | `schedule`, `event`, `request`, or `continuous` |
| `inputs` | Artifact ids it needs |
| `outputs` | Artifact ids it produces |
| `volume_per_month` | How many times a month |
| `minutes_per_run` | How long one run takes |
| `current_state` | `manual`, `assisted`, or `automated` today |
| `automation` | The seven facts, below |
| `notes` | Optional |

`owner` may be `null` and `performers` may be empty. That is deliberate. The point of writing
the map down is to find the work nobody owns, and a schema that refused it would push you into
inventing an owner to make the file load. Both show up in `gaps` instead.

`volume_per_month` times `minutes_per_run` is where every hours figure in the tool comes from.
They are estimates and the output is only ever as good as they are.

## The automation block

Seven facts. Each one is a question somebody who does the work can answer, and somebody else can
check. None of them is an opinion about whether the function should be automated.

### Can a machine do it

**`decision_type`**, the rule.

| | |
|---|---|
| `deterministic` | The rule is written down and has no exceptions |
| `judgement` | A rule exists, but applying it needs interpretation |
| `discretionary` | There is no rule. A person weighs it each time |

**`input_form`**, what arrives. Same vocabulary as an artifact's `form`: `structured`,
`semi_structured`, `unstructured`, `tacit`. Take the worst of the inputs, not the average.

**`interface`**, whether the systems can be driven by anything other than a person.

| | |
|---|---|
| `api` | Something can call it |
| `bulk_export` | A file drop or a scheduled export. No live calls |
| `ui_only` | A screen a person clicks, and nothing else |
| `offline` | Paper, a phone call, or a pair of hands |

**`change_rate`**, whether the rules hold still: `stable`, `periodic`, `volatile`. An automation
of something rewritten every fortnight spends more time being maintained than it saves.

### Is it allowed to run on its own

**`error_cost`**: `low`, `moderate`, `high`, `severe`. What one wrong answer costs.

**`reversibility`**: `reversible`, `costly_to_reverse`, `irreversible`. Whether you can take it
back once it has gone out.

**`oversight`**: `none_needed`, `sampled`, `every_case`, `regulatory`. How much a person has to
look, where `regulatory` means a named human signature is legally required.

## What the tool works out

None of this goes in the file. Writing any of it is an error, and the validator says so by name
rather than reporting an unknown key, because `"automatability": 0.8` is a mistake worth
explaining.

**Readiness**, 0 to 1, is the weighted mean of the four capability facts. The weights are in
`vocab.READINESS_WEIGHTS` and they are close together on purpose, so no single fact swings it.

There is one exception, and it is the most important rule in the model. **A capability fact
scoring zero caps the whole readiness at 0.25.** Picking parcels off a shelf is deterministic,
structured and stable: three good answers out of four, and an average would call it 0.75 ready.
It happens in a room, with hands. Averaging lets three good answers hide one impossible one, so
a zero is treated as a stop rather than a low score, and the tool names the axis.

**Risk** is the highest of the three control facts, never their average. An irreversible action
next to two harmless ones is an irreversible action, and averaging is exactly how that gets
lost.

**Pattern** is a ladder, checked in order. First match wins.

| Order | If | Pattern |
|---|---|---|
| 1 | `decision_type` is `discretionary` | `keep_human` |
| 2 | `oversight` is `regulatory` | `keep_human` |
| 3 | `input_form` is `tacit` | `document_first` |
| 4 | `interface` is `offline` | `instrument_first` |
| 5 | `interface` is `ui_only` | `instrument_first` |
| 6 | risk is `high` or `critical` | `agent_with_approval` |
| 7 | `change_rate` is `volatile` | `assisted` |
| 8 | readiness is 0.75 or better | `agent_led` |
| 9 | otherwise | `assisted` |

The capability questions are asked before the control questions, and that ordering is a choice
worth arguing with. It means a screen-only system with a severe error cost comes back as
`instrument_first` rather than `agent_with_approval`. The reasoning is that a conversation about
who approves a thing nobody can do yet is a wasted conversation. Get the interface first, then
have the argument about the release.

The six patterns:

| | |
|---|---|
| `agent_led` | Hand it over. Sample the output |
| `agent_with_approval` | The agent prepares all of it, a named person releases it |
| `assisted` | The agent does part. The person keeps the decision |
| `instrument_first` | Ready in every way except that nothing can drive the system |
| `document_first` | The inputs or the rules are not written down anywhere |
| `keep_human` | Discretionary judgement, or a signature the law requires |

**Recoverable hours** is annual hours times readiness times the share not already automated, and
zero for anything the verdict leaves with a person. It is a rough number resting on the volumes
in the map, and it should be read as an ordering rather than a budget.

## Extending it

Add a level to a vocabulary in `src/vocab.py`, give it a score, and document it here. The tests
check that this file mentions every value the code knows, so a level added in one place and not
the other fails the suite rather than shipping.
