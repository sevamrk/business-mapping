# business-mapping

[![tests](https://github.com/sevamrk/business-mapping/actions/workflows/ci.yml/badge.svg)](https://github.com/sevamrk/business-mapping/actions/workflows/ci.yml)

A format for writing down every function a company performs, and a tool that reads it and says
which of those functions an agent could drive today, which are blocked, and what is blocking
them.

> **In 30 seconds**
>
> | | |
> |---|---|
> | **What it does** | Turns a description of a company into a ranked answer to "what can we automate, and what has to change first" |
> | **The hard part** | Automatability is the field everyone fills in with a number they made up. There's no way to check it and no way to argue with it |
> | **The approach** | The map never states automatability. It states seven facts about each function, each one checkable, and the tool derives the verdict |
> | **What it admits** | The hours rest on volume estimates a person typed in, and the model can't tell "no software yet" from "it's physical work" |

```
$ python3 main.py report

Harbourgate Coffee Roasters
50 functions, 24 actors, 67 artifacts, 8 areas
11,004 hours a year of mapped work, of which 1,803 already runs without a person

What could be handed over
pattern              functions  hrs/yr  recoverable
-------------------  ---------  ------  -----------
agent_led                   12   1,417          928
agent_with_approval          8     824          526
assisted                     4   1,432          582
instrument_first            16   5,716        1,967
document_first               1     180           45
keep_human                   9   1,435            0
```

## The problem

Everybody who has tried to automate part of a company has met the same list. Someone puts
together a spreadsheet of processes with a column called "automation potential", scored high,
medium and low. The scores are guesses. Nobody can check them, nobody can argue with them
without arguing about somebody's judgement, and six months later nothing on the list has moved
because the high-scoring rows turned out to need an API that doesn't exist.

The scores are the wrong artifact. Write down the evidence instead, and the score falls out of
it where anybody can see where it came from.

## The interesting decision

**The map never carries an automatability score. It carries seven facts, and every one of them
is a question somebody who does the work can answer and somebody else can check.**

Four are about whether a machine *can* do it: is the rule written down, is the input
machine-readable, can the systems be driven by anything other than a person, do the rules hold
still. Three are about whether it's *allowed* to run without supervision: what a wrong answer
costs, whether it can be undone, and how much a person has to look.

Those are different questions with different remedies, so they stay on separate axes and are
never averaged into one number. Then two rules do most of the work:

**A zero on any capability axis caps the whole score at 0.25.** Picking parcels off a shelf is
deterministic, structured and stable. Three good answers out of four, and a weighted average
calls it 0.75 ready. It happens in a room, with hands. An average lets three good answers hide
one impossible one, so a zero is a stop rather than a low score, and the tool names the axis
that stopped it.

**Risk is the highest of the three control facts, never their average.** An irreversible action
next to two harmless ones is an irreversible action. In the example map the supplier payment run
scores a perfect 1.00 on readiness. Every fact about it is machine-readable. It comes back as
`agent_with_approval` and it always will, because the money doesn't come back.

The output isn't a score, it's one of six patterns, and each carries the next thing to do:
`agent_led`, `agent_with_approval`, `assisted`, `instrument_first`, `document_first`,
`keep_human`. That's the part that makes the map worth writing. "0.6 automatable" tells you
nothing. "The only way into that system is a screen a person clicks, so ask the vendor for an
export before you plan anything else" is a task.

Writing the conclusion into the file is refused by name, not as an unknown key:

```
$.functions[3].automation.automatability: automatability is worked out from the seven facts
below, never stated. Remove this field and let the tool draw the conclusion
```

## Quickstart

No dependencies to run it. Python 3.10 or newer, and pytest only if you want the tests.

```bash
git clone https://github.com/sevamrk/business-mapping.git
cd business-mapping

python3 main.py validate     # check the map against the schema
python3 main.py report       # where the hours are and what blocks them
python3 main.py rank         # what to do first, most hours first
python3 main.py gaps         # unowned work, orphaned artifacts, loops
python3 main.py trace sales-invoice
```

Or `make setup && make test` for a virtualenv with pytest and ruff in it.

Every command takes `--json`, because the point of the format is that something other than a
person can act on it.

## How it works

Three files describe the shape and one derives from it.

`SCHEMA.md` is the spec: what a function record holds, what every vocabulary means, and how the
verdict is worked out. Read that before writing a map. `src/vocab.py` is the same vocabularies
in code, and it's the only place any of them are written down. A test parses `SCHEMA.md` and
fails if the two have drifted apart, so a level added in one place and not the other is a red
suite rather than a surprise.

`src/validate.py` checks a document and returns **every** problem with a path and a code, not
the first one it hit. A map is written by somebody working through a company one department at
a time, and handing them one error per run turns an afternoon into a fortnight.

Inputs and outputs are artifact ids rather than prose, which is what buys the graph. Once
they're ids, "where does this number come from" stops being a question you ask a colleague:

```
$ python3 main.py trace sales-invoice --depth 4

Sales invoice (sales-invoice) is produced by:
  fn Issue wholesale invoices  [Finance Manager]
    <- Delivery confirmation
      fn Drive the wholesale round  [Operations Director]
        <- Delivery route   (goes further, raise --depth)
        <- Finished goods stock   (goes further, raise --depth)
    <- Wholesale price list
      fn Reissue the wholesale price list  [Head of Wholesale]
        <- Green coffee contract   (goes further, raise --depth)
```

`gaps` reads the same graph for things that are legal to write down and worth someone's
attention: functions nobody owns, artifacts that are consumed but never produced, work that
produces something nobody reads, one person who is the only one able to do five things, and
loops. A function with no owner validates fine, deliberately. The point of writing the map down
is to find them, and a schema that refused would push you into inventing an owner to make the
file load.

## The worked example

`examples/harbourgate-coffee.json` is Harbourgate Coffee Roasters: an invented specialty coffee
roaster, sixty-odd people, one roastery, about a hundred and eighty wholesale cafes, a webshop
with a subscription. 50 functions across 8 areas, 24 actors, 67 artifacts. No real company, and
none of the numbers are anybody's.

It's the example rather than a demo because of what it argues with. The largest single number on
the page is 1,760 hours a year of picking and packing webshop orders, and the model has to not
call that an automation opportunity. The VAT return is deterministic, structured and stable, and
a person still signs it. Production cupping comes back as `document_first`, because the thing
stopping it isn't the tasting, it's that the standard being tasted against has never been
written down.

The map is not clean, on purpose. A clean example would prove the checks compile and nothing
else, so it carries real problems: an onboarding process nobody owns, a packaging stock level the
reorder job depends on that nothing in the map produces, account call notes that get written
and never read, a bookkeeper who is the only person on five jobs, and four dependency loops. `gaps` finds
19 things. `tests/test_example.py` asserts each check fires on it, so the example can't quietly
stop exercising the tool.

## The canvas in `web/`

A React front end that lets you walk the example map instead of reading it as text. It
opens on the company, and each click goes one level down: company, area, function. Two
extra views sit beside the areas. **Unlocks** groups every function by the one thing
standing between it and an agent, with the most hours behind it first. **Findings** holds
the 19 things `gaps` reports, and each one links to the functions it names.

```bash
make web-setup     # npm ci in web/. Node 20.19 or newer
make web-run       # http://localhost:5173
make web-test      # the model and data tests, no browser
make web-build     # a static site in web/dist
```

**The canvas does not work anything out.** Patterns, readiness, risk, recoverable hours and
findings come from `python3 main.py --json report`, saved as `web/src/data/report.json`. The
map itself is read in place from `examples/`. A second implementation of the ladder in
JavaScript would drift from the tested Python one sooner or later, and a canvas showing a
different verdict from the CLI is worse than no canvas. So the canvas refuses a report that
doesn't match the map (a function missing on either side, hours that no longer agree, or a
finding about something the map no longer has),
and CI regenerates the report and fails if the committed copy is stale. After changing the
map, run `make web-data`.

What you can do on it: drill in and out, with a breadcrumb and a back button that remembers
jumps. Switch between a force layout, where you can drag nodes, and a layered one from ELK
that shows the flow left to right. Hover a node to trace its links. Search by function,
person or artifact. Filter functions by verdict. A function's panel shows its four
capability scores with the limiting one marked, why it got its verdict, the next step, and
which function each of its inputs comes from, clickable. Dashed arrows between functions
are artifacts one hands to another.

| What's weaker here | The detail |
|---|---|
| **It shows one map, fixed at build time** | The map and report are bundled into the site. There is no file picker and no upload, so pointing it at your own map means `make web-data` and a rebuild |
| **The tests cover the model, not the screen** | 50 vitest tests pin how the tree, the unlocks ranking, the findings and the search are built. Nothing tests the rendered page in CI. It was checked by driving a headless browser through every view, which is a manual step |
| **It is a desktop tool** | Below about 760px the sidebar stacks above the canvas and everything still works, but a tier of eight function cards is not readable on a phone, and touch input has not been tried |
| **Unlocks ranks by hours behind the blocker, not hours it would free** | The report says how many hours sit behind "the only way in is a screen". It does not say how many would become recoverable once there is an API, because that needs the model rerun with the fact changed. The ranking is a proxy |
| **ELK is most of the download** | The base bundle is about 130 kB gzipped. The layered layout adds about 440 kB, loaded only the first time someone picks Tree |

## Make it yours

1. Copy `examples/harbourgate-coffee.json`, empty the three lists, and point
   `FUNCTION_MAP_PATH` at it.
2. Write the actors first, then the artifacts, then the functions. Ids are the only thing tying
   them together, so getting the nouns settled early saves the most time.
3. Do one department, run `validate`, then run `gaps`. It'll tell you what you left out faster
   than reading it back will.
4. Set `HOURS_PER_FTE_YEAR` to whatever number your finance people already use, or the headcount
   figure will start an argument about the wrong thing.
5. If you disagree with the model, the numbers are in `src/vocab.py` and the ladder is one
   function in `src/automatability.py`. Change them and re-run. That's the reason they're not
   buried.

## Tests

```bash
make test        # or: python3 -m pytest -q
```

330 tests, no credentials, no network, about a second. The ones worth reading are
`tests/test_automatability.py`, which walks the ladder case by case and pins the two rules the
whole model rests on, and `tests/test_validate.py`, which has one test per way a map can be
rejected. `tests/test_example.py` holds the shipped example to being varied rather than just
valid: every level of every vocabulary has to appear in it, and every one of the six patterns
has to be reached by something.

## Layout

| Path | Does |
|---|---|
| `SCHEMA.md` | The spec. The artifact worth reading first |
| `src/vocab.py` | Every vocabulary and the score each level carries. Nothing else hardcodes one |
| `src/validate.py` | Structure, enums, references, boundaries. Collects, never stops at the first |
| `src/automatability.py` | Seven facts to a readiness score, a risk band, and a pattern |
| `src/graph.py` | Producers, consumers, tracing, and loop detection |
| `src/gaps.py` | Legal input that somebody should look at |
| `src/report.py` | Text and JSON, from the same numbers |
| `src/cli.py` | Five commands and three exit codes |
| `examples/harbourgate-coffee.json` | The invented company |
| `web/src/model.js` | The canvas's node tree, built from the map and the report. No React, so vitest runs it in Node |
| `web/src/App.jsx` | The canvas: layouts, navigation, panels |
| `web/src/data/report.json` | `main.py --json report`, generated by `make web-data`. Never edited by hand |

## Limits

| What's weaker here | The detail |
|---|---|
| **It can't tell "no software" from "no software possible"** | `interface: offline` means nothing can drive it, and the tool says `instrument_first`. For a spreadsheet nobody has exported that's the right advice. For packing boxes by hand it isn't, and the map has no way to say which. Splitting the fact into a medium (digital, physical, in person) is the first change I'd make |
| **The hours are estimates and the tool prints them to the hour** | Every figure comes from `volume_per_month` times `minutes_per_run`, both typed in by a person. The ordering survives bad estimates. The totals shouldn't be quoted at anybody |
| **The weights are argued for, not measured** | The four readiness weights and the level scores in `src/vocab.py` are a considered opinion about what makes work machine-executable, not a finding from data. They're in one file with one number each so they can be argued with, which is the most I can honestly claim for them |
| **JSON is the wrong format for the people who know the answers** | The people who can tell you what a function actually does are not going to edit JSON. A spreadsheet or a form that emits this format is the missing half, and it's missing |
| **Nothing checks the map against reality** | A map says what somebody believed on the day they wrote it. There's no drift detection, no sampling against system logs, no expiry. A year-old map that still validates is still wrong |

## Provenance

The idea is mine, from consulting work mapping company functions so that agents and automations
could drive them. **Nothing was extracted.** No code, no data and no documents from that work are
here or in this repository's history. The schema, the tool and the example company were written
from scratch against an invented business, and the client-facing material stayed where it was.

The canvas in `web/` is the one exception, and only for code. Its layout, navigation and
node components started as a private front end I built for that consulting work, and were
rewritten here against this format. No data, names, figures or screenshots came with them:
everything it shows is the invented company above.
