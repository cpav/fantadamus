# Gate report, 2026-10-26: the local gate

Every gate that can be proved on the owner's machine, each fed a bad input (R20.1, R20.4).

- **How it ran:** `uv run pytest tests/acceptance` on branch `test/ef-14-local-gate`, in temporary
  directories and throwaway git repositories, never in this repository.
- **Results:** 14 passed in 14 s. The full `make check` is green.
- **Hooks:** the agent hooks' live check is in [the 2026-10-25 report](gate-selftest-2026-10-25.md).

| AT | Gate | Bad input | Expected | Observed |
|---|---|---|---|---|
| AT-1 | ruff format and ruff check (`make check`, pre-commit) | A badly formatted file; an unused import | Both fail | `format --check` exits 1; `check` exits 1 (F401); a clean file passes both |
| AT-2 | mypy `--strict` | A function returning text where it promises a number | Fails | Exit 1: "Incompatible return value type" |
| AT-4 | gitleaks on staged files (pre-commit), then the pre-push hook | A fake AWS access key | Rejected, value hidden | "secrets found (redacted)", no key in the message; pre-push exits 1 |
| AT-5 | Coverage gate | 85 % of lines, then 85 % of branches | Each fails | Both fail; 95 % and 95 % pass |
| AT-7 | Walking skeleton | A submission from a host off the allowlist | Rejected, nothing written | As expected; the whole run under 10 s |
| AT-8 | Agent hooks | A push, deploys, a private-configuration write, a red check | Blocked or returned to the agent | As expected, through the hook commands as wired |
| AT-12 | FantaCreator identity check (pre-commit, pre-push) | An invented identity, in capitals, in a staged file | Rejected, location only | "identity found at notes.md:3"; pre-push exits 1; the name appears nowhere in the output |
| AT-13 | Commit messages (commit-msg hook; PR titles in CI) | "fixed the thing", "feat:missing space" | Rejected | Both rejected; "feat(ef): add the gate proofs" accepted |
| AT-14 | Contract versioning | A schema change without a version bump; a field removal with only a minor bump | Both fail | "schema changed without a version bump"; "breaking change needs a major bump … $.shirt: removed" |
| AT-15 | Suppression lint | A blanket `noqa`, a bare `type: ignore`, an unexplained skip, a register row with no approval date | Each fails | All four reported, each with its file and line |
| AT-16 | Threshold ratchet | Coverage 90 → 80, examples 500 → 100, CI budget 5 → 9 minutes | Each fails | Three issues |
| AT-17 | Dependency audit (real pip-audit, network) | `jinja2==2.10` | Fails; passes with a valid allowlist entry; fails when it has expired | As expected |

Still to come:

- **The remote parts (task 15):** CI for AT-1, AT-2, AT-4, AT-5, AT-13, AT-14, AT-16 and AT-17, and the
  checklist for AT-3, AT-9, AT-11 and AT-19.
- **Moved to Phase 3:** AT-6, AT-10, AT-18, AT-20 and AT-21.

Owner's review (task 14.3): accepted on 2026-10-26. **Local gate passed.**

## The remote gate (task 15.1 and 15.2)

The repository went public as <https://github.com/cpav/fantadamus> on 2026-10-26.

- **The push:** the pre-push hook scanned every commit for secrets and identities first, and passed.
- **CI on `main`:** the first run passed; the `check` job took 64 s on `ubuntu-latest`.
- **Settings:** compared with `docs/runbooks/github-setup.md` through the GitHub API, read-only.

| Setting | Live value |
|---|---|
| Visibility | Public |
| Merge methods | Squash only; head branches deleted on merge |
| Ruleset `main` | Active on the default branch, empty bypass list; deletion and force-push blocked; pull request required (0 approvals, squash only); required checks `check` and `pr`, strict |
| Secret scanning, push protection | Both enabled |
| Workflows from fork pull requests | Approval required for all external contributors |
| Workflow token | Read-only |
| `FANTADAMUS_CREATOR_IDENTITIES` | Set for Actions and for Dependabot (a placeholder until the creators are chosen) |

| AT | Gate | Bad change | Expected | Observed |
|---|---|---|---|---|
| AT-3 | Required checks | PR #2, with a planted failing test | `check` red, merge blocked | `check` failed on the planted test alone ("18 passed, 1 failed"); merge state BLOCKED |
| AT-13 (remote) | Pull-request title | PR #2, titled "Gate probe: failing test and bad title" | `pr` red | `pr` failed at the title step |
| AT-4 (remote) | Push protection | None pushed | Enabled | Enabled, read from the settings; the CI scan is the same gitleaks command proved locally |
| AT-11 | Direct and force pushes to `main` | None attempted | Refused | Proved by the live ruleset: pull request required, force-push blocked, no bypass. The owner decided against a live push |

- **The probe:** PR #2 was closed and its branch deleted after the result was recorded.
- **The first real pull request:** PR #1 (the hook fix) passed `check` and `pr`, and its merge state was CLEAN.
- **Found on the way:** the pre-push hook needed `uv` on the PATH, and failed closed without it. PR #1 fixes
  this; the hooks now run from the project's `.venv`.

### Task 15.3: CI time and Dependabot

The CI runs so far, from start to finish (AT-9; budget: median under 5 minutes, none over 8):

| Run | Event | Result | Time |
|---|---|---|---|
| First push of `main` | push | success | 68 s |
| PR #1, first commit | pull request | success | 78 s |
| PR #2, the probe | pull request | failure, as intended | 61 s |
| PR #1, evidence commit | pull request | success | 79 s |

The median is under 80 seconds, so AT-9 is met with a wide margin; the owner closed 15.3 on these runs.
The first Dependabot pull request (AT-19) hasn't arrived yet, since Dependabot runs weekly. It stays a
follow-up: when it comes, check that it passes the identity check with the Dependabot secret.

Owner's review (task 15.4): accepted on 2026-10-26. **Remote gate passed.**
