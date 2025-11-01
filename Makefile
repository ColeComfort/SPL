PY ?= python3

# Simple workflow
.PHONY: help venv install dev test test-spl test-splpp run-spl run-splpp clean

help:
	@echo "make venv       # create venv .venv"
	@echo "make install    # pip install -e ."
	@echo "make dev        # install dev deps"
	@echo "make test       # run all tests"
	@echo "make test-spl   # run SPL tests"
	@echo "make test-splpp # run SPL++ tests"
	@echo "make run-spl    # run CLI on example SPL"
	@echo "make run-splpp  # run CLI on example SPL++"
	@echo "make clean      # remove build and cache"

venv:
	$(PY) -m venv .venv
	. .venv/bin/activate && $(PY) -m pip install --upgrade pip

install:
	. .venv/bin/activate && $(PY) -m pip install -e .

dev: install
	. .venv/bin/activate && $(PY) -m pip install pytest

test:
	. .venv/bin/activate && $(PY) -m pytest -q spl/tests splpp/tests

test-spl:
	. .venv/bin/activate && $(PY) -m pytest -q spl/tests

test-splpp:
	. .venv/bin/activate && $(PY) -m pytest -q splpp/tests

run-spl:
	. .venv/bin/activate && spl-rel spl/programs/5_1_3.spl

run-splpp:
	. .venv/bin/activate && splpp-rel splpp/programs/teleportation.spl++ --fn main

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache **/__pycache__
