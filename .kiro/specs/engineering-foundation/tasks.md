# Implementation Plan: `engineering-foundation` (Spec 0)

Status: **Approved; re-planned 2026-10-26** (requirements.md, change log) · Date: 2026-10-24 · From the approved [requirements](requirements.md)
and [design](design.md).

## How to read and run these tasks

- **One top-level task = one branch = one pull request**, named `<type>/ef-<n>-<slug>`. Sub-tasks are the
  steps inside it, each with its own test.
- Every sub-task lists:
  - `_Requirements:_` the criteria it implements;
  - `_Test:_` the test that proves it, written first and seen failing (red → green);
  - where relevant, `_Depends on:_` and `_ADRs:_`.
  `make task-check TASK=<id>` (R17.4) reads these lines; the agent runs it before every task once it
  exists (task 9.5), and checks the same things by hand until then.
- A ticked box (`- [x]`) marks a task or step as done. The agent ticks it on the task's own branch, so it
  reaches `main` only with the owner's merge; `make task-check` treats a dependency as complete when its
  box is ticked.
- Property-based tests (P1–P13 in the design) are **required** tasks. No task is optional.
- Run one task at a time and post the task report after each (`quality.md`).
- **Before the remote go-ahead (task 15)** there is no GitHub, so there are no pull requests. Each task
  still gets its own local branch. After the task report, the owner reviews it and squash-merges it into
  the local `main` (`git merge --squash`), with the task's Conventional Commits message. From task 15 on,
  every task goes through a pull request and the remote gate.
- **Owner** marks a step only the owner can do (approvals, admin AWS actions, creating the GitHub
  repository, Billing settings).
- Criteria with a WHERE condition that Spec 0 doesn't trigger get no task: R12.7 (no Glue jobs), R14.5 (no
  Athena bucket until v1), R14.9 (CDK, only if ADR-0002 chooses it).

## Tasks

- [x] 1. Repository skeleton (local only)
  - Branch: `chore/ef-1-repository` · Depends on: none · ADRs: none
  - [x] 1.1 `git init` with a `main` branch; README (purpose, setup, and "no licence granted, all rights
    reserved"); `.editorconfig`; `.gitignore` for private configuration, `.env*`, `data/local/`,
    `data/private/`, `bin/`, build output, Terraform state, plans and `.terraform/` (keeping
    `.terraform.lock.hcl`), `.claude/settings.local.json` and `.claude/launch.json`
    - _Requirements: R2.1, R2.8, R2.10_
    - _Test: no harness exists yet, so the proof is a recorded `git check-ignore -v` for each private path in
      the task report. Automated in 3.4: `tests/unit/test_repo_hygiene.py::test_private_paths_ignored`,
      `::test_readme_states_no_licence`_
  - [x] 1.2 Pull-request template with the Definition of Done checklist and fields for task, requirements,
    tests and ADRs; empty suppression register `docs/quality/suppressions.md`; ADR template
    `docs/adr/0000-template.md`
    - _Requirements: R21.1, R6.3, R18.1_
    - _Test: automated in 3.4: `tests/unit/test_repo_hygiene.py::test_pr_template_fields`,
      `::test_suppression_register_columns`_

- [x] 2. ADR-0001: tool choices (research)
  - Branch: `docs/ef-2-adr-0001` · Depends on: 1 · ADRs: none
  - [x] 2.1 Write `docs/adr/0001-tool-choices.md`. It confirms each tool, version and licence in the
    design's C3, plus commitizen vs conventional-pre-commit, and Dependabot vs Renovate (uv, GitHub Actions
    and pre-commit ecosystems).
    - _Requirements: R18.1, R18.3, R11.4_
    - _Test: owner approval; `scripts/checks/adr_lint` passes on it once 4.4 lands
      (`tests/unit/checks/test_adr_lint.py::test_repo_adrs_pass`)_
  - [x] 2.2 Claude Code hook contract: record from the official reference the events we use (`PreToolUse`,
    `PostToolUse`, `Stop`), their JSON payloads and the exit-code contract; save example payloads as
    fixtures for 9.1. The live confirmation is task 9.7.
    - _Requirements: R17.8_
    - _Test: the recorded payloads under `tests/fixtures/hooks/` parse in 9.1
      (`tests/contract/test_hook_events.py::test_recorded_events_parse`)_
  - [x] 2.3 **Owner:** approve ADR-0001 (status Accepted)
    - _Requirements: R18.4_
    - _Test: `Status: Accepted` in the ADR; checked by `pr_meta` and `pre_task` from 9.5 and 13.2_

