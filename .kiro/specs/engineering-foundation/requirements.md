# Requirements Document: `engineering-foundation` (Spec 0)

Status: **Draft for owner review** · Workflow: Feature Spec, Requirements-First · Last updated: 2026-10-24

## Introduction

Spec 0 builds the repository and everything that keeps it honest: the Python project, format, lint and type
checks, the test harness, pre-commit hooks, one `make check` command shared by local runs and CI, a GitHub
Actions pipeline, branch protection, an infrastructure skeleton with the AWS Budgets alarm, Kiro hooks, the
ADRs for the tool choices, and a **walking skeleton**: a three-row fixture carried through
bronze → silver → gold on DuckDB.

The only pipeline code in Spec 0 is the walking skeleton. Its purpose is to prove that every layer of the
harness (unit, property, integration, golden file, coverage, infrastructure) works end to end before
Spec 1 adds real sources.

Spec 0 is done when its acceptance tests pass, including the gate self-tests that prove each gate
**blocks a bad change** (Phase 0 exit gate, `quality.md`). Because nothing is pushed to GitHub until the
owner says so (Q8), the exit gate has two parts:

- the **local gate**: every acceptance test, or part of one, that `make check`, pre-commit and the pre-push
  hook can prove on the owner's machine;
- the **remote gate**: the parts that need GitHub (branch protection, CI, push protection, Dependabot),
  run after the owner's **remote go-ahead** (R2.11).

## Change log

| Date | Change |
|---|---|
| 2026-10-17 | First draft. |
| 2026-10-17 | Public repository (Q1): R2.9, R2.10, R10.7, R12.8, R12.9. Reuse of the owner's gamegusto project: R22, R14.12, the budget in the bootstrap module (R15), deploy credentials (R19.3). Owner decisions Q2–Q9. |
| 2026-10-24 | Agent hooks shared by Claude Code and Kiro (R17 rewritten, Q5). The method arrives as `docs/method.md` (Q6). The MVP's collector mode (ADR-0005) shapes the walking skeleton. |
| 2026-10-24 | Analyze Requirements review ([analysis-2026-10-24.md](analysis-2026-10-24.md)): all 30 findings applied. New criteria R1.8, R1.9, R2.11, R2.12, R6.7, R9.6, R10.8, R14.13, R15.7, R16.10–R16.13, R19.6, R20.5, R22.12; acceptance tests split into local and remote gates; AT-19 to AT-21 added. |

## Glossary

| Term | Definition |
|---|---|
| THE SYSTEM | The `fantadamus` repository together with its local tooling (`make`, pre-commit), its GitHub settings, its CI workflows and its infrastructure code. |
| Owner | The project owner, who approves specs, ADRs, suppressions, paid services and deploys. |
| Check | One row of the `make check` table in `quality.md` (format, lint, types, tests, coverage, …). |
| Required check | A CI job that branch protection requires to pass before a merge into `main`. |
| PR gate | All required checks for one pull request, measured in wall-clock time from the first job starting to the last job finishing. |
| Suppression | Any mechanism that silences a finding: `# noqa`, `# type: ignore`, a cdk-nag or checkov suppression, a gitleaks allowlist entry, a `pip-audit` ignore, `pytest.mark.skip` or `xfail`. |
| Gate threshold | A configured number that a check enforces, each with a **safe direction**: the coverage minima and the Hypothesis `ci` profile's example count may only go up; the CI time budget may only go down. Moving one the other way **weakens** it. |
| Local gate, remote gate | The two parts of the Phase 0 exit gate (see the introduction). |
| Remote go-ahead | The owner's explicit approval to create the GitHub repository and push to it (Q8, R2.11). |
| Bronze envelope | The fields every bronze record carries (R16.2), whatever its payload. |
| Allowlist | The hosts from which the submit tools accept facts: the MVP reading list in `docs/source-registry.md` (ADR-0005). |
| Private configuration | The file at `FANTADAMUS_PRIVATE_CONFIG` (default `~/.config/fantadamus/private.toml`) and the matching GitHub Actions secrets. It is never committed. |
| FantaCreator identity | A creator's real name, channel name, handle or channel URL, as listed in private configuration. |
| Identity matching | Comparison after Unicode NFKD normalisation, accent stripping, case folding and whitespace collapsing. |
| Data contract | A versioned pydantic model describing a bronze payload, a silver table or a gold product, with a semantic version and a changelog. |
| Contract schema | The JSON Schema generated from a data contract. |
| Walking skeleton | The minimal bronze → silver → gold pipeline over a three-row fixture, used to prove the harness. |
| Golden file | A committed, owner-reviewed expected output that a test compares against. |
| Throwaway branch | A short-lived branch, prefixed `gate-selftest/`, used only to prove a gate fails; it is deleted after the test. |

## Research: sources and terms of use

Spec 0 depends on tools and services, not data sources. Licences and costs below are as published by each
project or vendor on 2026-10-17. ADR-0001 records the final choice, with links and versions.

