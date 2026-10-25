"""Run a group of checks, keep going past failures, and print one PASS/FAIL line per check (R1.1 to R1.3).

`make check` runs the group `all`, which is exactly static + tests + infra + audit; CI runs those four as
parallel jobs (R1.2). Every check gets the thorough Hypothesis profile and no AWS credentials (R1.6, R7.3).

Usage: python -m scripts.checks.run_all {all,static,tests,infra,audit}
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

UV = ("uv", "run", "--frozen")
AWS_BLOCKERS = {"AWS_CONFIG_FILE": "/dev/null", "AWS_SHARED_CREDENTIALS_FILE": "/dev/null"}

Runner = Callable[[Sequence[str], dict[str, str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]


def _module(name: str, *args: str) -> tuple[str, ...]:
    return (*UV, "python", "-m", f"scripts.checks.{name}", *args)


STATIC = [
    Check("lockfile", _module("lockfile")),
    Check("tool-versions", _module("tool_versions")),
    Check("format", (*UV, "ruff", "format", "--check", ".")),
    Check("lint", (*UV, "ruff", "check", ".")),
    Check("types", (*UV, "mypy")),
    Check("yaml", (*UV, "yamllint", "--strict", ".")),
    Check("sql", (*UV, "sqlfluff", "lint", ".")),
    Check("markdown", (*UV, "pre-commit", "run", "markdownlint-cli2", "--all-files")),
    Check("actions", _module("actions")),
    Check("suppressions", _module("suppressions")),
    Check("thresholds", _module("thresholds")),
    Check("adr-lint", _module("adr_lint")),
    Check("identities", _module("identities", "--tree")),
    Check("secrets", _module("secrets", "--history")),
]
TESTS = [
    Check("tests", (*UV, "pytest", "--cov", "--cov-report=json", "--cov-report=term")),
    Check("coverage", _module("coverage_gate")),
]
INFRA: list[Check] = []  # Terraform checks and the IAM policy evaluator arrive with task 11.
AUDIT = [Check("audit", _module("audit"))]

GROUPS: dict[str, list[Check]] = {
    "static": STATIC,
    "tests": TESTS,
    "infra": INFRA,
    "audit": AUDIT,
    "all": [*STATIC, *TESTS, *INFRA, *AUDIT],
}


def check_env(base: Mapping[str, str]) -> dict[str, str]:
    """The environment for checks: no AWS credentials or profiles, and the `ci` Hypothesis profile."""
    env = {key: value for key, value in base.items() if not key.startswith("AWS_")}
    env.update(AWS_BLOCKERS)
    env["HYPOTHESIS_PROFILE"] = "ci"
    return env


def _run(command: Sequence[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run with output streaming to the terminal, so long checks show progress."""
    return subprocess.run(list(command), env=env, check=False, text=True)  # noqa: S603  # reason: fixed commands defined in this module


def run_checks(checks: Sequence[Check], run: Runner = _run, env: dict[str, str] | None = None) -> int:
    env = check_env(os.environ) if env is None else env
    results: list[tuple[str, bool]] = []
    for check in checks:
        print(f"==> {check.name}", flush=True)
        completed = run(check.command, env)
        for stream, text in ((sys.stdout, completed.stdout), (sys.stderr, completed.stderr)):
            if text:
                print(text, end="", file=stream)
        results.append((check.name, completed.returncode == 0))
    if not checks:
        print("nothing to check in this group yet")
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    failed = sum(1 for _, ok in results if not ok)
    print(f"{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in GROUPS:
        print(f"usage: python -m scripts.checks.run_all {{{','.join(GROUPS)}}}", file=sys.stderr)
        return 2
    return run_checks(GROUPS[args[0]])


if __name__ == "__main__":
    raise SystemExit(main())
