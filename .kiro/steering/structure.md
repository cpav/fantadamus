---
inclusion: always
---

# Structure and working agreements

## Repository layout

Target layout. Directories appear as the task that needs them lands; nothing is created ahead of its spec.

```text
.kiro/                 spec documents in Kiro's layout (Kiro itself isn't used)
  steering/            product.md, tech.md, structure.md, quality.md
  specs/<spec>/        requirements.md, design.md, tasks.md
.github/
  workflows/           ci.yml (PR gate), audit.yml (weekly), …
  rulesets/main.json   the `main` branch ruleset as code, applied through the GitHub API
  pull_request_template.md   Definition of Done checklist
  dependabot.yml       (or renovate.json; ADR-0001)
docs/
  method.md            the decision method (implemented by decision-engine; tests from §A9)
  agent-prompt.md      the chat agent's system prompt (delivered by the MCP server)
  adr/NNNN-<decision>.md
  reports/             task, slice and phase reports (phase reports are committed)
  quality/suppressions.md      every approved suppression, with its reason and approval date
  runbooks/leak.md     what to do if a secret or a FantaCreator identity reaches GitHub
  data-products/       catalog: one page per gold data product (owner, contract, freshness)
  source-registry.md   (Spec 1) terms of use and access route per source; the first Spec 1 work
src/fantadamus/
  core/                shared, I/O-free helpers (hashing, clock, time zones, ids)
  contracts/<domain>/  versioned pydantic models (bronze payloads, silver tables, gold products)
  domains/<domain>/    bronze.py, silver.py, gold.py: one module set per data domain
  quality/             data-quality rule definitions (defined once, rendered for DuckDB and Glue DQ)
  lake/                storage adapters: DuckDB/Parquet (MVP, local or S3), S3/Iceberg (v1)
  mcp/                 the MCP server: read tools, refresh plans and submit tools (ADR-0005)
  web/                 v1 only (ADR-0004): search client, polite fetcher, extractor
  cli/                 the `fantadamus` command line
infra/                 IaC (Terraform proposed, ADR-0002)
  bootstrap/           applied once by the owner as admin; local state (git-ignored):
                       state bucket, permissions boundary, deploy role, assume-only user, budget
  stack/               applied as fantadamus-deploy; remote state; backend config from private config
tests/
  unit/ property/ contract/ integration/ acceptance/ infra/
  fixtures/<source>/   synthetic data, or recorded payloads whose terms permit public redistribution
  golden/              reviewed outputs for golden-file tests (same redistribution rule)
data/
  private/             owner-supplied and non-redistributable data: official list, rosters,
                       recorded payloads (git-ignored)
  local/               DuckDB lake for local runs (git-ignored)
config/                thresholds.toml (gate thresholds), sources.toml (submit-tool allowlist),
                       audit-allowlist.toml (dependency-audit exceptions with expiry)
scripts/               helpers called by `make`
  checks/              one module per check (suppressions, thresholds, coverage gate, identities, …)
  hooks/               Claude Code hook logic, tested in CI
  tools/ smoke/ selftest/   tool installer, post-deploy smoke test, gate self-tests
Makefile               `make check`, `make test-fast`, `make setup`, `make bootstrap`, `make deploy`, …
tool-versions.toml     pinned versions and checksums of the non-Python tools
bin/                   project-local tools installed by `make setup` (git-ignored)
.claude/settings.json  Claude Code project hooks (thin wrappers over scripts/hooks/)
CLAUDE.md              points Claude Code to these steering files
```

### The repository is public

The GitHub repository is **public** (owner decision, 2026-10-17), so that branch protection is enforced on
GitHub Free. Everything committed is visible to everyone, forever. Therefore:

- third-party content (data files, recorded source payloads, outputs derived from them) is committed only
  where its terms permit public redistribution, and that permission is noted in the directory's README;
  everything else lives in git-ignored `data/private/`;
- no personal data about league members (names, team names, rosters) is committed;
- tests that need non-redistributable data use synthetic fixtures with the same schema.

### Private configuration

Anything that must not be in the repository lives **outside** it, at the path in `FANTADAMUS_PRIVATE_CONFIG`
(default `~/.config/fantadamus/private.toml`), and in CI as GitHub Actions secrets. This covers:
FantaCreator identities and channels, the budget-alarm e-mail address, AWS account IDs and profiles, the
Terraform backend configuration (its bucket name contains the account ID), and, from v1, API keys (Brave
Search, The Odds API, API-Football; in AWS, SSM SecureStrings under `/fantadamus/`).
The repository may contain a `private.example.toml` with placeholder values only.

## Naming