- [x] 3. Python project and pinned toolchain
  - Branch: `chore/ef-3-python-project` · Depends on: 2 · ADRs: ADR-0001
  - [x] 3.1 `pyproject.toml` with the `fantadamus` package in `src/`, Python 3.12 in `requires-python` and
    `.python-version`, runtime and dev dependencies from the design's C3; `uv.lock` committed
    - _Requirements: R3.1, R3.2, R3.3, R3.5_
    - _Test: `tests/unit/test_project.py::test_python_pinned_312`, `::test_src_layout_importable`_
  - [x] 3.2 Lockfile check `scripts/checks/lockfile.py`
    - _Requirements: R3.4_
    - _Test: `tests/unit/checks/test_lockfile.py::test_stale_lock_fails`_
  - [x] 3.3 `tool-versions.toml` (terraform, tflint, gitleaks, actionlint; version and SHA-256 per platform);
    `scripts/tools/install.py` into `bin/`; `scripts/checks/tool_versions.py`
    - _Requirements: R1.8, R1.9_
    - _Test: `tests/unit/tools/test_install.py::test_checksum_mismatch_refused`,
      `tests/unit/checks/test_tool_versions.py::test_version_mismatch_fails`_
  - [x] 3.4 Backfill task 1's proofs as tests
    - _Requirements: R2.1, R2.8, R2.10, R21.1_
    - _Test: `tests/unit/test_repo_hygiene.py` (the four tests named in task 1)_

- [x] 4. Format, lint, types and gate integrity
  - Branch: `chore/ef-4-lint-types` · Depends on: 3 · ADRs: ADR-0001
  - [x] 4.1 ruff (format; lint with `B`, `S`, `PGH`, `RUF`), mypy `--strict` on `src/`, `scripts/` and
    Python under `infra/` and `tests/infra/` (tests with `check_untyped_defs`), plus sqlfluff, yamllint,
    markdownlint and actionlint configurations
    - _Requirements: R4.1, R4.2, R4.3, R4.4, R5.1, R5.2_
    - _Test: `tests/unit/test_tool_config.py::test_ruff_selects_bugbear_and_bandit`,
      `::test_mypy_strict_paths`, `::test_linters_configured`_
  - [x] 4.2 Suppression lint `scripts/checks/suppressions.py` and the register format
    - _Requirements: R6.1, R6.2, R6.3, R6.4, R6.6, R6.7_
    - _Test: `tests/unit/checks/test_suppressions.py` (one case per rule, including a blank approval date);
      property P10 `tests/property/test_suppression_lint.py::test_suppression_lint`_
  - [x] 4.3 `config/thresholds.toml` with directions; ratchet check `scripts/checks/thresholds.py`
    - _Requirements: R6.5, R8.4_
    - _Test: `tests/unit/checks/test_thresholds.py::test_weakened_coverage_fails`,
      `::test_raised_time_budget_fails`; property P9
      `tests/property/test_threshold_ratchet.py::test_threshold_ratchet`_
  - [x] 4.4 ADR lint `scripts/checks/adr_lint.py`
    - _Requirements: R18.1, R18.2_
    - _Test: `tests/unit/checks/test_adr_lint.py::test_missing_section_fails`, `::test_no_sources_fails`,
      `::test_repo_adrs_pass`_

