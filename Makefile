# Project task runner.
#
# `make test` runs the focused unit tests that guard the pure functions whose
# bugs would change reported paper numbers (recovery scoring, Cohen's kappa,
# membership-inference AUC, certificate status boundaries).
#
# Override the interpreter if the venv lives elsewhere:
#   make test PYTHON=/path/to/python
PYTHON ?= /home/salman/Desktop/venv/myenv/bin/python

.PHONY: test
test:
	$(PYTHON) -m pytest tests/ -v
