---
inclusion: always
---

# Quality: phases, gates, checks and the Definition of Done

We go step by step. Every step ends at a gate, and **nothing moves forward on a red check**.

## Phases

| Phase | Spec | What gets built | Research around it | Exit gate |
|---|---|---|---|---|
| 0 | `engineering-foundation` | Repository, tooling, CI, test harness, Claude Code hooks, and a walking skeleton (a tiny fixture through bronze → silver → gold) | Tool choices (ADR-0001) | Spec 0's acceptance tests pass, including those proving each gate blocks a bad change: the **local gate** first, the **remote gate** after the owner's go-ahead to push (Spec 0, R2.11) |
| 1 | `mvp-x-or-y` | "X or Y?" for two forwards, locally: submit tools and storage for the facts it needs (ADR-0005), the method for forwards ([`docs/method.md`](../../docs/method.md) §A3–§A4), and `compare_players` | The MVP reading list for those facts; fitting team xG from betting lines | The slice's acceptance tests pass, including method §A9 tests 2, 4 and 6; one real round answered end to end in the owner's Claude Desktop |
| 2 | Further slices | First `mvp-collect`: Fantadamus collects the round's facts itself, many sources compared, forecast-style answers (ADR-0006). Then keepers and defenders; the full lineup with league rules, the bench and the simulation; the formation call | Calibrating the *(start)* constants against this season's data | Each slice's acceptance tests pass, ending with all six of method §A9; a calibration report exists for at least one real round |
| 3 | Online | The remote MCP endpoint for the second player, with the AWS skeleton, budget alarm and deploy gate moved from Phase 0 | Remote MCP auth; IaC (ADR-0002); account, region and deploy identity (ADR-0003) | Both users answered from their Claude apps; the first deploy passes its smoke test |
| 4 | v1 | Scheduled pipelines on AWS, licensed or permitted sources | Source registry decisions D1–D6 | Defined when v1 is specified |

Every exit gate ends with the owner's sign-off.

## The slice loop (Phase 1 onward)

Slices are **vertical**: one source or data product end to end, never all of bronze before any silver.

1. **Research.** A new source needs its route confirmed in the source registry and an ADR. No code for a
   source until the owner has approved its route. In the MVP, ADR-0005 is the route; each slice adds its
   sources to the MVP reading list, which is the submit tools' allowlist.
2. **Contract.** Versioned pydantic models for the bronze payload and the silver tables.
3. **Failing tests.** Unit, property and contract tests, plus the acceptance test the slice serves. Run
   them and show them failing.
4. **Pipeline.** Bronze → silver → gold, the minimum that turns the tests green.
5. **Quality checks.** The slice's data-quality rules, run on its fixtures.
6. **Slice gate.** `make check` and CI are green; post a short slice report and stop.

## The gates

1. **Spec gate.** The owner approves requirements.md, design.md and tasks.md in turn. An
   Analyze-Requirements-style review runs before design.
2. **Research gate.** Every research task ends in an ADR in `docs/adr/` (context, options, decision,
   consequences, sources). The owner approves it before any code depends on it.
3. **Task gate (Definition of Done).** A task is done only when:
   - its test was written first and seen failing, then passing;
   - `make check` is green;
   - tasks.md lists its requirement IDs and test names;
   - docs, contracts and data-product catalog entries it touches are updated;
   - it is committed on its own branch with a Conventional Commits message;
   - the task report (below) has been posted, and the agent has stopped.
4. **Merge gate.** One pull request per task. CI runs the same `make check` plus the integration and
   infrastructure jobs. Branch protection on `main` requires every check: no direct pushes, squash merges
   only.
5. **Deploy gate.** Nothing reaches AWS without the owner's approval. The owner sees the `terraform plan` (or
   `cdk diff`) first. The budget alarm is in the bootstrap module, the first one applied. A smoke test runs after every deploy.
6. **Phase gate.** The exit criteria are met. A phase report covers tests, coverage, quality results, cost
   and open risks, and from Phase 2 on a mutation-testing run on the core modules. The owner signs off
   before the next spec starts.

### Never weaken a gate to get to green

Don't skip or delete tests, lower thresholds, or add blanket `noqa`, `type: ignore`, `nosec` or policy
suppressions. **Every suppression** is rule-specific, carries a written reason (inline for code, a `reason`
field for file-based allowlists), and has an entry in `docs/quality/suppressions.md` with the owner's
approval date. An agent may propose an entry but leaves the approval date blank; only the owner fills it
in. Dependency-audit allowlist entries also carry an expiry date. Gate thresholds move only in their safe
direction: coverage and Hypothesis examples up, the CI time budget down.