| Thing | Convention | Example |
|---|---|---|
| Python modules, functions | `snake_case` | `resolve_alias()` |
| Classes, pydantic contracts | `PascalCase`; the version is a class attribute | `class Player(Contract): __version__ = "1.0.0"` |
| Tables | `<layer>.<table>`, snake_case, plural nouns for silver | `silver.players`, `gold.availability_consensus` |
| Columns | snake_case; timestamps end in `_at` (UTC); dates end in `_date`; probabilities start with `p_` | `captured_at`, `p_start` |
| Data domains | singular lowercase | `competition`, `availability`, `performance`, `context`, `opinion`, `league` |
| ADRs | `docs/adr/NNNN-<kebab-decision>.md`, numbered in order, never renumbered | `0002-iac-cdk-vs-terraform.md` |
| Requirement IDs | `R<requirement>.<criterion>`, unique within a spec; across specs, `<spec>#R<n>.<m>` | `R3.2`, `data-foundation#R4.1` |
| Acceptance tests | `AT-<n>` per spec; test function `test_at<n>_<slug>` in `tests/acceptance/` | `test_at4_fake_aws_key_rejected` |
| Branches | `<type>/<spec-abbrev>-<task-id>-<slug>`; types `feat`, `fix`, `refactor`, `test`, `chore`, `docs`; abbreviations `ef`, `df`, `de`, `ca` | `chore/ef-1.4-test-harness` |
| Commits | Conventional Commits; the scope is the spec abbreviation or domain | `feat(availability): add consensus p_start` |
| AWS resources | Prefix `fantadamus-` (SSM paths `/fantadamus/`). **The prefix is the security boundary**: the deploy role can touch nothing else | `fantadamus-lake-<account>` |
| AWS tags | `Project=fantadamus`, `Environment`, `Spec`, `ManagedBy` (`terraform/bootstrap` or `terraform/stack`) | |

## Code conventions

- Pure functions in `core/` and in domain transforms; I/O stays at the edges (`lake/`, `cli/`, adapters).
- Time is injected (a clock parameter), never read from the wall clock inside logic, so as-of queries and
  tests are deterministic.
- Every bronze record carries the same envelope: `source`, `source_url`, `published_at` (nullable),
  `captured_at` (when the source was read), `received_at` (when the server received it), `content_sha256`,
  `contract_version` and `submitted_by` (pseudonymous). Bronze is append-only, and as-of queries use
  `captured_at`.
- Every automated source has a manual CSV fallback that writes **the same schema**.
- Code, comments, docs and identifiers are in English. Italian football terms keep their Italian names
  (ballottaggio, voti, schierabilità, pupilli) and are defined in the glossary in `product.md`.
- Answer language is a per-user setting (the owner's is English).

## Working agreements

These apply to the coding agent, Claude Code, and to the owner.

- **Spec-driven.** Steering → requirements → design → tasks, with the owner's approval at each document.
  Run an Analyze-Requirements-style review before design. Research is cited in each document.
- **Change order.** When a requirement changes mid-build: update requirements.md first, then design.md,
  then tasks.md. Never change code ahead of its spec.
- **Order of specs.** `engineering-foundation` before any pipeline code. After it, work goes in thin vertical
  slices, each a small spec taking one question from data to answer (data, then engine, then tool inside the
  slice). No phase starts before the previous one has passed its gate.
- **Smallest thing that works.** No new tooling or machinery unless a feature needs it now. A slow check is a
  defect to fix.
- **Decisions.** The agent makes small decisions itself and logs them in the task report. A report asks the
  owner for at most three decisions, each with a recommendation, in plain language. Anything this file or
  `quality.md` reserves for the owner (gates, paid services, deploys, pushes, downloads) is still asked.
- **Step by step.** One task at a time, starting with `make task-check TASK=<id>` once it exists. One
  branch and one pull request per task (local squash merges until the remote go-ahead). Post the task
  report (`quality.md`) after each task, then stop.
- **Git hygiene** (same as gamegusto). `main` is protected and always green. Stage specific files, never
  `git add -A`. Prefer new commits to amending pushed history. A PR body says what changed, why, how it was
  verified and the known gaps, under the Definition of Done checklist.
- **AWS identities.** Day-to-day Terraform runs only as `fantadamus-deploy`. Admin is used only to apply
  `infra/bootstrap/`, and only by the owner. Check `aws sts get-caller-identity` before any apply.
- **Tests first.** Write the failing test, show it failing, then implement.
- **Never weaken a gate to get to green.** Ask the owner instead. Agents may propose a suppression entry
  but leave its approval date blank; only the owner fills it in.
- **Research ends in an ADR** with its sources, approved before any code depends on it.
- **Ask before** adding any paid service, deploying anything to AWS, or scraping or downloading third-party
  content without an approved route.
- **FantaCreator identities** stay in private configuration and never appear in outputs, fixtures or logs.
- **Out of scope for v1:** trades, auctions and market valuation.