| Tool or service | Purpose | Licence or terms | Cost | Notes |
|---|---|---|---|---|
| uv | Python, dependency and lockfile management | MIT / Apache-2.0 | Free | `uv lock --check`, `uv sync --locked` |
| ruff | Format and lint (with `B`, `S`, `PGH`, `RUF` rules) | MIT | Free | Replaces black, flake8, isort and bandit's Python rules |
| mypy | Static types, `--strict` | MIT | Free | |
| pytest, pytest-cov | Tests and coverage | MIT | Free | |
| Hypothesis | Property-based tests | MPL-2.0 | Free | Profiles `dev` and `ci` |
| pytest-socket (or equivalent) | Block network access in unit and property tests | MIT | Free | |
| pydantic v2 | Data contracts | MIT | Free | |
| DuckDB | Local lakehouse engine | MIT | Free | |
| moto | AWS mocks | Apache-2.0 | Free | |
| sqlfluff | SQL lint | MIT | Free | Dialect chosen in design (DuckDB and Athena) |
| yamllint | YAML lint | GPL-3.0 | Free | Dev-time tool only; it is not distributed with our code |
| markdownlint-cli2 | Markdown lint | MIT | Free | Needs Node.js |
| actionlint | GitHub Actions workflow lint | MIT | Free | |
| pre-commit | Local hook runner | MIT | Free | Hook revisions pinned |
| commitizen or conventional-pre-commit | Conventional Commits check | MIT / Apache-2.0 | Free | Choice in ADR-0001 |
| gitleaks | Secret scanning | MIT | Free | The `gitleaks-action` wrapper requires a licence key for organisation-owned repositories; running the CLI directly avoids that dependency |
| pip-audit | Dependency vulnerability audit | Apache-2.0 | Free | Uses the PyPI/OSV advisory data |
| Dependabot or Renovate | Automated dependency updates | GitHub feature / AGPL-3.0 (self-hosted Renovate) | Free | Must cover `uv.lock`, GitHub Actions and pre-commit revisions. Whether Dependabot handles pre-commit revisions is unconfirmed (R11.4) |
| MCP Python SDK (`mcp`) | The MCP server and an in-process client for tests (R16.10–R16.13) | MIT | Free | Version pinned in `uv.lock` |
| mutmut | Mutation testing (phase gate only) | BSD-3-Clause | Free | |
| AWS CDK v2, cdk-nag | IaC option A, with `AwsSolutions` policy pack | Apache-2.0 | Free | CLI needs Node.js |
| Terraform, tflint, checkov | IaC option B | BSL 1.1 / MPL-2.0 / Apache-2.0 | Free for our use | OpenTofu (MPL-2.0) is the open-licence fork |
| GitHub, **public** repository | Hosting, CI, branch protection | GitHub Terms of Service | Free | Rulesets and branch protection are enforced on public repositories on GitHub Free, but not on private ones ([About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)). Owner decision, 2026-10-17: public repository (Q1) |
| GitHub secret scanning and push protection | Server-side secret scanning, a second layer behind gitleaks | GitHub Terms of Service | Free on public repositories | Push protection blocks a push containing a recognised secret before it lands on GitHub |
| Owner's `gamegusto` project (`~/Documents/gamegusto`) | Proven patterns for AWS permissions, Terraform layout and git conventions in the **same AWS account** | Owner's own code | Free | Reused as described in "Reuse from gamegusto" below |
| GitHub Actions | CI runners | GitHub Terms of Service | Free for public repositories on standard GitHub-hosted runners | Workflows triggered from forks get no secrets and, once configured, need owner approval to run |
| AWS Budgets | Cost alarm | AWS Service Terms | Budgets without budget actions are free (to confirm in design.md) | |
| Kiro hooks | Fast-feedback loop | Kiro terms | Included in Kiro | Hook files are `.kiro/hooks/<id>.json` with `version: "v1"` and a `hooks[]` array of `name`, `trigger`, `matcher`, `action` (`command` or `agent`), `timeout` and `enabled` ([Hooks](https://kiro.dev/docs/hooks/)). The exact trigger identifiers and the Pre Tool Use blocking contract are not documented and must be verified (R17.7) |
| Claude Code hooks | Fast-feedback loop in the agent gamegusto was built with | Anthropic terms | Included in Claude Code | Project hooks live in `.claude/settings.json`. A command hook receives the event as JSON on stdin; exit code 2 blocks a `PreToolUse` call or keeps a `Stop` from ending the turn, and returns stderr to the agent ([Hooks reference](https://docs.claude.com/en/docs/claude-code/hooks)). To be confirmed in ADR-0001 |

Other references for this spec: [Testing AWS CDK applications](https://docs.aws.amazon.com/cdk/v2/guide/testing.html);
[cdk-nag rule packs](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/check-aws-cdk-applications-or-cloudformation-templates-for-best-practices-by-using-cdk-nag-rule-packs.html);
[Well-Architected DevOps Guidance: continuous integration](https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/continuous-integration.html);
[Kiro hook triggers](https://kiro.dev/docs/hooks/types/);
[Terraform tests, including mocks and `override_data`](https://developer.hashicorp.com/terraform/language/tests);
[IAM permissions boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html);
[IAM quotas (managed policy size)](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html).

### Reuse from gamegusto

The owner's `gamegusto` project already runs in the AWS account Fantadamus will use, with a reviewed
least-privilege model. Spec 0 adopts that model rather than inventing a new one. The files are copied and
adapted **in the task that needs them**, not before, because no code lands ahead of an approved tasks.md.

| gamegusto source | What we reuse | Adapted how | Requirements |
|---|---|---|---|
| `infra/README.md`, two-module split `infra/bootstrap/` + `infra/stack/` | Bootstrap applied once by the owner as admin with local state; everything else applied as a scoped deploy role with remote state | Prefix `fantadamus`; the budget moves into bootstrap so that it is in the first module applied | R15, R22 |
| `infra/bootstrap/state.tf` | State bucket: versioned, encrypted, TLS-only, Block Public Access, `prevent_destroy`; native S3 locking (Terraform ≥ 1.11), no DynamoDB lock table | Unchanged apart from the prefix | R22.2 |
| `infra/bootstrap/boundary.tf` | Permissions boundary: the ceiling for every role the project creates | Rewritten for Fantadamus's runtime needs (S3, Glue, Athena, Step Functions…), grown slice by slice | R22.5 |
| `infra/bootstrap/deploy.tf` | Deny-first deploy policy: deny tampering with its own controls, deny roles without the boundary, restrict `iam:PassRole`; service wildcards over prefix-scoped ARNs to stay under IAM's 6,144-character limit | Prefix `fantadamus`; PassRole limited to the services Fantadamus uses; no DynamoDB live-table carve-out | R22.3–R22.8, R22.11 |
| `infra/bootstrap/terraform_user.tf` | Assume-only IAM user, so no admin key is used for day-to-day applies; no access keys created by Terraform | Unchanged apart from the prefix | R19.3, R22.10 |
| `infra/bootstrap/verify_policy.py` | A small deny-wins IAM evaluator with escalation, blast-radius and still-does-its-job cases | Moved into `tests/infra/` as a pytest suite that runs in CI on the rendered policy, plus a case proving the role cannot touch `gamegusto-*` resources | R22.9, AT-18 |
| `.gitignore` (Terraform section) | Ignore state, plans and `.terraform/`; **commit** `.terraform.lock.hcl` for provider pinning and checksum integrity | Merged into our `.gitignore` | R2.8 |
| `Makefile` | `help` target; `PROFILE`-driven Terraform wrapper; interactive `apply` | **Without** the `AUTO=1` auto-approve escape and the hard-coded login e-mail (R19.1, R14.7) | R1, R19.1 |
| `.pre-commit-config.yaml` | ruff-format, ruff and mypy hooks with pinned revisions | Extended with gitleaks, the identity check and the commit-message check | R9 |
| `CLAUDE.md` "Git" section | `<type>/<kebab>` branches, Conventional Commits, stage specific files, new commits rather than amending pushed history, PR body "what, why, how verified, known gaps" | Branch becomes `<type>/<spec>-<task>-<slug>`; the PR template adds the Definition of Done | R2.1, R21 |

**Not reused:** gamegusto has no CI workflows, no secret scanning and no budget, and its state backend
names the account ID in committed code. Fantadamus's repository is public, so the backend configuration
comes from private configuration instead (R14.7).

## Requirements

### Requirement 1: One check command

**User Story:** As the owner, I want one command that runs every check the same way locally and in CI, so
that a green local run predicts a green pull request.

#### Acceptance Criteria

- **R1.1** THE SYSTEM SHALL provide `make check`, which runs every check in the `make check` table of `quality.md` except mutation testing.
- **R1.2** WHEN CI runs on a pull request or on `main` THE SYSTEM SHALL run `make check`, either as one job or as parallel jobs whose `make` sub-targets together are exactly `make check`, with no CI-only variant of any check it contains.
- **R1.3** IF any check in `make check` fails THEN THE SYSTEM SHALL exit with a non-zero status after running the remaining checks, and SHALL print one pass or fail line per check.
- **R1.4** THE SYSTEM SHALL provide `make test-fast` (format, lint, unit and property tests with the `dev` Hypothesis profile) that finishes in under 30 seconds on the Spec 0 codebase, measured on a GitHub-hosted `ubuntu-latest` runner.
- **R1.5** THE SYSTEM SHALL provide `make setup`, which installs the locked Python environment, the pinned non-Python tools (R1.8) and the git hooks (pre-commit, commit-msg, pre-push) from a fresh clone with one command.
- **R1.6** THE SYSTEM SHALL run `make check` without AWS credentials and without network calls to AWS.
- **R1.7** THE SYSTEM SHALL provide `make mutation`, which runs mutation testing on the modules listed as core in `pyproject.toml`, for use at phase gates.
- **R1.8** THE SYSTEM SHALL pin the version and checksum of every non-Python tool (Terraform, tflint, checkov, gitleaks, actionlint, Node.js, markdownlint) in one committed file (`tool-versions.toml`), and `make setup` SHALL install them into a git-ignored, project-local `bin/` on macOS (Intel and Apple silicon) and Linux.
- **R1.9** IF an installed tool's version differs from its pin THEN THE SYSTEM SHALL fail `make check` with the expected and found versions.

### Requirement 2: Repository and branch policy

**User Story:** As the owner, I want `main` protected so that nothing reaches it without passing every
gate, including changes I make myself.

#### Acceptance Criteria

- **R2.1** THE SYSTEM SHALL be a public GitHub repository containing a README, a `.gitignore`, an `.editorconfig` and a pull-request template. The README SHALL state that no licence is granted (all rights reserved; Q7).
- **R2.2** THE SYSTEM SHALL reject direct pushes to `main`.
- **R2.3** THE SYSTEM SHALL reject force-pushes to `main` and the deletion of `main`.
- **R2.4** THE SYSTEM SHALL allow only squash merges into `main`.
- **R2.5** IF any required check has failed or has not completed on a pull request THEN THE SYSTEM SHALL block its merge into `main`.
- **R2.6** IF a pull request's branch is behind `main` THEN THE SYSTEM SHALL block its merge until the branch is updated and the required checks pass again.
- **R2.7** THE SYSTEM SHALL apply R2.2–R2.6 to repository administrators.
- **R2.8** THE SYSTEM SHALL git-ignore private configuration, `.env` files, local lake data (`data/local/`), private data (`data/private/`), the project-local `bin/`, build output, and Terraform state, plan files and `.terraform/` directories, while committing `.terraform.lock.hcl`; and local agent settings (`.claude/settings.local.json`, `.claude/launch.json`), while committing the shared `.claude/settings.json`.
- **R2.9** THE SYSTEM SHALL commit third-party content (data files, recorded source payloads, golden outputs derived from them) only where its terms of use permit public redistribution, recorded in the README of the directory that holds it, and SHALL keep all other such content in `data/private/`.
- **R2.10** THE SYSTEM SHALL keep personal data about league members (names, team names, rosters) out of the repository.
- **R2.11** THE SYSTEM SHALL create the GitHub repository and push to it only after the owner's remote go-ahead, given as its own task in tasks.md; until then all work stays local.
- **R2.12** THE SYSTEM SHALL define the `main` branch ruleset as committed JSON (`.github/rulesets/main.json`), apply it with a `make` target through the GitHub API, and IF the live ruleset differs from the committed one THEN THE SYSTEM SHALL fail the remote gate.

### Requirement 3: Python project and dependencies

**User Story:** As a developer, I want a reproducible Python environment so that every machine and every
CI run uses exactly the same dependencies.

#### Acceptance Criteria

- **R3.1** THE SYSTEM SHALL define one Python package, `fantadamus`, in a `src/` layout configured in `pyproject.toml`.
- **R3.2** THE SYSTEM SHALL pin Python 3.12 in both `requires-python` and `.python-version`.
- **R3.3** THE SYSTEM SHALL manage dependencies with uv and commit `uv.lock`.
- **R3.4** IF `uv.lock` is out of date with `pyproject.toml` THEN THE SYSTEM SHALL fail `make check`.
- **R3.5** WHEN CI installs dependencies THE SYSTEM SHALL install them only from the lockfile.

### Requirement 4: Format and lint

**User Story:** As a reviewer, I want style and common bugs caught by machines so that reviews focus on
behaviour.

#### Acceptance Criteria

- **R4.1** IF a Python file is not formatted as `ruff format` would format it THEN THE SYSTEM SHALL fail the format check.
- **R4.2** IF `ruff check` reports a violation of the configured rule set, which includes the bugbear (`B`) and bandit (`S`) rules, THEN THE SYSTEM SHALL fail the lint check.
- **R4.3** WHERE the repository contains SQL files THE SYSTEM SHALL lint them with sqlfluff and fail on any violation.
- **R4.4** IF a YAML file, a Markdown file or a GitHub Actions workflow fails yamllint, markdownlint or actionlint respectively THEN THE SYSTEM SHALL fail the lint check.

### Requirement 5: Types

**User Story:** As a developer, I want strict typing so that contract and pipeline errors surface before
runtime.

#### Acceptance Criteria

- **R5.1** IF `mypy --strict` reports an error in `src/`, `scripts/`, or any Python under `infra/` or `tests/infra/` THEN THE SYSTEM SHALL fail the type check.
- **R5.2** THE SYSTEM SHALL type-check `tests/` with mypy, with at least `check_untyped_defs` enabled.

### Requirement 6: Suppressions and thresholds (never weaken a gate)

**User Story:** As the owner, I want every exception to a gate to be visible, justified and approved, so
that nobody gets to green by weakening a gate.

#### Acceptance Criteria

- **R6.1** IF a suppression does not name the specific rule or error code it silences THEN THE SYSTEM SHALL fail the lint check.
- **R6.2** IF a suppression has no written reason THEN THE SYSTEM SHALL fail the lint check. The reason sits in an inline comment on the same line or the line above for code suppressions (`# noqa`, `# type: ignore`, `pytest.mark.skip`/`xfail`, Terraform and checkov skips), and in a `reason` field of the entry for file-based allowlists (`.gitleaks.toml`, the dependency-audit allowlist).
- **R6.3** IF a suppression has no matching entry in `docs/quality/suppressions.md` (location, rule, reason, approval date), the single register for every kind of suppression, THEN THE SYSTEM SHALL fail the lint check.
- **R6.4** IF a suppression no longer silences anything THEN THE SYSTEM SHALL fail the lint check.
- **R6.5** IF a pull request weakens any gate threshold relative to `main` (see Glossary: each threshold's safe direction) THEN THE SYSTEM SHALL fail the build.
- **R6.6** IF a test is skipped or marked `xfail` without a reason and a suppressions entry THEN THE SYSTEM SHALL fail the build.
- **R6.7** IF an entry in `docs/quality/suppressions.md` has a blank approval date THEN THE SYSTEM SHALL fail the lint check. An agent may propose an entry but leaves the date blank; only the owner fills it in.

### Requirement 7: Test harness

**User Story:** As a developer, I want a test harness with clear layers, so that each kind of test runs
where it belongs and failures are easy to reproduce.

#### Acceptance Criteria

- **R7.1** THE SYSTEM SHALL provide the test directories `tests/unit`, `tests/property`, `tests/contract`, `tests/integration`, `tests/acceptance` and `tests/infra`, each selectable with its own pytest marker.
- **R7.2** THE SYSTEM SHALL provide shared pytest fixtures and a `tests/fixtures/` directory for recorded payloads and CSVs.
- **R7.3** THE SYSTEM SHALL provide two Hypothesis profiles, `ci` (thorough) and `dev` (fast), selected by the `HYPOTHESIS_PROFILE` environment variable. `make check` SHALL use `ci` everywhere, locally and in CI, so a green local run predicts a green pull request; only `make test-fast` uses `dev`.
- **R7.4** IF a unit or property test attempts a network connection THEN THE SYSTEM SHALL fail that test.
- **R7.5** WHEN a property test fails THE SYSTEM SHALL report the shrunk failing example and the information needed to reproduce it.

### Requirement 8: Coverage

**User Story:** As the owner, I want coverage to stay high and only go up, so that the core logic stays
tested as the codebase grows.

#### Acceptance Criteria

- **R8.1** THE SYSTEM SHALL measure line and branch coverage of `src/` and `scripts/` across all test layers that `make check` runs.
- **R8.2** IF line coverage of `src/` and `scripts/` falls below the line threshold (initially 90 %) THEN THE SYSTEM SHALL fail the build.
- **R8.3** IF branch coverage of `src/` and `scripts/` falls below the branch threshold (initially 90 %) THEN THE SYSTEM SHALL fail the build.
- **R8.4** THE SYSTEM SHALL store the coverage thresholds in one configuration location, which R6.5 protects.

### Requirement 9: Pre-commit and commit messages

**User Story:** As a developer, I want problems caught before a commit exists, so that history stays clean
and CI rarely fails on trivial issues.

#### Acceptance Criteria

- **R9.1** WHEN a commit is created THE SYSTEM SHALL run the pre-commit hooks: format, lint, types, secret scan, FantaCreator-identity check, and checks for large files and merge-conflict markers.
- **R9.2** WHEN a commit message is written THE SYSTEM SHALL check it against the Conventional Commits specification.
- **R9.3** IF a pre-commit or commit-message hook fails THEN THE SYSTEM SHALL reject the commit.
- **R9.4** THE SYSTEM SHALL pin every pre-commit hook to a fixed revision.
- **R9.5** WHEN a pull request is opened or its title is edited THE SYSTEM SHALL check that the title follows Conventional Commits, because the title becomes the squash commit message on `main`.
- **R9.6** WHEN commits are pushed THE SYSTEM SHALL run the secret scan and the FantaCreator-identity check on every outgoing commit, and IF either fails THEN THE SYSTEM SHALL reject the push. In a public repository this is the preventive gate; CI is the detective one.

### Requirement 10: Secrets and FantaCreator identities

**User Story:** As the owner, I want credentials and creators' identities kept out of the repository
automatically, so that one careless commit can't leak them.

#### Acceptance Criteria

- **R10.1** IF a commit contains a secret or credential (for example an AWS access key, a private key or an API token) THEN THE SYSTEM SHALL reject it in pre-commit and fail CI.
- **R10.2** WHEN a pull request is opened or updated THE SYSTEM SHALL scan every commit in it for secrets, not only the final tree.
- **R10.3** IF a commit contains a FantaCreator identity, under identity matching, THEN THE SYSTEM SHALL reject it in pre-commit and fail CI.
- **R10.4** THE SYSTEM SHALL read the list of FantaCreator identities only from private configuration locally, and in CI from a GitHub Actions secret and an identical Dependabot secret (Dependabot pull requests can't read Actions secrets), and SHALL never commit that list in any form.
- **R10.5** IF the list of FantaCreator identities is unavailable THEN THE SYSTEM SHALL fail the identity check with a message explaining how to provide it.
- **R10.6** WHEN the identity check finds a match THE SYSTEM SHALL report only the file and line, never the matched text.
- **R10.7** THE SYSTEM SHALL enable GitHub secret scanning and push protection on the repository.
- **R10.8** THE SYSTEM SHALL provide a leak runbook (`docs/runbooks/leak.md`) for a secret or FantaCreator identity that reaches GitHub: rotate the secret; for an identity, delete the branch and pull request and ask GitHub support to purge cached views; then add a test that would have caught it.

### Requirement 11: Dependency security

**User Story:** As the owner, I want known-vulnerable dependencies to fail the build and updates to arrive
automatically, so that security doesn't depend on my memory.

#### Acceptance Criteria

- **R11.1** WHEN CI runs, and weekly on a schedule, THE SYSTEM SHALL audit the locked dependencies for known vulnerabilities.
- **R11.2** IF a locked dependency has a known vulnerability THEN THE SYSTEM SHALL fail the audit, unless an allowlist entry names that vulnerability with a reason and an expiry date.
- **R11.3** IF an allowlist entry has passed its expiry date THEN THE SYSTEM SHALL fail the audit.
- **R11.4** THE SYSTEM SHALL open dependency-update pull requests at least weekly for Python dependencies, GitHub Actions and pre-commit hook revisions. ADR-0001 confirms the tool; if Dependabot can't update pre-commit revisions, Renovate or a weekly `pre-commit autoupdate` workflow does.
- **R11.5** THE SYSTEM SHALL pin every third-party GitHub Action to a full commit SHA.
- **R11.6** WHEN the scheduled audit fails THE SYSTEM SHALL notify the owner.

### Requirement 12: Continuous integration

**User Story:** As the owner, I want every change checked automatically, in under 5 minutes, so that
feedback is fast and the merge gate can be trusted.

#### Acceptance Criteria

- **R12.1** WHEN a pull request is opened or updated THE SYSTEM SHALL run every check: `make check` (including its integration, golden-file, contract-version and infrastructure checks, split into parallel jobs as R1.2 allows) plus the checks that only make sense on a pull request: the secret scan of every commit (R10.2), the title check (R9.5) and the description check (R21.2).
- **R12.2** WHEN a commit lands on `main` THE SYSTEM SHALL run the same checks on `main`.
- **R12.3** THE SYSTEM SHALL keep the PR gate fast: the median of the last 10 pull-request runs SHALL be under 5 minutes, and IF any run takes over 8 minutes THEN THE SYSTEM SHALL fail AT-9.
- **R12.4** THE SYSTEM SHALL run CI with read-only repository permissions by default and without AWS credentials.
- **R12.5** THE SYSTEM SHALL cache dependencies keyed on the lockfile.
- **R12.6** IF a CI job exceeds its configured timeout THEN THE SYSTEM SHALL fail that job.
- **R12.7** WHERE the repository contains AWS Glue PySpark jobs THE SYSTEM SHALL run their tests in CI inside the AWS Glue 5 image (`public.ecr.aws/glue/aws-glue-libs:5`).
- **R12.8** IF a workflow run is triggered by a pull request from a fork THEN THE SYSTEM SHALL require the owner's approval before it runs, and SHALL give it no secrets.
- **R12.9** THE SYSTEM SHALL NOT use the `pull_request_target` trigger or any other trigger that runs fork-supplied code with write permissions or secrets.

### Requirement 13: Data-contract versioning

**User Story:** As a consumer of a data product, I want every schema change to be versioned and explained,
so that a change never breaks downstream code silently.

#### Acceptance Criteria

- **R13.1** THE SYSTEM SHALL give every data contract a semantic version and a changelog.
- **R13.2** WHEN a pull request changes a contract schema relative to `main` THE SYSTEM SHALL require a version bump and a changelog entry for the new version, and SHALL fail the contract-version check otherwise.
- **R13.3** IF a contract change removes or renames a field, narrows a type, or makes an optional field required THEN THE SYSTEM SHALL require a major version bump.

### Requirement 14: Infrastructure skeleton

**User Story:** As the owner, I want the cloud foundation defined as tested, policy-checked code, so that
the first deploy is safe and every later change is reviewable.

#### Acceptance Criteria

- **R14.1** THE SYSTEM SHALL define all AWS infrastructure as code in `infra/`, using the tool chosen in ADR-0002.
- **R14.2** THE SYSTEM SHALL define a storage stack, applied as the deploy role, with one private **lake bucket** (a prefix per medallion layer, for the MVP's Parquet once the MCP endpoint is remote) and an access-log bucket. The Athena query-results bucket, S3 Tables and Iceberg storage arrive with v1.
- **R14.3** THE SYSTEM SHALL configure every bucket in `infra/`, in both the bootstrap and the stack, with server-side encryption, all four Block Public Access settings, and a bucket policy that denies requests not made over TLS.
- **R14.4** THE SYSTEM SHALL enable versioning on the lake bucket, and server access logging to the access-log bucket for every bucket except the access-log bucket itself. The bootstrap's state bucket logs too, or carries a registered suppression with its reason.
- **R14.5** WHERE an Athena query-results bucket exists (v1) THE SYSTEM SHALL expire its objects after a configurable number of days, by default 7.
- **R14.6** THE SYSTEM SHALL tag every taggable resource with `Project=fantadamus`, `Environment`, `Spec` and `ManagedBy` (exactly these keys, which are case-sensitive in AWS), for cost allocation and the budget filter.
- **R14.7** THE SYSTEM SHALL read account IDs, e-mail addresses, AWS profiles and the remote-state backend configuration from private configuration or CI secrets, SHALL synthesise or plan in CI with placeholder values, and SHALL commit a `private.example.toml` with placeholder values only.
- **R14.8** WHEN CI runs THE SYSTEM SHALL synthesise or plan the infrastructure offline, run its fine-grained assertion tests and a snapshot test, and run the policy checks. Under Terraform, the assertions are `terraform test` runs and the snapshot is a committed, normalised plan in JSON; under CDK, they are CDK assertions and a template snapshot.
- **R14.9** WHERE the infrastructure is defined with AWS CDK THE SYSTEM SHALL apply the cdk-nag `AwsSolutions` pack at synth time.
- **R14.10** WHERE the infrastructure is defined with Terraform THE SYSTEM SHALL run `terraform fmt -check`, `terraform validate`, `tflint`, `checkov` and `terraform test`.
- **R14.11** IF a policy check reports a finding that has no written suppression reason THEN THE SYSTEM SHALL fail the infrastructure check.
- **R14.12** THE SYSTEM SHALL name every AWS resource it creates with the prefix `fantadamus-`, because the deploy role's permissions are scoped by that prefix.
- **R14.13** IF a taggable resource lacks any of the tags in R14.6 THEN THE SYSTEM SHALL fail the infrastructure tests.

### Requirement 15: Budget alarm

**User Story:** As the owner, I want a cost alarm in place before anything else exists in AWS, so that a
mistake can't run up a bill unnoticed.

#### Acceptance Criteria

- **R15.1** THE SYSTEM SHALL include an AWS Budgets monthly cost budget in the bootstrap module, which is the first module applied.
- **R15.2** WHEN actual monthly cost reaches 50 %, 80 % or 100 % of the budget, or forecast monthly cost reaches 100 %, THE SYSTEM SHALL e-mail the owner.
- **R15.3** THE SYSTEM SHALL take the budget amount and the notification thresholds as parameters, and the recipient from private configuration. The amount is in USD, because AWS Budgets works only in USD: it is the owner's EUR 20 per month (Q2), converted when bootstrap is applied and rounded down so the alerts fire early.
- **R15.4** THE SYSTEM SHALL make it impossible to apply any other module before the bootstrap module, because their remote state lives in the bucket that bootstrap creates.
- **R15.5** IF the planned bootstrap module lacks the budget or any of its notifications THEN THE SYSTEM SHALL fail the infrastructure tests.
- **R15.6** THE SYSTEM SHALL scope the budget to costs tagged `Project=fantadamus`, because the account is shared with gamegusto (Q9).
- **R15.7** WHEN the smoke test runs THE SYSTEM SHALL check that the `Project` cost-allocation tag is active in Billing, and IF it isn't THEN THE SYSTEM SHALL fail with instructions for the owner to activate it (activation can take up to 24 hours).

### Requirement 16: Walking skeleton

**User Story:** As a developer, I want a tiny end-to-end pipeline from day one, so that every layer of the
harness is proven before real sources arrive.

#### Acceptance Criteria

- **R16.1** THE SYSTEM SHALL provide a three-row fixture and a pipeline that carries it through bronze, silver and gold on DuckDB, entering through a minimal MCP submit tool and leaving through a minimal MCP read tool (the MVP's shape, ADR-0005), runnable with one `make` target.
- **R16.2** WHEN the skeleton ingests a payload THE SYSTEM SHALL write a bronze record whose envelope holds `source`, `source_url`, `published_at` (nullable), `captured_at` (when the source was read), `received_at` (when the server received it), `content_sha256`, `contract_version` and `submitted_by` (a pseudonymous user ID), with the payload. All times are UTC; as-of queries use `captured_at`.
- **R16.3** THE SYSTEM SHALL store bronze records append-only: an ingestion never modifies or deletes an existing bronze record, including when the same payload arrives again.
- **R16.4** WHEN bronze records are promoted to silver THE SYSTEM SHALL validate them against a versioned data contract.
- **R16.5** IF a record fails its data contract THEN THE SYSTEM SHALL keep it out of silver and report it with the reason.
- **R16.6** WHEN the skeleton builds its gold product THE SYSTEM SHALL compare the result with a committed golden file and fail on any difference.
- **R16.7** THE SYSTEM SHALL run the skeleton end to end, including its golden-file test, in under 10 seconds on a GitHub-hosted `ubuntu-latest` runner.
- **R16.8** THE SYSTEM SHALL lay out the skeleton's modules, tables and lake paths following `structure.md`, so that Spec 1 extends them rather than replacing them.
- **R16.9** THE SYSTEM SHALL use only synthetic or owner-approved data in the fixture, with no FantaCreator identity.
- **R16.10** WHEN a payload is submitted through the skeleton's MCP submit tool THE SYSTEM SHALL validate it against its contract and write it to bronze as in R16.2.
- **R16.11** IF a submitted payload's `source_url` host is not on the allowlist THEN THE SYSTEM SHALL reject it with the reason and write nothing.
- **R16.12** WHEN the skeleton's MCP read tool is called THE SYSTEM SHALL return the gold product, with the source URLs it was built from.
- **R16.13** THE SYSTEM SHALL exercise R16.10–R16.12 in `tests/integration` through an in-process MCP client, without network access.

### Requirement 17: Agent hooks

**User Story:** As the owner, I want the coding agent to get fast feedback and hit guard rails while it
works, the same way whether it runs in Claude Code (as gamegusto was built) or in Kiro, so that problems are
fixed in the same turn and risky actions wait for me.

#### Acceptance Criteria

- **R17.1** THE SYSTEM SHALL implement each hook's logic once, as a script in `scripts/hooks/` that reads the agent's JSON event on standard input. Claude Code project hooks (`.claude/settings.json`) and Kiro hooks (`.kiro/hooks/*.json`) SHALL call these scripts as thin wrappers.
- **R17.2** WHEN the agent edits a `*.py` file THE SYSTEM SHALL format and lint that file.
- **R17.3** WHEN the agent finishes a spec task, or a turn that changed tracked files, THE SYSTEM SHALL run `make check` with a 10-minute timeout and return any failure to the agent, so that a turn can't end on a red build without saying so; WHEN a turn changed no tracked files THE SYSTEM SHALL report that no check was needed.
- **R17.4** WHERE the agent provides a pre-task event (Kiro's Pre Task Execution) THE SYSTEM SHALL check that the task's dependencies are complete, that it names its requirement IDs and test, and that any ADR it depends on is Accepted, and IF any of these is missing THEN THE SYSTEM SHALL stop and ask the owner.
- **R17.5** IF the agent attempts a deploy (`terraform apply`, `make deploy`, `make bootstrap`) or a write to private configuration THEN THE SYSTEM SHALL block the tool call and ask the owner for approval. Before the remote go-ahead (R2.11) the same applies to every `git push` and `gh repo create`; afterwards, to force-pushes and pushes to `main`.
- **R17.6** THE SYSTEM SHALL test the hook scripts in CI by feeding them recorded agent events, asserting that a failing `make check` is returned to the agent and that every action in R17.5 is blocked.
- **R17.7** THE SYSTEM SHALL validate `.claude/settings.json` and every `.kiro/hooks/*.json` file in `make check` against their documented formats.
- **R17.8** THE SYSTEM SHALL record in ADR-0001 how each agent signals "block": Claude Code's exit-code contract, and Kiro's as verified empirically, since its documentation doesn't specify it.
- **R17.9** THE SYSTEM SHALL also run, in pre-commit or CI, every check that a hook runs. Hooks fire only on the agent's own actions; as in gamegusto, pre-commit, CI and the protected `main` are the gates of record.

### Requirement 18: Architecture decision records

**User Story:** As the owner, I want every research decision written down with its sources, so that I can
approve it before code depends on it and revisit it later.

#### Acceptance Criteria

- **R18.1** THE SYSTEM SHALL record each research decision as `docs/adr/NNNN-<decision>.md` with a status, a date and the sections Context, Options, Decision, Consequences and Sources.
- **R18.2** IF an ADR lacks a required section or cites no sources THEN THE SYSTEM SHALL fail the lint check.
- **R18.3** THE SYSTEM SHALL include, for Spec 0, ADR-0001 (tool choices, with licences, costs and the verified hook behaviour), ADR-0002 (CDK vs Terraform, with test and policy tooling) and ADR-0003 (AWS account, region and deploy identity).
- **R18.4** THE SYSTEM SHALL list, for each task in tasks.md and in each pull-request description, the ADRs it depends on, and IF any of them is not Accepted THEN THE SYSTEM SHALL fail the PR description check (and the pre-task check, R17.4).

### Requirement 19: Deploy gate and first deploy

**User Story:** As the owner, I want to see and approve every change before it reaches AWS, and to know
right away whether the deploy worked.

#### Acceptance Criteria

- **R19.1** THE SYSTEM SHALL deploy the stack only through a `make deploy` target that shows the infrastructure diff and requires interactive confirmation.
- **R19.2** THE SYSTEM SHALL NOT deploy from CI during Spec 0.
- **R19.3** THE SYSTEM SHALL deploy by assuming the scoped deploy role with short-lived session credentials (at most one hour). The only long-lived credential allowed is an access key for an identity whose sole permission is to assume that role.
- **R19.4** WHEN a deploy completes THE SYSTEM SHALL run a smoke test confirming that the buckets exist with encryption, Block Public Access and the TLS-only policy, and that the budget exists with its notifications.
- **R19.5** IF the smoke test fails THEN THE SYSTEM SHALL exit with a non-zero status and report which assertion failed.
- **R19.6** THE SYSTEM SHALL provide `make bootstrap` for the owner to apply the bootstrap module with the administrator profile: it SHALL first show `aws sts get-caller-identity` and the plan, and SHALL apply only after interactive confirmation.

### Requirement 20: Gate self-tests

**User Story:** As the owner, I want proof that each gate actually blocks a bad change, not just that it
runs.

#### Acceptance Criteria

- **R20.1** THE SYSTEM SHALL provide automated gate self-tests that, for each acceptance test that can be automated, introduce the bad change on a throwaway branch, assert that the gate fails, then delete the branch.
- **R20.2** WHERE a gate is enforced by GitHub settings THE SYSTEM SHALL exercise it through a throwaway pull request and the GitHub API, and close that pull request afterwards.
- **R20.3** WHERE a gate cannot be exercised automatically (a live run of the hooks inside Claude Code and Kiro) THE SYSTEM SHALL provide a manual procedure and record its evidence in the gate self-test report.
- **R20.4** WHEN the gate self-tests run THE SYSTEM SHALL write a report to `docs/reports/` listing each gate, the bad change and the observed result.
- **R20.5** THE SYSTEM SHALL run the gate self-tests locally, on demand, with the owner's own GitHub login; they SHALL never run in CI, whose token is read-only (R12.4).

### Requirement 21: Traceability and the Definition of Done

**User Story:** As the owner, I want every pull request to show which task, requirements and tests it
covers, so that I can check the Definition of Done at a glance.

#### Acceptance Criteria

- **R21.1** THE SYSTEM SHALL provide a pull-request template with the Definition of Done checklist from `quality.md` and fields for the task ID, the requirement IDs, the test names and the ADRs relied on.
- **R21.2** IF a pull request's description lacks a task ID, requirement IDs or test names THEN THE SYSTEM SHALL fail the PR description check, except for automated dependency-update pull requests.
- **R21.3** THE SYSTEM SHALL map every Spec 0 acceptance test to the requirement IDs it proves (table below).

### Requirement 22: Deploy identity and least privilege

**User Story:** As the owner, I want automation to run with the smallest permissions that can do the job,
inside an account I share with other projects, so that a mistake or a leaked key can't escalate, can't
touch other projects, and can't rewrite its own limits.

#### Acceptance Criteria

- **R22.1** THE SYSTEM SHALL provide a bootstrap module, applied once by the owner with an administrator identity, that creates the remote-state bucket, a permissions boundary, the deploy policy and role, an assume-only IAM user and the budget (R15.1).
- **R22.2** THE SYSTEM SHALL keep the bootstrap module's state local and git-ignored, and every other module's state in the remote-state bucket with native S3 locking.
- **R22.3** THE SYSTEM SHALL scope every Allow in the deploy policy to resources named with the `fantadamus-` prefix (or the `fantadamus/` path), except planning calls that AWS supports only on `"*"`, each listed with its reason in the policy source.
- **R22.4** THE SYSTEM SHALL deny the deploy role every action on its own role, its own policy, the permissions boundary and the assume-only user.
- **R22.5** IF the deploy role creates a role without the project's permissions boundary THEN THE SYSTEM SHALL deny the request.
- **R22.6** THE SYSTEM SHALL deny `iam:PassRole` to any service other than those the project uses, listed in the policy source.
- **R22.7** THE SYSTEM SHALL deny the deploy role access to resources of other projects in the account, including every `gamegusto-*` resource.
- **R22.8** THE SYSTEM SHALL NOT grant the deploy role secret-reading actions (`ssm:GetParameter*`, `secretsmanager:GetSecretValue`) outside the project's own path.
- **R22.9** WHEN CI runs THE SYSTEM SHALL render the deploy policy and the boundary without AWS credentials, evaluate them against escalation, blast-radius and still-does-its-job cases, and fail on any regression.
- **R22.10** THE SYSTEM SHALL NOT create access keys or other secrets in Terraform, because Terraform writes them into state.
- **R22.11** IF the rendered deploy policy exceeds IAM's managed-policy size limit (6,144 characters) THEN THE SYSTEM SHALL fail the infrastructure check.
- **R22.12** THE SYSTEM SHALL grant the deploy role read-only `budgets:ViewBudget` on `budget/fantadamus-*` and `ce:ListCostAllocationTags`, so the smoke test can verify R15 and R15.7, and SHALL include both in the still-does-its-job cases.

## Acceptance tests

AT-1 to AT-10 come from the owner's brief. AT-11 to AT-18 were added with the first drafts, AT-19 to AT-21
by the 2026-10-24 review. **Gate** says where a test runs: *Local* (owner's machine, before the remote
go-ahead), *Remote* (needs GitHub, after the go-ahead), *Both* (local and CI parts), *Deploy* (the first
deploy, task 12).

| ID | Acceptance test | Proves | Gate | Automation |
|---|---|---|---|---|
| AT-1 | A badly formatted file, and separately a lint error, each fail `make check`, the pre-commit hook and CI | R1.3, R4.1, R4.2, R9.3, R12.1 | Both | Gate self-test |
| AT-2 | A type error in `src/` or `scripts/` fails `make check` and CI | R5.1, R12.1 | Both | Gate self-test |
| AT-3 | A failing test blocks the merge into `main` | R2.5, R12.1 | Remote | Gate self-test via throwaway PR |
| AT-4 | A fake AWS secret key is rejected by pre-commit, by the pre-push hook and by CI, and GitHub push protection is enabled | R9.6, R10.1, R10.2, R10.7 | Both | Gate self-test |
| AT-5 | Coverage below the threshold fails `make check` and CI | R8.2, R8.3 | Both | Gate self-test |
| AT-6 | A bucket without encryption, or one that allows non-TLS access, fails the infrastructure check; it passes once fixed, or once suppressed with a written reason and a registered, approved entry | R14.3, R14.11, R6.2, R6.3 | Local | `tests/infra` |
| AT-7 | The walking skeleton: a payload submitted through the MCP submit tool reaches gold and is read back through the MCP read tool with its source URL; a payload from a host off the allowlist is rejected and nothing is written; the run takes under 10 s on `ubuntu-latest` and its golden-file test passes | R16.1–R16.13 | Local | `tests/acceptance`, `tests/integration` |
| AT-8 | When the agent finishes a task, or a turn that changed files, the hook runs `make check` and a failure is returned to the agent; a turn with no changes reports that no check was needed; deploys are blocked, and before the remote go-ahead so is every push | R17.3, R17.5, R17.6 | Local | `tests/unit` on recorded agent events, plus one live run per agent recorded in the gate self-test report (R20.3) |
| AT-9 | The median of the last 10 pull-request runs is under 5 minutes, and no run exceeds 8 minutes | R12.3 | Remote | Measured from the GitHub API |
| AT-10 | The planned bootstrap module contains the budget alarm, scoped to `Project=fantadamus` | R15.1, R15.2, R15.5, R15.6 | Local | `tests/infra` |
| AT-11 | A direct push to `main`, and a force-push to `main`, are rejected; the live ruleset matches the committed JSON | R2.2, R2.3, R2.7, R2.12 | Remote | Gate self-test |
| AT-12 | A commit containing a test FantaCreator identity is rejected by pre-commit and by the pre-push hook, and the output shows only file and line | R9.6, R10.3, R10.5, R10.6 | Local | Gate self-test, with a dummy identity in a test-only private configuration |
| AT-13 | A non-Conventional commit message is rejected locally, and a non-Conventional PR title fails CI | R9.2, R9.5 | Both | Gate self-test |
| AT-14 | A contract schema change without a version bump and changelog entry fails `make check` and CI; a field removal with only a minor bump fails too | R13.2, R13.3 | Both | Gate self-test |
| AT-15 | A blanket `# noqa`, a `# type: ignore` without a code, an unregistered suppression, an unexplained `skip`, and a register entry with a blank approval date each fail `make check` | R6.1–R6.4, R6.6, R6.7 | Local | Gate self-test |
| AT-16 | Weakening a gate threshold (lowering the coverage minimum, or raising the CI time budget) fails `make check` and CI | R6.5, R8.4 | Both | Gate self-test |
| AT-17 | A vulnerable pinned dependency fails the audit; with a valid allowlist entry it passes; with an expired entry it fails | R11.2, R11.3 | Both | Gate self-test |
| AT-18 | The rendered deploy policy refuses: editing its own controls, creating a role without the boundary, passing a role to an unlisted service, touching any `gamegusto-*` resource, and reading secrets outside its path. It still does its job, including reading its budget and the tag status. Removing any Deny statement makes the test fail | R22.3–R22.9, R22.11, R22.12 | Local | `tests/infra`, plus a gate self-test |
| AT-19 | A Dependabot pull request passes the FantaCreator-identity check | R10.4, R11.4 | Remote | Observed on the first Dependabot PR |
| AT-20 | A resource missing any of `Project`, `Environment`, `Spec` or `ManagedBy` fails the infrastructure tests | R14.6, R14.13 | Local | `tests/infra` |
| AT-21 | The smoke test fails with instructions while the `Project` cost-allocation tag is inactive, and passes once it's active | R15.7, R19.4 | Deploy | Smoke test after the first deploy |

## Out of scope for Spec 0

- Any pipeline code other than the walking skeleton; any real data source.
- The Athena query-results bucket, S3 Tables or self-managed Iceberg, Glue jobs, Step Functions and
  EventBridge schedules (v1).
- The MVP's real submit and read tools (Specs 1 and 3); Spec 0 has only the skeleton's minimal pair.
- Deploying from CI, and cross-account or multi-environment setups.
- Running mutation testing in the PR gate (phase gate only, R1.7).

## Owner decisions (formerly open questions)

| # | Question | Affects | Proposal |
|---|---|---|---|
| Q1 | ~~Repository visibility and branch protection.~~ **Resolved 2026-10-17:** public repository, so rulesets are enforced on GitHub Free. Follow-ups: R2.9, R2.10, R10.7, R12.8, R12.9, Q7 and Q8. | R2, AT-3, AT-11 | Public |
| Q2 | ~~Budget amount~~ **Resolved:** EUR 20 per month, scoped to `Project=fantadamus`. AWS Budgets works only in USD ([re:Post](https://repost.aws/questions/QU-J7u0-3ERYmcDdFeRWaxTA/is-the-currency-unit-in-aws-budgets-always-in-usd)), so the parameter is the USD equivalent when bootstrap is applied, rounded down. You still need to activate the `Project` cost-allocation tag in Billing. | R15.3, R15.6 | — |
| Q3 | ~~Region~~ **Resolved:** `eu-north-1`. S3 Tables is available there ([AWS, Jan 2025](https://aws.amazon.com/about-aws/whats-new/2025/01/amazon-s3-tables-additional-aws-regions)); Glue Data Quality is generally available wherever Glue is. ADR-0003 still confirms Lake Formation, Athena and Iceberg materialized views, and Spec 1's design must not depend on materialized views if they're missing. | R14, R19, ADR-0003 | — |
| Q4 | ~~Task order~~ **Resolved:** ADR-0001 right after task 1; ADR-0002, ADR-0003 and the bootstrap module before the infrastructure skeleton. | tasks.md | — |
| Q5 | ~~AT-8 and the Kiro IDE hook~~ **Resolved:** follow gamegusto's setup. Build with Claude Code; pre-commit, CI and the protected `main` are the gates of record. Hook logic lives in tested scripts shared by Claude Code and Kiro, so AT-8 is automated. | R17, AT-8 | — |
| Q6 | ~~Playbook and seed files~~ **Resolved:** the playbook is not used. The method was defined from scratch with the owner and delivered as `docs/method.md` on 2026-10-24, as input to Spec 2. No seed data is supplied: finding the best sources is the foundation of Spec 1 and starts with a dedicated sources discussion. Spec 0 is unaffected, because the walking skeleton uses a synthetic fixture. | Spec 1, Spec 2 | — |
| Q7 | ~~Licence~~ **Resolved:** none; all rights reserved. | R2.1 | — |
| Q8 | ~~Data in the public repo~~ **Resolved:** third-party and personal data stay in git-ignored `data/private/`. **Nothing is pushed to GitHub until the owner says so.** Local tasks go ahead; tasks that need the remote (CI runs, branch protection, gate self-tests through pull requests) wait for that go-ahead, which is its own task (R2.11). The exit gate is split into local and remote gates (Introduction). | R2, R12, R20 | — |
| Q9 | ~~Same AWS account as gamegusto, or a new one?~~ **Resolved 2026-10-17:** same account, isolated by the `fantadamus-` prefix, the permissions boundary and a tag-scoped budget. | R15.6, R22.7, ADR-0003 | Same account |
