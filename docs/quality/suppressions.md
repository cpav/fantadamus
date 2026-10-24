# Suppression register

Every suppression in the repository has exactly one row here: a `# noqa`, a `# type: ignore`, a skipped
or `xfail` test, a checkov or tflint skip, a gitleaks allowlist entry, or a dependency-audit exception
(requirements R6.1–R6.7). The suppression lint (`scripts/checks/suppressions.py`) fails on a suppression
without a row, and on a row whose approval date is blank.

**Agents may propose a row but leave "Approved" blank. Only the owner fills it in.**

| ID | Path | Rule | Reason | Approved |
|---|---|---|---|---|
