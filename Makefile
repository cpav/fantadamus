# Fantadamus: every gate is a make target (quality.md). Run `make help` for the list.
# `make check` is the same locally and in CI; CI runs check-static, check-tests, check-infra and
# check-audit as parallel jobs, whose union is exactly `make check` (R1.2).

SHELL := /bin/bash
.DEFAULT_GOAL := help
UV := uv run --frozen

.PHONY: help setup check check-static check-tests check-infra check-audit test-fast task-check skeleton mutation

help: ## List the targets
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install the locked environment, the pinned tools and the git hooks (R1.5)
	uv sync --locked
	$(UV) python -m scripts.tools.install
	$(UV) pre-commit install

check: ## Run every gate, as CI does, then print one line per check (R1.1 to R1.3, R1.6)
	@$(UV) python -m scripts.checks.run_all all

check-static: ## Lockfile, tools, format, lint, types, docs, suppressions, thresholds, ADRs, identities, secrets
	@$(UV) python -m scripts.checks.run_all static

check-tests: ## Every test layer with coverage, then the coverage gate
	@$(UV) python -m scripts.checks.run_all tests

check-infra: ## Infrastructure checks (Terraform and the IAM policy evaluator, from task 11)
	@$(UV) python -m scripts.checks.run_all infra

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

mutation: ## Mutation testing on the core modules, for phase gates only (R1.7)
	$(UV) mutmut run