- [x] 5. Test harness and coverage
  - Branch: `test/ef-5-harness` · Depends on: 3 · ADRs: ADR-0001
  - [x] 5.1 Layer directories; `tests/conftest.py` applying one marker per directory; shared fixtures;
    `pytest-socket` blocking the network in unit and property tests
    - _Requirements: R7.1, R7.2, R7.4_
    - _Test: `tests/unit/test_harness.py::test_markers_applied_by_directory`,
      `::test_network_blocked_in_unit_tests`_
  - [x] 5.2 Hypothesis profiles `ci` and `dev`, chosen by `HYPOTHESIS_PROFILE`; failures print the seed
    - _Requirements: R7.3, R7.5_
    - _Test: `tests/unit/test_harness.py::test_profile_selection`, `::test_failure_prints_reproduction`_
  - [x] 5.3 Coverage of `src/` and `scripts/`, and the gate `scripts/checks/coverage_gate.py` (line and
    branch checked separately)
    - _Requirements: R8.1, R8.2, R8.3_
    - _Test: `tests/unit/checks/test_coverage_gate.py::test_branch_below_threshold_fails`; property P13
      `tests/property/test_coverage_gate.py::test_coverage_gate`_

- [x] 6. Git hooks, secrets and identities
  - Branch: `chore/ef-6-git-hooks` · Depends on: 4, 5 · ADRs: ADR-0001
  - [x] 6.1 `.pre-commit-config.yaml` with pre-commit, commit-msg and pre-push stages; every `rev` pinned
    - _Requirements: R9.1, R9.3, R9.4_
    - _Test: `tests/unit/test_precommit_config.py::test_all_revs_pinned`, `::test_stages_present`_
  - [x] 6.2 conventional-pre-commit as the commit-msg hook (ADR-0001)
    - _Requirements: R9.2_
    - _Test: `tests/integration/test_commit_msg.py::test_non_conventional_message_rejected` (temporary repo)_
  - [x] 6.3 Identity check `scripts/checks/identities.py`: loads from private configuration or the CI
    secret, fails closed, normalises, scans staged files, a commit range or the tree, prints `path:line`
    only
    - _Requirements: R10.3, R10.4, R10.5, R10.6_
    - _Test: `tests/unit/checks/test_identities.py::test_missing_list_fails_closed`; property P7
      `tests/property/test_identity.py::test_identity_normalisation`, `::test_identity_output_redacted`_
  - [x] 6.4 `.gitleaks.toml` and a wrapper for staged, range and tree scans
    - _Requirements: R10.1, R10.2_
    - _Test: `tests/integration/test_gitleaks_wrapper.py::test_fake_aws_key_detected_in_range`_
  - [x] 6.5 The pre-push stage runs gitleaks and the identity check on every outgoing commit
    - _Requirements: R9.6_
    - _Test: `tests/integration/test_pre_push.py::test_outgoing_secret_rejected`,
      `::test_outgoing_identity_rejected`_
  - [x] 6.6 Leak runbook `docs/runbooks/leak.md`
    - _Requirements: R10.8_
    - _Test: `tests/unit/test_repo_hygiene.py::test_leak_runbook_sections`_

- [x] 7. Make targets and dependency audit
  - Branch: `chore/ef-7-make` · Depends on: 4, 5, 6 · ADRs: ADR-0001
  - [x] 7.1 Makefile: `setup`, `check` (runs everything, then a per-check summary), `check-static`,
    `check-tests`, `check-infra` (Python-only until task 11), `check-audit`, `test-fast`, `mutation`,
    `help`; `make check` uses `HYPOTHESIS_PROFILE=ci` and no AWS credentials
    - _Requirements: R1.1, R1.2, R1.3, R1.4, R1.5, R1.6, R1.7_
    - _Test: `tests/unit/test_makefile.py::test_check_continues_and_summarises`,
      `::test_check_is_union_of_subtargets`, `::test_check_env_has_no_aws_credentials`,
      `::test_setup_installs_all_hook_types`_
  - [x] 7.2 `pip-audit` with `config/audit-allowlist.toml` (id, reason, expiry)
    - _Requirements: R11.1, R11.2, R11.3_
    - _Test: `tests/unit/checks/test_audit_allowlist.py::test_expired_entry_fails`,
      `::test_entry_requires_reason`, `::test_offline_audit_fails_not_passes`_

