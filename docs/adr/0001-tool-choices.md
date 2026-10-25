# ADR-0001: Tool choices for the engineering foundation

- **Status:** Accepted by the owner, 2026-10-24
- **Deciders:** the owner
- **Specs affected:** `engineering-foundation` (all later specs inherit the toolchain)

## Context

Spec 0 needs one toolchain for formatting, linting, types, tests, coverage, secrets, dependency
security, infrastructure checks, commit messages, dependency updates and agent hooks (requirements R1–R13,
R17). The constraints:

- Python 3.12 with uv; the same `make check` locally and in CI.
- A **public** repository, so no paid tools and no tool whose licence restricts our use.
- The owner's **Intel Mac** and GitHub's Linux runners. gamegusto showed that pre-commit's isolated
  environments can't build some packages on that Mac (`cryptography`), so hooks that need the project's
  dependencies must run in the project environment.
- **Claude Code** is the only agent (Kiro dropped 2026-10-24).

Licences below were read on 2026-10-24 from each project's repository (GitHub's licence API, or the
licence file where GitHub reports `NOASSERTION`). "Latest" is the newest release or tag on that date.
Python versions are fixed in `uv.lock` and binary versions in `tool-versions.toml` at task 3; the
versions here are the starting point, not a promise.

## Options

Only the choices with a real alternative are listed; for the rest there was one clear option.

| Area | Options | Notes |
|---|---|---|
| Commit-message check | **conventional-pre-commit** (Apache-2.0, v4.4.0) vs commitizen (MIT, v4.19.3) | We only need the check. commitizen also bumps versions and writes changelogs, and pulls a larger dependency tree into the audit surface. The PR-title check (R9.5) reuses the same Conventional Commits pattern in `pr_meta`. |
| Dependency updates | **Dependabot** vs Renovate (AGPL-3.0 when self-hosted, or an installed app) | GitHub's docs list `uv`, `pre-commit` (version updates) and `github-actions` as supported Dependabot ecosystems. Dependabot is built in and needs no app installation. |
| Async test runner (MCP tests) | **anyio's pytest plugin** (MIT, 4.15.1) vs pytest-asyncio | The MCP SDK is built on anyio, and its own testing guide uses `pytest.mark.anyio`; anyio is already a dependency, so this adds nothing. |
| Network blocking in tests | **pytest-socket** (MIT, 0.8.1) vs a hand-written socket patch | A maintained plugin with per-test and per-directory control (R7.4). |
| Installing Terraform, tflint, gitleaks, actionlint | **Our installer** (`scripts/tools/install.py`, stdlib, SHA-256 verified) vs mise, asdf or aqua | One small script; no extra tool on the owner's Mac or in CI. aqua would also verify checksums, but is one more moving part (R1.8). |
| mypy in pre-commit | **Local hook in the project environment** (`uv run mypy`) vs the `mirrors-mypy` hook | The mirrors hook runs in an isolated environment, which failed for gamegusto on this Mac. A local hook sees exactly the dependencies `make check` sees. |
| Secret scanning | **gitleaks CLI** (MIT, v8.30.1) vs the `gitleaks-action` wrapper | The CLI needs no licence key and runs identically in pre-commit, pre-push and CI (R10). |

## Decision

