# Suppression register

Every suppression in the repository has exactly one row here: a `# noqa`, a `# type: ignore`, a skipped
or `xfail` test, a checkov or tflint skip, a gitleaks allowlist entry, or a dependency-audit exception
(requirements R6.1–R6.7). The suppression lint (`scripts/checks/suppressions.py`) fails on a suppression
without a row, and on a row whose approval date is blank.

**Agents may propose a row but leave "Approved" blank. Only the owner fills it in.**

| ID | Path | Rule | Reason | Approved |
|---|---|---|---|---|
| S-001 | `scripts/checks/_common.py` | ruff `S603` | The shared check runner executes fixed argument lists built by the checks, never shell strings | |
| S-002 | `scripts/tools/install.py` | ruff `S310` | Downloads only HTTPS URLs from `tool-versions.toml`, and verifies each against its pinned SHA-256 before use | |
| S-003 | `tests/unit/test_repo_hygiene.py` | ruff `S603` | Runs a fixed `git check-ignore` command with test-defined paths | |
| S-004 | `tests/unit/test_repo_hygiene.py` | ruff `S607` | Resolves `git` from `PATH`, as in every developer shell and CI runner | |
