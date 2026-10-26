# Fantadamus: every gate is a make target (quality.md). Run `make help` for the list.
# `make check` is the same locally and in CI (R1.2); the weekly audit workflow runs `make check-audit`.

SHELL := /bin/bash
.DEFAULT_GOAL := help
UV := uv run --frozen

.PHONY: help setup check check-audit test-fast task-check skeleton

help: ## List the targets
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install the locked environment, the pinned tools and the git hooks (R1.5)
	uv sync --locked
	$(UV) python -m scripts.tools.install
	$(UV) pre-commit install

check: ## Run every gate, as CI does, then print one line per check (R1.1 to R1.3, R1.6)
	@$(UV) python -m scripts.checks.run_all all

check-audit: ## Dependency vulnerability audit against the allowlist
	@$(UV) python -m scripts.checks.run_all audit

test-fast: ## Format, lint, and unit and property tests with the fast profile (R1.4)
	$(UV) ruff format --check .
	$(UV) ruff check .
	HYPOTHESIS_PROFILE=dev $(UV) pytest -m "unit or property" -p no:cacheprovider

task-check: ## Before a task: dependencies done, requirements and tests named, ADRs Accepted (TASK=<id>, R17.4)
	@$(UV) python -m scripts.checks.task_check $(TASK)

skeleton: ## Run the walking skeleton end to end and compare gold with its golden file (R16.1, R16.6)
	$(UV) fantadamus skeleton run --golden tests/golden/skeleton/role_counts.json