| Purpose | Tool | Licence | Latest on 2026-10-24 | Pinned in |
|---|---|---|---|---|
| Python, dependencies, lockfile | uv | Apache-2.0 | 0.13.5 | CI setup; `.python-version` for Python 3.12 |
| Format and lint | ruff (`B`, `S`, `PGH`, `RUF` among its rules) | MIT | 0.17.2 | `uv.lock`, pre-commit `rev` |
| Types | mypy (`--strict`) | MIT | v2.4.0 | `uv.lock`; local pre-commit hook |
| Tests, coverage | pytest, pytest-cov | MIT, MIT | 9.1.1, v7.1.0 | `uv.lock` |
| Network blocking | pytest-socket | MIT | 0.8.1 | `uv.lock` |
| Property-based tests | Hypothesis | MPL-2.0 | v6.170.9 | `uv.lock` |
| Async tests | anyio pytest plugin | MIT | 4.15.1 | `uv.lock` |
| Contracts | pydantic v2 | MIT | v2.14.1 | `uv.lock` |
| Local lake | DuckDB | MIT | v2.0.0 (released 2026-10-21) | `uv.lock` |
| MCP server and test client | MCP Python SDK (`mcp`), **v2 API** | MIT | v2.3.0 | `uv.lock` |
| AWS mocks, AWS client | moto, boto3 | Apache-2.0, Apache-2.0 | 5.2.4, at lock time | `uv.lock` |
| SQL, YAML lint | sqlfluff, yamllint | MIT, GPL-3.0 | 4.4.0, v1.38.0 | `uv.lock` (yamllint is a dev tool only; it isn't distributed with our code) |
| Markdown lint | markdownlint-cli2 (Node, via pre-commit) | MIT | v0.24.0 | pre-commit `rev` |
| Workflow lint | actionlint | MIT | v1.7.12 | `tool-versions.toml` |
| Git hooks | pre-commit, pre-commit-hooks | MIT, MIT | v4.7.0, v6.0.0 | `uv.lock`, pre-commit `rev` |
| Commit messages | conventional-pre-commit | Apache-2.0 | v4.4.0 | pre-commit `rev` |
| Secrets | gitleaks CLI | MIT | v8.30.1 | `tool-versions.toml` |
| Dependency audit | pip-audit | Apache-2.0 | v2.10.1 | `uv.lock` |
| Mutation testing | mutmut | BSD-3-Clause | 3.8.0 | `uv.lock` |
| IaC (if ADR-0002 confirms Terraform) | Terraform, tflint, checkov | BUSL-1.1, MPL-2.0, Apache-2.0 | v1.17.0, v0.65.0, 3.3.30 | `tool-versions.toml` (Terraform, tflint); `uv.lock` (checkov) |
| Dependency updates | Dependabot: `uv`, `github-actions`, `pre-commit` | GitHub feature | — | `.github/dependabot.yml` |

**Claude Code hook contract** (R17.8), from the official hooks reference; confirmed live in task 9.7:

- Hooks live in `.claude/settings.json` as event → matcher group → handlers
  (`{"type": "command", "command": …, "timeout": …}`). Commands can use `${CLAUDE_PROJECT_DIR}`, and the
  same value arrives as the `CLAUDE_PROJECT_DIR` environment variable.
- Every event arrives as JSON on stdin, with `session_id`, `transcript_path`, `cwd`, `permission_mode` and
  `hook_event_name`.
  - `PreToolUse` adds `tool_name`, `tool_input` (for Bash: `command`; for Write and Edit: an absolute
    `file_path`) and `tool_use_id`.
  - `PostToolUse` adds `tool_input` and `tool_response`.
  - `Stop` adds `stop_hook_active`.
- **Exit codes:**
  - **0** means success.
  - **2** blocks `PreToolUse` and keeps `Stop` from ending the turn, and feeds stderr back to Claude. A JSON
    `decision: "block"` with a `reason` does the same.
  - **Any other code** is a non-blocking error that the user sees, so enforcing hooks must use exit 2,
    never exit 1.
- The default timeout for command hooks is 600 seconds. Edits to hooks in settings files are picked up
  automatically.
- Example payloads in this shape are committed as fixtures in `tests/fixtures/hooks/` (task 2.2).

## Consequences

- **The design changes** in three places, made in the same branch as this ADR:
  - conventional-pre-commit instead of commitizen;
  - anyio's pytest plugin instead of pytest-asyncio;
  - the MCP SDK's v2 API: `MCPServer` (from `mcp.server.mcpserver`, formerly `FastMCP`), tested in memory
    with `mcp.Client(server, raise_exceptions=True)` under `pytest.mark.anyio`. The v1 helper the design
    cited is gone in v2.
- **DuckDB 2.0 is three days old.** We start on it, since the skeleton only writes and reads Parquet. If its
  tests turn up a regression, we pin `duckdb<2` and record it here.
- **Terraform's licence** (BUSL-1.1) permits our use: it restricts only offering Terraform as a competing
  hosted product. OpenTofu (MPL-2.0) stays the drop-in fallback; ADR-0002 decides IaC itself.
- **Dependabot** can't raise security alerts for pre-commit hooks, only weekly version updates. Hook
  revisions are pinned, and gitleaks and actionlint are covered by `tool-versions.toml` instead.
- **Every tool is free.** Nothing here needs the owner's approval as a paid service.

## Amendments

**2026-10-24, task 3 (Intel-Mac wheels and a dependency conflict).** Found while locking the project; for
the owner's review with task 3:

- **checkov runs isolated** through `uvx --from checkov==3.3.30 checkov`, pinned in `tool-versions.toml`
  rather than `uv.lock`, because checkov pins `boto3==1.35.49`, which conflicts with current boto3 and
  moto.
- **mutmut 3.7** instead of 3.8, with `libcst<1.9`: mutmut 3.8 needs libcst 1.9, which ships no macOS
  x86_64 wheel for Python 3.12, so installing it on the owner's Intel Mac would need a Rust toolchain.
- **`cryptography<49` on Intel Macs only** (pulled in by moto and mcp), for the same reason: 49 and later
  ship no macOS x86_64 wheel. *Revised 2026-10-25 (task 7):* the dependency audit found three advisories
  in 48.0.1 (PYSEC-2026-3552, -3553, -3554, fixed in 49 and 50), so the constraint is now limited to
  `sys_platform == 'darwin' and platform_machine == 'x86_64'`, and every other platform is held to
  `cryptography>=50`. CI and Linux servers get the fix; the Intel Mac keeps 48.0.1 under three
  allowlist entries expiring 2026-11-30 (register rows S-010 to S-012).

These are `[tool.uv] constraint-dependencies` in `pyproject.toml`, each with a comment. They are reviewed
whenever the dependency audit flags one of these packages, and lifted once wheels return or the owner moves
off the Intel Mac.

**2026-10-25, task 9.7 (the hook contract, confirmed live).** For the owner's review with task 9. The
evidence is in [the gate self-test report](../reports/gate-selftest-2026-10-25.md).

- **Confirmed:** the payload fields above, the exit codes (2 blocks `PreToolUse`, returns stderr after
  `PostToolUse`, and keeps `Stop` from ending the turn), and that edits to `.claude/settings.json` are
  picked up during a session, from the next tool call on.
- **Extra fields:** live payloads also carry `effort`, `prompt_id` and `scratchpad_dir`; `PostToolUse` adds
  `duration_ms`, and `Stop` adds `background_tasks`, `last_assistant_message` and `session_crons`. The
  parser keeps unknown fields, so the hooks don't depend on them.
- **Timeouts:** a hook that runs past its `timeout` is cancelled, and a cancelled `Stop` hook ends the turn
  with no feedback to the agent. A hook with a long job therefore stops it itself, before its own timeout,
  and reports the failure.

## Sources

- Each tool's repository and licence file, read through the GitHub API on 2026-10-24:
  [uv](https://github.com/astral-sh/uv), [ruff](https://github.com/astral-sh/ruff),
  [mypy](https://github.com/python/mypy), [pytest](https://github.com/pytest-dev/pytest),
  [pytest-cov](https://github.com/pytest-dev/pytest-cov), [pytest-socket](https://github.com/miketheman/pytest-socket),
  [Hypothesis](https://github.com/HypothesisWorks/hypothesis), [anyio](https://github.com/agronholm/anyio),
  [pydantic](https://github.com/pydantic/pydantic), [DuckDB](https://github.com/duckdb/duckdb),
  [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [moto](https://github.com/getmoto/moto),
  [sqlfluff](https://github.com/sqlfluff/sqlfluff), [yamllint](https://github.com/adrienverge/yamllint),
  [markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2), [actionlint](https://github.com/rhysd/actionlint),
  [pre-commit](https://github.com/pre-commit/pre-commit), [pre-commit-hooks](https://github.com/pre-commit/pre-commit-hooks),
  [conventional-pre-commit](https://github.com/compilerla/conventional-pre-commit),
  [commitizen](https://github.com/commitizen-tools/commitizen), [gitleaks](https://github.com/gitleaks/gitleaks),
  [pip-audit](https://github.com/pypa/pip-audit), [mutmut](https://github.com/boxed/mutmut),
  [Terraform](https://github.com/hashicorp/terraform), [tflint](https://github.com/terraform-linters/tflint),
  [checkov](https://github.com/bridgecrewio/checkov), [Renovate](https://github.com/renovatebot/renovate)
- GitHub Docs, [Supported ecosystems and repositories (Dependabot)](https://docs.github.com/en/code-security/dependabot/ecosystems-supported-by-dependabot/supported-ecosystems-and-repositories)
- Claude Code, [Hooks reference](https://code.claude.com/docs/en/hooks)
- MCP Python SDK, [testing guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/get-started/testing.md)
  and [v1 → v2 migration guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/migration.md)
- anyio, [testing with anyio](https://anyio.readthedocs.io/en/stable/testing.html)
- The owner's gamegusto project: its pre-commit mypy hook failed in an isolated environment on the Intel Mac