- [x] 8. Contracts and the walking skeleton
  - _The skeleton was retired on 2026-10-31 (requirements change log); the tests named below for it are gone._
  - Branch: `feat/ef-8-walking-skeleton` · Depends on: 5, 7 · ADRs: ADR-0001
  - [x] 8.1 `core`: canonical-JSON hashing, the injected clock, URL host matching for the allowlist
    - _Requirements: R16.2, R16.11_
    - _Test: property P2 `tests/property/test_hashing.py::test_hash_canonical`; property P3
      `tests/property/test_allowlist.py::test_allowlist_rejects_lookalikes`_
  - [x] 8.2 Contract base, bronze envelope, `SkeletonPlayer` 1.0.0, committed JSON schemas and changelog;
    contract-version check `scripts/checks/contracts.py`
    - _Requirements: R13.1, R13.2, R13.3, R16.2, R16.4_
    - _Test: `tests/contract/test_skeleton_schema.py::test_schema_matches_committed`; property P8
      `tests/property/test_contract_versions.py::test_contract_version_rules`_
  - [x] 8.3 DuckDB/Parquet lake store: append-only bronze, silver promotion with the quality rule, gold
    - _Requirements: R16.3, R16.4, R16.5, R16.6, R16.8_
    - _Test: properties P1 `tests/property/test_lake.py::test_bronze_append_only`, P4
      `::test_valid_rows_roundtrip`, P5 `::test_invalid_rows_excluded`, P6 `::test_gold_order_invariant`;
      `tests/unit/test_quality_rules.py::test_duplicate_player_id_reported`_
  - [x] 8.4 MCP server with `submit_skeleton_rows` and `get_skeleton_summary`; `config/sources.toml`
    - _Requirements: R16.10, R16.11, R16.12, R16.13_
    - _Test: `tests/integration/test_skeleton_mcp.py::test_submit_then_read`,
      `::test_off_allowlist_rejected_nothing_written` (in-process MCP client)_
  - [x] 8.5 Synthetic fixture and golden file (each with a README on why it may be public), the CLI, and
    `make skeleton`
    - _Requirements: R16.1, R16.6, R16.7, R16.9, R2.9_
    - _Test: **AT-7** `tests/acceptance/test_at7_walking_skeleton.py::test_at7_walking_skeleton` (timed,
      golden file)_

- [x] 9. Agent hooks
  - Branch: `feat/ef-9-agent-hooks` · Depends on: 2, 7 · ADRs: ADR-0001
  - [x] 9.1 `HookEvent` parser for Claude Code payloads
    - _Requirements: R17.1_
    - _Test: `tests/contract/test_hook_events.py::test_recorded_events_parse`_
  - [x] 9.2 `post_edit`: format and lint the edited file
    - _Requirements: R17.2_
    - _Test: `tests/unit/hooks/test_post_edit.py::test_formats_and_reports_remaining`_
  - [x] 9.3 `stop_check`: runs `make check` only on changes, with a 10-minute timeout and loop protection
    - _Requirements: R17.3_
    - _Test: `tests/unit/hooks/test_stop_check.py::test_no_changes_reports_no_check`,
      `::test_red_first_time_blocks`, `::test_red_again_allows_stop_with_message`,
      `::test_timeout_is_failure`_
  - [x] 9.4 `guard`: pushes, remote creation, deploys and private-configuration writes
    - _Requirements: R17.5_
    - _Test: `tests/unit/hooks/test_guard.py::test_pre_go_ahead_blocks_any_push`; property P11
      `tests/property/test_guard.py::test_guard_commands`_
  - [x] 9.5 `make task-check TASK=<id>` (`scripts/checks/task_check.py`): dependencies, requirement IDs,
    tests and ADR status; CLAUDE.md tells the agent to run it before each task
    - _Requirements: R17.4, R18.4_
    - _Test: `tests/unit/checks/test_task_check.py::test_missing_requirements_fails`,
      `::test_unaccepted_adr_fails`, `::test_unfinished_dependency_fails`_
  - [x] 9.6 Wire `.claude/settings.json`; hook-config check
    - _Requirements: R17.1, R17.6, R17.7, R17.9_
    - _Test: `tests/unit/checks/test_hook_config.py::test_configs_valid`; **AT-8**
      `tests/acceptance/test_at8_agent_hooks.py::test_at8_agent_hooks` (recorded events)_
  - [x] 9.7 Live check in Claude Code (owner and agent): a red stop, a blocked push and a blocked deploy,
    with the observed payloads compared against 2.2's fixtures and the evidence recorded
    - _Requirements: R20.3, R17.8_
    - _Test: checklist evidence in `docs/reports/gate-selftest-<date>.md`_

