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
	rm -rf $(VENV) .pytest_cache .ruff_cache **/__pycache__ *.egg-info
