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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from scripts.checks._common import run_command

UV = ("uv", "run", "--frozen")
# The test suite uses every core, and the coverage gate reads what it wrote: these two run on their own,
# after the other checks have run side by side, a few at a time.
ALONE = {"tests", "coverage"}
PARALLEL = 4
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
    Check("contracts", _module("contracts")),
    Check("hook-config", _module("hook_config")),
    Check("identities", _module("identities", "--tree")),
    Check("secrets", _module("secrets", "--history")),
]
TESTS = [
    Check(
        "tests",
        (*UV, "pytest", "-n", "4", "--dist", "worksteal", "--cov", "--cov-report=json", "--cov-report=term"),
    ),
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


def _capture(command: Sequence[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run with output captured, for checks that run side by side."""
    return run_command(command, env=env)


def _print(completed: subprocess.CompletedProcess[str]) -> None:
    for stream, text in ((sys.stdout, completed.stdout), (sys.stderr, completed.stderr)):
        if text:
            print(text, end="", file=stream, flush=True)


def run_checks(
    checks: Sequence[Check], run: Runner = _run, env: dict[str, str] | None = None, capture: Runner = _capture
) -> int:
    """Run the quick checks side by side, then the test suite on its own; report every check in order."""
    env = check_env(os.environ) if env is None else env
    results: dict[str, bool] = {}
    quick = [check for check in checks if check.name not in ALONE]
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        futures = {check.name: pool.submit(capture, check.command, env) for check in quick}
        for check in quick:
            completed = futures[check.name].result()
            print(f"==> {check.name}", flush=True)
            _print(completed)
            results[check.name] = completed.returncode == 0
    for check in checks:
        if check.name in ALONE:
            print(f"==> {check.name}", flush=True)
            completed = run(check.command, env)
            _print(completed)
            results[check.name] = completed.returncode == 0
    if not checks:
        print("nothing to check in this group yet")
    for check in checks:
        print(f"{'PASS' if results[check.name] else 'FAIL'} {check.name}")
    failed = sum(1 for ok in results.values() if not ok)
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
