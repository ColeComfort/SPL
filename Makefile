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
	@echo "  make run-spl     Run SPL CLI example"
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


run-spl: 
	$(ACT) spl-rel spl/programs/teleportation.spl


clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache **/__pycache__

distclean: clean
	rm -rf $(VENV)


test-verbose: install
	$(ACT) $(PY) -m pytest -vv -s
	
