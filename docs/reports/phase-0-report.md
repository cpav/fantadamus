# Phase 0 report: engineering foundation

2026-10-26 · Spec `engineering-foundation` · Owner's sign-off: pending (task 17.2)

## What Phase 0 delivered

Everything that keeps the repository honest is built and proved:

- **The project:** Python with pinned, locked tools.
- **One `make check`:** the same locally and in CI.
- **Git hooks:** pre-commit, commit message and pre-push.
- **Guards against leaks:** secret and FantaCreator-identity checks.
- **Data contracts with versions.**
- **The walking skeleton:** a synthetic fixture through the MCP tools, bronze, silver and gold.
- **Claude Code hooks.**
- **CI on a public GitHub repository** with a protected `main`.

The AWS skeleton (bootstrap, stack, budget alarm, first deploy) moved to Phase 3 in the
[2026-10-26 re-plan](../../.kiro/specs/engineering-foundation/replan-2026-10-26.md). It will be built when the
online server needs it.

## Numbers

| Measure | Value |
|---|---|
| Tests | 408, written before the code they test |
| Coverage | 98.0 % of lines and 94.5 % of branches; the floor is 90 % and only goes up |
| `make check` (19 checks) | 77 s on the owner's Intel Mac, about 135 s before the speed-up |
| `make test-fast` (end of each agent turn) | 18 s |
| CI per pull request | 61 to 79 s, against a 5-minute budget |
| Code | 977 lines of product code, 2,529 of checks and hooks, 4,358 of tests |

## Gates

| Gate | Result | Evidence |
|---|---|---|
| Local gate: every local acceptance test fails on its bad input | Passed, accepted 2026-10-26 | [gate report](gate-selftest-2026-10-26.md) |
| Remote gate: settings, required checks, PR title, push protection, protected `main` | Passed, accepted 2026-10-26 | [gate report](gate-selftest-2026-10-26.md), remote section |
| Agent hooks, live in Claude Code | Passed after one fix | [hook report](gate-selftest-2026-10-25.md) |

## Cost

$0. No AWS resources exist yet, and GitHub Actions is free for a public repository.

## Decisions taken in Phase 0

- **ADR-0001, tool choices:** accepted, with three amendments:
  - workarounds for the Intel Mac;
  - the live hook contract;
  - two test plugins added for speed.
- **ADR-0005, collector mode:** accepted. Each player's Claude collects the facts; the Fantadamus tools check
  them, store them and decide.
- **The re-plan (2026-10-26):**
  - the AWS work moves to Phase 3;
  - CI is one job;
  - GitHub settings are a checklist, not code;
  - the next phase is one thin slice, "X or Y?" for forwards.
- **cryptography on the Intel Mac:** the owner accepted the risk (option B). It is renewed every three
  months; the next review is due by 2027-01-26.

## Open risks and follow-ups

1. **No creator names yet.** The identity check protects nothing until the real FantaCreator names replace the
   placeholder, in the Actions secret, the Dependabot secret and the private configuration.
2. **The first Dependabot pull request (AT-19) hasn't arrived.** When it does, check that it passes the
   identity check.
3. **The Intel Mac is losing pre-built packages.** cryptography's three known flaws are accepted until
   2027-01-26, and mutmut and libcst are pinned to older versions. An Apple Silicon Mac would remove all
   three.
4. **One end-of-turn check ran 13 minutes once,** on 2026-10-25, and the cause is unknown. A hang now names
   the test and is stopped within 2 minutes, so a repeat would be diagnosed.
5. **The presentation pages show 25 October figures.** Refresh them before sharing.
6. **Mutation testing** waits until Phase 2, when there is football logic to test this way.

## Next

Phase 1 is the `mvp-x-or-y` spec: "X or Y?" for two forwards, answered in the owner's Claude Desktop. It
covers the facts that question needs, the method for forwards, and the `compare_players` tool. Its
requirements come first, for the owner's approval.