## `make check`: one command, the same locally and in CI

Tools are **proposed** until ADR-0001 (tool choices) and ADR-0002 (IaC) are approved; this table is then
updated with the final list.

| Check | Proposed tool | Runs in |
|---|---|---|
| Format | `ruff format --check` | Hook, pre-commit, CI |
| Lint | `ruff check` (incl. bugbear `B` and bandit `S` rules); `sqlfluff` for SQL; `yamllint`; `markdownlint`; `actionlint` | Hook, pre-commit, CI |
| Types | `mypy --strict` | Pre-commit, CI |
| Unit and property tests | `pytest` with Hypothesis | Hook, CI |
| Contract tests | `pytest` against recorded source payloads | CI |
| Integration and golden files | The whole medallion on DuckDB from fixtures | CI |
| Coverage | `pytest-cov`: ≥ 90 % of lines and branches in `src/`; the threshold only goes up | CI |
| Data quality | Spec 1's rules, on fixtures | CI, and after every real ingestion |
| Data-contract versioning | Schema diff against `main`: a changed contract needs a version bump and a changelog entry | CI |
| Secrets and identities | `gitleaks`; a FantaCreator-identity check fed from private configuration | Pre-commit, **pre-push** (the preventive gate in a public repository), CI |
| Dependency security | `pip-audit` (allowlist with reason and expiry); Dependabot or Renovate | CI, weekly |
| Infrastructure | Terraform (proposed): `fmt`, `validate`, `tflint`, `checkov`, `terraform test` (offline, with `override_data`), and a committed, normalised plan JSON as the snapshot. CDK alternative: `cdk synth`, assertion tests, a template snapshot, cdk-nag `AwsSolutions` pack | CI |
| Tool versions | Every non-Python tool pinned with its checksum and installed by `make setup` into a project-local `bin/`; a version mismatch fails | Hook, CI |
| IAM policy self-test | Deny-wins evaluator (adapted from gamegusto's `verify_policy.py`) on the rendered deploy policy and boundary: escalation, blast radius (including `gamegusto-*`), still-does-its-job, size limit | CI |
| Commit messages | Conventional Commits | Pre-commit (commit-msg) |
| Mutation testing | `mutmut` on the core modules | Phase gate only |

- Dependencies are managed with `uv` and a committed lockfile.
- **The pull-request gate stays under 5 minutes**: the median of the last 10 runs, wall clock, all required
  checks; any run over 8 minutes fails the gate's own acceptance test.
- `make test-fast` is the inner loop: format, lint, unit and property tests with the fast Hypothesis profile,
  in under 20 seconds. `make check` runs its quick checks side by side and the test suite in parallel; slowness
  is treated as a defect, and any single test over two minutes fails with a traceback.

## Test layers

- **Unit:** pure functions with no I/O: parsing, name resolution, consensus, shrinkage, regression toward a
  prior. Network access fails the test.
- **Property-based:** Hypothesis, with properties derived from the EARS requirements (listed in each design.md),
  for example:
  - consensus p_start is always in [0, 1];
  - an official lineup always wins;
  - snapshots are only ever appended;
  - an as-of query never sees data captured after its timestamp;
  - name resolution gives the same answer whatever order names arrive in.
- **Contract:** every source parser runs against recorded raw payloads and must produce valid models, so a
  format change at the source fails loudly instead of loading garbage.
- **Integration:** bronze → silver → gold on DuckDB from fixtures, including the manual CSV path. AWS calls
  are mocked with moto. If Glue PySpark jobs are chosen, their tests run in CI inside AWS's Glue 5 image
  (`public.ecr.aws/glue/aws-glue-libs:5`).
- **Golden files:** gold products for the round-6 seed at fixed as-of times, compared with outputs the owner
  has reviewed.
- **Data quality:** each rule is defined once and runs on fixtures in CI, on DuckDB locally and with Glue
  Data Quality in AWS after each ingestion.
- **Infrastructure:** `terraform test` assertions on the planned resources, tflint and checkov (or CDK
  assertions, a snapshot test and cdk-nag), plus the IAM policy self-test on the rendered deploy policy.
- **Cloud smoke test:** after each deploy, run one pipeline on the seed and check row counts in Athena
  (Spec 0: check that the deployed resources exist and are configured as tested).
- **Acceptance:** each spec's acceptance tests, automated wherever the platform allows.
- **Collector check (MVP):** the collector is the user's Claude, so tools are tested with scripted
  submissions, and each slice ends with one manual end-to-end check in a Claude app (ADR-0005).
- **Calibration (from the MVP's first real round):** every published probability is logged with its as-of
  time; after each round, Brier score and reliability by bucket, next to the market's numbers (method §A8).
  This audits decisions, not results, and is reported in each phase report.

Hypothesis profiles, selected by `HYPOTHESIS_PROFILE`: `ci` (thorough) for `make check`, locally and in CI, so a
green local run predicts a green pull request; `dev` (fast) for `make test-fast` only.

**Fixtures** come only from approved routes or our manual CSVs, and they never contain a FantaCreator's real
name. Because the repository is public, a fixture is committed only if its source's terms permit public
redistribution; otherwise the test uses a synthetic fixture with the same schema, or reads from git-ignored
`data/private/` and is skipped (with a registered reason) when that data is absent.

## Agent setup (Claude Code)

The project is built the way gamegusto was: **Claude Code** is the only coding agent (Kiro was dropped on
2026-10-24), with `make check`, pre-commit, CI and the protected `main` as the gates of record. The specs
keep Kiro's file layout (`.kiro/steering/`, `.kiro/specs/`) because it works well as plain Markdown.

- Specs are **requirements-first**: requirements → design → tasks, each approved by the owner.
- Correctness property-based tests are **required**, never optional.
- **Supervised working:** the agent runs one task at a time, runs `make task-check TASK=<id>` first (once
  it exists), and stops after every task report so the owner can review.
- When a requirement changes mid-build: requirements.md, then design.md, then tasks.md, by hand.
- Hook logic lives in `scripts/hooks/`, is tested in CI on recorded events, and is wired into
  `.claude/settings.json`:

  | Purpose | Claude Code event |
  |---|---|
  | Format and lint an edited `*.py` file | `PostToolUse` on Edit/Write |
  | Run `make test-fast` (2-minute limit) when the turn changed tracked files, otherwise report that no check was needed; a failure goes back to the agent. The full `make check` runs before each task report | `Stop` |
  | Block deploys (`make deploy`, `make bootstrap`, `terraform apply`) and writes to private configuration; before the remote go-ahead every push and `gh repo create`, afterwards force-pushes and pushes to `main`, unless approved | `PreToolUse` on Bash/Write |

- Hooks fire only on the agent's own actions. **Pre-commit and CI are the gates of record**; hooks are
  the fast loop. Claude Code blocks with exit code 2 and the reason on stderr (ADR-0001).

## Task report

Post this after every task, then stop:

```text
Task 1.4: <title>
Requirements: R1.2, R1.3
Tests: tests/unit/test_aliases.py::test_soule_variants (red → green), …
make check: format ✓ lint ✓ types ✓ tests 142 ✓ coverage 93% ✓ security ✓ infra ✓
Changed: <files>
Decisions and open questions: …
Next: task 1.5
```

## References

- Spec format: Kiro's [feature specs](https://kiro.dev/docs/specs/feature-specs/) (EARS requirements, design, tasks), used as plain Markdown
- Claude Code [hooks](https://docs.claude.com/en/docs/claude-code/hooks)
- [Testing AWS CDK applications](https://docs.aws.amazon.com/cdk/v2/guide/testing.html)
- [Adopt a test-driven development approach (CDK)](https://docs.aws.amazon.com/prescriptive-guidance/latest/best-practices-cdk-typescript-iac/development-best-practices.html)
- [Check CDK applications or CloudFormation templates with cdk-nag rule packs](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/check-aws-cdk-applications-or-cloudformation-templates-for-best-practices-by-using-cdk-nag-rule-packs.html)
- [Develop and test AWS Glue jobs locally using a Docker image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html)
- [Run unit tests for Python ETL jobs in AWS Glue using pytest](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/run-unit-tests-for-python-etl-jobs-in-aws-glue-using-the-pytest-framework.html)
- Well-Architected DevOps Guidance: [Development lifecycle](https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/development-lifecycle.html),
  [Continuous integration](https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/continuous-integration.html),
  [QA.DT.1 data quality tests](https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/qa.dt.1-ensure-data-integrity-and-accuracy-with-data-quality-tests.html)
