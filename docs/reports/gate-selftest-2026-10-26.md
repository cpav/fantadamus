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
