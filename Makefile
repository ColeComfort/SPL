# Makefile for SPL / SPL++
# Usage variables
PY ?= python3
PIP ?= $(PY) -m pip

# Virtualenv
VENV = .venv
ACT = . $(VENV)/bin/activate &&

.PHONY: help venv install dev test test-spl test-splpp run-spl run-splpp clean distclean

help:
	@echo "Targets:"
	@echo "  make venv        Create venv in $(VENV)"
	@echo "  make install     Editable install into venv"
	@echo "  make dev         Install dev deps"
	@echo "  make test        Run all tests"
	@echo "  make test-spl    Run SPL tests"
	@echo "  make test-splpp  Run SPL++ tests"
	@echo "  make run-spl     Run SPL CLI example"
	@echo "  make run-splpp   Run SPL++ CLI example (assertions in main)"
	@echo "  make clean       Remove caches"
	@echo "  make distclean   Remove venv + caches"

$(VENV)/bin/python:
	$(PY) -m venv $(VENV)
	$(ACT) $(PIP) install -U pip setuptools wheel

venv: $(VENV)/bin/python

install: venv
	$(ACT) $(PIP) install -e .

dev: install
	$(ACT) $(PIP) install -U pytest

test: test-spl test-splpp

test-spl: 
	$(ACT) $(PY) -m pytest -q spl/tests

test-splpp: 
	$(ACT) $(PY) -m pytest -q splpp/tests

run-spl: 
	$(ACT) spl-rel spl/programs/teleportation.spl

# Note: splpp-rel now runs run_assertions_via_spl when --fn main, so this works.
run-splpp: 
	$(ACT) splpp-rel splpp/programs/teleportation.spl++ --fn main

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache **/__pycache__

distclean: clean
	rm -rf $(VENV)


test-verbose: install
	$(ACT) $(PY) -m pytest -vv -s
	
	
	
run-splpp-test: 
	$(ACT) splpp-rel splpp/programs/test.spl++ --fn main