- [ ] 10. ADR-0002 (IaC) and ADR-0003 (account, region, deploy identity)
  - Branch: `docs/ef-10-adr-0002-0003` · Depends on: 4.4 · ADRs: none
  - **Moved to Phase 3** by the 2026-10-26 re-plan: built with the online server, not now.
  - [ ] 10.1 ADR-0002: Terraform vs CDK, with a spike in a scratch module proving offline rendering of the
    policy templates and a `mock_provider` plan
    - _Requirements: R14.1, R14.10, R18.3_
    - _Test: `tests/unit/checks/test_adr_lint.py::test_repo_adrs_pass`; spike output recorded in the ADR_
  - [ ] 10.2 ADR-0003: the gamegusto account, `eu-north-1`, and the bootstrap → assume-only user → deploy
    role chain
    - _Requirements: R18.3, R19.3_
    - _Test: `tests/unit/checks/test_adr_lint.py::test_repo_adrs_pass`_
  - [ ] 10.3 **Owner:** approve ADR-0002 and ADR-0003 (status Accepted)
    - _Requirements: R18.4_
    - _Test: `Status: Accepted` in both ADRs_

- [ ] 11. Bootstrap module (written and tested, not applied)
  - Branch: `feat/ef-11-bootstrap` · Depends on: 7, 10 · ADRs: ADR-0002, ADR-0003
  - **Moved to Phase 3** by the 2026-10-26 re-plan: built with the online server, not now.
  - [ ] 11.1 `versions.tf`, default tags, the state and log buckets (encryption, Block Public Access, TLS
    deny, versioning, lifecycle, logging)
    - _Requirements: R14.3, R14.4, R14.6, R14.12, R14.13, R22.2_
    - _Test: `infra/bootstrap/tests/buckets.tftest.hcl` (runs `state_bucket_secure`, `log_bucket_secure`,
      `tags_present`)_
  - [ ] 11.2 Policy templates (`boundary.json.tftpl`, `deploy.json.tftpl`), the role, and the group and
    user; the IAM evaluator adapted from gamegusto into `tests/infra/`
    - _Requirements: R22.1, R22.3, R22.4, R22.5, R22.6, R22.7, R22.8, R22.9, R22.10, R22.11, R22.12_
    - _Test: `tests/infra/test_deploy_policy.py` (gamegusto's cases plus `gamegusto-*` blast radius,
      budget read and tag read; `::test_policy_under_size_limit`, `::test_renders_without_credentials`); property P12
      `tests/property/test_iam_eval.py::test_iam_deny_wins`;
      `tests/unit/test_policy_templates.py::test_no_template_directives`; **AT-18**
      `tests/acceptance/test_at18_deploy_policy.py::test_at18_deploy_policy`_
  - [ ] 11.3 The budget (USD amount variable, tag filter, four notifications, e-mail from private
    configuration)
    - _Requirements: R15.1, R15.2, R15.3, R15.4, R15.5, R15.6_
    - _Test: `infra/bootstrap/tests/budget.tftest.hcl`; **AT-10**
      `tests/acceptance/test_at10_budget_alarm.py::test_at10_budget_alarm`_
  - [ ] 11.4 `make bootstrap`: shows the caller identity and the plan, applies only after confirmation
    - _Requirements: R19.6_
    - _Test: `tests/unit/test_makefile.py::test_bootstrap_shows_identity_and_requires_confirmation` (stubbed
      terraform and aws)_

