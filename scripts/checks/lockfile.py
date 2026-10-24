"""Fail when uv.lock is out of date with pyproject.toml (R3.4)."""

from __future__ import annotations

from scripts.checks._common import CheckResult, Runner, report, run_command

__all__ = ["Runner", "check"]


def check(run: Runner = run_command) -> CheckResult:
    """Run `uv lock --check`, which exits non-zero when the lockfile needs updating."""
    completed = run(["uv", "lock", "--check"])
    if completed.returncode == 0:
        return CheckResult("lockfile", ok=True)
    detail = (completed.stderr or completed.stdout).strip().splitlines()
    reason = detail[0] if detail else "uv.lock is out of date"
    return CheckResult("lockfile", ok=False, message=f"{reason}; run `uv lock` and commit uv.lock")


if __name__ == "__main__":
    raise SystemExit(report(check()))
