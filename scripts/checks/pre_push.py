"""The pre-push gate: secrets and FantaCreator identities in every outgoing commit (R9.6).

pre-commit runs this at the pre-push stage with PRE_COMMIT_FROM_REF and PRE_COMMIT_TO_REF set. In a
public repository this is the preventive gate; CI repeats the scan, but by then the commit is visible.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from scripts.checks import identities, secrets
from scripts.checks._common import report

ROOT = Path(__file__).resolve().parents[2]


def log_opts(from_ref: str, to_ref: str) -> str:
    """The git log range being pushed; a new branch (all-zero from_ref) is everything not yet on a remote."""
    if not from_ref or set(from_ref) == {"0"}:
        return f"{to_ref} --not --remotes"
    return f"{from_ref}..{to_ref}"


def main(env: Mapping[str, str] | None = None, repo: Path | None = None) -> int:
    env = os.environ if env is None else env
    repo = repo or ROOT
    from_ref, to_ref = env.get("PRE_COMMIT_FROM_REF", ""), env.get("PRE_COMMIT_TO_REF", "")
    if not to_ref:
        return 0
    opts = log_opts(from_ref, to_ref)
    secret_code = report(secrets.check(secrets.Mode.RANGE, log_opts=opts, repo=repo))
    lines = identities.range_lines(opts, repo)
    identity_code = report(identities.check_lines(lines, env=env, config=identities.config_path(env)))
    return max(secret_code, identity_code)


if __name__ == "__main__":
    raise SystemExit(main())