- [ ] 12. Stack module, policy checks, deploy and smoke test (written and tested, not applied)
  - Branch: `feat/ef-12-stack` · Depends on: 11 · ADRs: ADR-0002, ADR-0003
  - **Moved to Phase 3** by the 2026-10-26 re-plan: built with the online server, not now.
  - [ ] 12.1 Partial S3 backend; lake bucket with prefixes, versioning, lifecycle and logging; tags
    - _Requirements: R14.2, R14.3, R14.4, R14.6, R14.12, R14.13_
    - _Test: `infra/stack/tests/lake.tftest.hcl`; **AT-6**
      `tests/acceptance/test_at6_bucket_policy_gate.py::test_at6_bucket_policy_gate`; **AT-20**
      `tests/acceptance/test_at20_tags_required.py::test_at20_tags_required`_
  - [ ] 12.2 tflint and checkov in `check-infra`; proposed suppressions entered with blank approval dates
    - _Requirements: R14.10, R14.11_
    - _Test: `make check-infra` green after the **Owner** fills in the approval dates (R6.7 blocks it
      before)_
  - [ ] 12.3 Plan snapshot `infra/stack/plan.snapshot.json` and its comparison
    - _Requirements: R14.8_
    - _Test: `tests/infra/test_plan_snapshot.py::test_snapshot_matches`, `::test_drift_fails`_
  - [ ] 12.4 `private.example.toml` with placeholders only; configuration loading
    - _Requirements: R14.7_
    - _Test: `tests/unit/test_private_config.py::test_example_has_placeholders_only`_
  - [ ] 12.5 `make deploy` (plan, confirm, apply, smoke) and `scripts/smoke/spec0.py`
    - _Requirements: R19.1, R19.2, R19.4, R19.5, R15.7_
    - _Test: `tests/integration/test_smoke.py::test_tag_inactive_fails_with_instructions`,
      `::test_reports_failed_assertion` (moto)_

- [x] 13. CI workflow, Dependabot and the GitHub setup checklist (written, not yet run)
  - Branch: `chore/ef-13-ci` · Depends on: 7 · ADRs: ADR-0001
  - [x] 13.1 `ci.yml` `check` job: `make setup` and `make check`; read-only permissions; concurrency;
    10-minute timeout; uv cache; actions pinned to SHAs; no `pull_request_target`
    - _Requirements: R1.2, R11.5, R12.1, R12.2, R12.4, R12.5, R12.6, R12.9_
    - _Test: `tests/unit/test_ci_workflow.py::test_check_job_runs_make_check`, `::test_actions_pinned_to_sha`,
      `::test_no_pull_request_target`, `::test_read_only_permissions`, `::test_job_timeouts`_
  - [x] 13.2 `pr` job: the title as a Conventional Commits message; gitleaks and the identity check over
    `base..head`
    - _Requirements: R9.5, R10.2, R21.2_
    - _Test: `tests/unit/test_ci_workflow.py::test_pr_job_checks_title_and_commit_range`_
  - [x] 13.3 `audit.yml` (weekly) and `dependabot.yml` (uv, GitHub Actions, pre-commit)
    - _Requirements: R11.1, R11.4, R11.6_
    - _Test: `tests/unit/test_ci_workflow.py::test_audit_schedule_weekly`,
      `::test_dependency_updates_cover_uv_actions_precommit`_
  - [x] 13.4 `docs/runbooks/github-setup.md`: the ruleset, secret scanning, push protection, fork approval
    and the identity secret, as a checklist for the go-ahead
    - _Requirements: R2.2, R2.3, R2.4, R2.5, R2.6, R2.7, R2.12, R10.4, R10.7, R12.8_
    - _Test: `tests/unit/test_github_setup.py::test_checklist_covers_each_setting`_

