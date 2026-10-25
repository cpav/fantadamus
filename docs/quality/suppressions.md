# Suppression register

Every suppression in the repository has exactly one row here: a `# noqa`, a `# type: ignore`, a skipped
or `xfail` test, a checkov or tflint skip, a gitleaks allowlist entry, or a dependency-audit exception
(requirements R6.1–R6.7). The suppression lint (`scripts/checks/suppressions.py`) fails on a suppression
without a row, and on a row whose approval date is blank.

**Agents may propose a row but leave "Approved" blank. Only the owner fills it in.**

| ID | Path | Rule | Reason | Approved |
|---|---|---|---|---|
| S-001 | `scripts/checks/_common.py` | ruff `S603` | The shared check runner executes fixed argument lists built by the checks, never shell strings | 2026-10-24 |
| S-002 | `scripts/tools/install.py` | ruff `S310` | Downloads only HTTPS URLs from `tool-versions.toml`, and verifies each against its pinned SHA-256 before use | 2026-10-24 |
| S-003 | `tests/unit/test_repo_hygiene.py` | ruff `S603` | Runs a fixed `git check-ignore` command with test-defined paths | 2026-10-24 |
| S-004 | `tests/unit/test_repo_hygiene.py` | ruff `S607` | Resolves `git` from `PATH`, as in every developer shell and CI runner | 2026-10-24 |
| S-005 | `tests/**` | ruff `S101` | Plain `assert` is how pytest tests assert; configured in `pyproject.toml` per-file-ignores | 2026-10-24 |
| S-006 | `scripts/checks/suppressions.py` | ruff `S607` | Resolves `git` from `PATH`, as in every developer shell and CI runner | 2026-10-24 |
| S-007 | `scripts/checks/thresholds.py` | ruff `S603` | Runs fixed git subcommands with a ref chosen by the script itself | 2026-10-24 |
| S-008 | `scripts/checks/thresholds.py` | ruff `S607` | Resolves `git` from `PATH`, as in every developer shell and CI runner | 2026-10-24 |
| S-009 | `scripts/checks/run_all.py` | ruff `S603` | `make check` runs the fixed commands defined in this module | 2026-10-25 |
| S-010 | `config/audit-allowlist.toml` | audit `PYSEC-2026-3552` | cryptography 48.0.1 on the Intel Mac only; PKCS#7 decryption, unused by Fantadamus; risk accepted by the owner (option B); renewed every three months, now to 2027-01-26 | 2026-10-26 |
| S-011 | `config/audit-allowlist.toml` | audit `PYSEC-2026-3553` | cryptography 48.0.1 on the Intel Mac only; X.509 path building, unused by Fantadamus; risk accepted by the owner (option B); renewed every three months, now to 2027-01-26 | 2026-10-26 |
| S-012 | `config/audit-allowlist.toml` | audit `PYSEC-2026-3554` | cryptography 48.0.1 on the Intel Mac only; X.509 name constraints, unused by Fantadamus; risk accepted by the owner (option B); renewed every three months, now to 2027-01-26 | 2026-10-26 |
