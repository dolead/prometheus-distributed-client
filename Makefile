# Generic Makefile for Poetry-managed Python libraries
# Version: 1.0.0
#
# Usage:
#   make test              - run test suite via pytest
#   make lint              - run all linters (pycodestyle, black, flake8, pylint, mypy)
#   make build             - clean, lint, test, then build distribution
#   make release           - prompt for bump type, commit, and git tag (vX.Y.Z)
#   make publish           - build and publish to PyPI
#
# Designed to be copy-pasted into any poetry-managed Python library.
# Only .vars.mk needs to change per project — the Makefile itself is generic.

# ──────────────────────────────────────────────
# Configuration — loaded from .vars.mk
# ──────────────────────────────────────────────
# Project-specific variables (CODE, TEST_CMD, linter flags, etc.)
# are defined in .vars.mk — the only file that changes per project.

include .vars.mk

# ──────────────────────────────────────────────
# Targets
# ──────────────────────────────────────────────

.PHONY: clean test lint build publish release

clean:
	rm -rf build dist .coverage .mypy_cache .pytest_cache *.egg-info

test:
	$(TEST_CMD)

# Lint: runs all configured linters sequentially; each must pass before the next runs
lint:
	poetry check
	poetry run pycodestyle --ignore=$(PYCODESTYLE_IGNORE) $(CODE)
	poetry run black --check --verbose $(CODE)
	poetry run flake8 $(CODE)
	poetry run pylint $(CODE) -d $(PYLINT_DISABLE)
	poetry run mypy --ignore-missing-imports $(CODE)

build: clean lint test
	poetry build

# Publish: build then push to PyPI
# Can be triggered manually or by CI on tag push
publish: build
	poetry publish

# ──────────────────────────────────────────────
# Release: bump version, commit, and tag
# ──────────────────────────────────────────────
# These targets bump the version in pyproject.toml via poetry,
# commit the change, and create a git tag (vX.Y.Z).
# They do NOT push — push manually or let CI handle it.

release:
	@echo "Current version: $$(poetry version -s)"
	@printf "Bump type [patch/minor/major]: " && read BUMP && \
	case "$$BUMP" in \
		patch|minor|major) ;; \
		*) echo "Invalid bump type: $$BUMP"; exit 1 ;; \
	esac && \
	poetry version "$$BUMP" && \
	git add pyproject.toml && \
	git commit -m "release v$$(poetry version -s)" && \
	git tag "v$$(poetry version -s)" && \
	echo "Release v$$(poetry version -s) ready. Run 'git push && git push --tags' or 'make publish' to deploy."