- [x] 14. Local acceptance tests and the **local gate**
  - Branch: `test/ef-14-local-gate` · Depends on: 6, 7, 8, 9, 13 · ADRs: ADR-0001
  - [x] 14.1 One test per local acceptance test, each running the real gate on a bad input in a temporary
    directory or repository, gathered in one file: AT-1, AT-2, AT-4, AT-5, AT-12, AT-13, AT-14, AT-15, AT-16
    and AT-17 (local parts)
    - _Requirements: R1.3, R4.1, R4.2, R5.1, R6.1, R6.2, R6.3, R6.4, R6.5, R6.6, R6.7, R8.2, R8.3, R9.2, R9.3,
      R9.6, R10.1, R10.3, R10.5, R10.6, R11.2, R11.3, R13.2, R13.3, R20.1_
    - _Test: `tests/acceptance/test_local_gates.py::test_at1_format_lint_gate`, `::test_at2_type_gate`,
      `::test_at4_fake_aws_key_rejected`, `::test_at5_coverage_gate`, `::test_at12_identity_rejected`,
      `::test_at13_conventional_commits`, `::test_at14_contract_versioning`, `::test_at15_suppressions`,
      `::test_at16_threshold_ratchet`, `::test_at17_dependency_audit`_
  - [x] 14.2 Traceability: every acceptance test maps to existing requirements, and every local one to a test
    file; the gate report lists them
    - _Requirements: R20.4, R21.3_
    - _Test: `tests/unit/test_traceability.py::test_acceptance_tests_map_to_existing_requirements`,
      `::test_local_acceptance_tests_exist`_
  - [x] 14.3 **Owner:** review the local gate report → **local gate passed**
    - _Requirements: Phase 0 exit gate, local part (requirements, Introduction)_
    - _Test: `docs/reports/gate-selftest-<date>.md` shows every local gate failing on its bad input_

- [x] 15. Remote go-ahead and the **remote gate**
  - Branch: `chore/ef-15-remote` · Depends on: 14 · ADRs: ADR-0001
  - [x] 15.1 **Owner:** give the remote go-ahead: create the public repository, apply
    `docs/runbooks/github-setup.md`, add the identity secret, push `main`
    - _Requirements: R2.1, R2.11, R2.12, R10.4, R10.7_
    - _Test: the checklist, ticked, in the gate report_
  - [x] 15.2 The remote checklist with throwaway branches: a failing test blocks the merge (AT-3), push
    protection rejects a fake key (AT-4), direct and force pushes to `main` are refused (AT-11), a
    non-Conventional PR title fails (AT-13)
    - _Requirements: R2.2, R2.3, R2.5, R2.6, R2.7, R9.5, R10.2, R12.1, R12.2, R20.2, R20.5_
    - _Test: evidence in `docs/reports/gate-selftest-<date>.md`_
  - [x] 15.3 From the first pull requests: CI time (AT-9) and the first Dependabot PR (AT-19)
    - _Requirements: R12.3, R11.4, R10.4_
    - _Test: both noted in the gate report_
  - [x] 15.4 **Owner:** review the remote gate report → **remote gate passed**
    - _Requirements: Phase 0 exit gate, remote part_
    - _Test: the report shows every remote gate failing as expected_

- [ ] 16. First deploy (owner approval)
  - Branch: `chore/ef-16-first-deploy` · Depends on: 12, 14 · ADRs: ADR-0002, ADR-0003
  - **Moved to Phase 3** by the 2026-10-26 re-plan: built with the online server, not now.
  - [ ] 16.1 **Owner:** activate the `Project` cost-allocation tag in Billing; run `make bootstrap` with the
    admin profile; create the access key for `fantadamus-terraform` by hand; configure the
    `fantadamus-deploy` profile
    - _Requirements: R15.1, R19.6, R22.1, R19.3_
    - _Test: `terraform output` of the bootstrap shows the state bucket, the role and the budget_
  - [ ] 16.2 **Owner:** `make deploy` (review the plan, confirm); the smoke test runs
    - _Requirements: R19.1, R19.4, R19.5, R15.7_
    - _Test: **AT-21** smoke-test output recorded in `docs/reports/first-deploy-<date>.md` (fails while the
      tag is inactive, passes once active)_

- [x] 17. Phase 0 gate
  - Branch: `docs/ef-17-phase-report` · Depends on: 15 · ADRs: none
  - [x] 17.1 Short phase report in `docs/reports/`: tests, coverage, gate results, cost ($0), open risks.
    Mutation testing starts in Phase 2, once there is football logic to mutate
    - _Requirements: R20.4, Phase 0 exit gate_
    - _Test: the report exists with every section; `make check` green on `main`_
  - [x] 17.2 **Owner:** sign off Phase 0 → the `mvp-x-or-y` spec may start
    - _Requirements: Phase gate (`quality.md`)_
    - _Test: sign-off recorded in the phase report_
