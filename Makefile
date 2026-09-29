# Every command the README mentions lives here, so the workflow is executable
# rather than only described.
.PHONY: setup test lint run validate gaps report clean

VENV ?= .venv
PY   := $(VENV)/bin/python

setup:            ## create a virtualenv and install the dev extras
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

test:             ## the whole suite. No credentials, no network
	$(PY) -m pytest -q

lint:             ## style only, and never a substitute for the tests
	$(PY) -m ruff check .

run: report       ## the most useful single command

validate:         ## check the map against the schema
	$(PY) main.py validate

gaps:             ## unowned functions, orphaned artifacts, loops
	$(PY) main.py gaps

report:           ## where the hours are and what is blocking them
	$(PY) main.py report

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache **/__pycache__ *.egg-info web/dist web/node_modules

# --- web/: the canvas. Needs Node 20.19 or newer ---------------------------------
.PHONY: web-setup web-data web-test web-lint web-run web-build

web-setup:        ## install the canvas's pinned dependencies
	cd web && npm ci

# The canvas reads this file instead of recomputing verdicts. Regenerate it after any
# change to the map or the model; CI fails if the committed copy is stale. The env vars
# are cleared so a local override cannot leak into the committed file.
web-data:         ## rewrite web/src/data/report.json from the example map
	env -u FUNCTION_MAP_PATH -u HOURS_PER_FTE_YEAR python3 main.py \
		--map examples/harbourgate-coffee.json --json report > web/src/data/report.json.tmp
	mv web/src/data/report.json.tmp web/src/data/report.json

web-test:         ## model and data tests for the canvas. No browser
	cd web && npm test

web-lint:
	cd web && npm run lint

web-run:          ## dev server on http://localhost:5173
	cd web && npm run dev

web-build:        ## static site in web/dist
	cd web && npm run build
