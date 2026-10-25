"""Scan for secrets with the pinned gitleaks: staged files, a commit range or all history (R10.1, R10.2).

Findings are redacted and reported as rule, commit and location only.

Usage: python -m scripts.checks.secrets (--staged | --history | --range LOG_OPTS)
"""

from __future__ import annotations

import argparse
import enum
import json
from collections.abc import Sequence
from pathlib import Path

from scripts.checks._common import CheckResult, Runner, report, run_command

__all__ = ["Mode", "Runner", "check"]

ROOT = Path(__file__).resolve().parents[2]


class Mode(enum.Enum):
    STAGED = "staged"
    HISTORY = "history"
    RANGE = "range"


def _command(mode: Mode, log_opts: str, root: Path, repo: Path) -> list[str]:
    command = [str(root / "bin" / "gitleaks"), "git", "--redact", "--no-banner"]
    command += ["--config", str(root / ".gitleaks.toml"), "--report-format", "json", "--report-path", "-"]
    if mode is Mode.STAGED:
        command += ["--pre-commit", "--staged"]
    elif mode is Mode.RANGE:
        command += ["--log-opts", log_opts]
    return [*command, str(repo)]


def _describe(finding: dict[str, object]) -> str:
    commit = str(finding.get("Commit") or "")[:12]
    where = f"{finding.get('File')}:{finding.get('StartLine')}"
    return f"{finding.get('RuleID')} at {commit + ' ' if commit else ''}{where}"


def check(
    mode: Mode, log_opts: str = "", run: Runner = run_command, root: Path = ROOT, repo: Path | None = None
) -> CheckResult:
    completed = run(_command(mode, log_opts, root, repo or root))
    if completed.returncode == 0:
        return CheckResult("secrets", ok=True)
    if completed.returncode == 1:
        findings = json.loads(completed.stdout or "[]")
        found = ", ".join(_describe(finding) for finding in findings) or "see gitleaks output"
        return CheckResult("secrets", ok=False, message=f"secrets found (redacted): {found}")
    detail = (completed.stderr or completed.stdout).strip().splitlines()
    reason = detail[0] if detail else "no output; run `make setup` to install the pinned gitleaks"
    return CheckResult(
        "secrets", ok=False, message=f"gitleaks failed (exit {completed.returncode}): {reason}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true")
    group.add_argument("--history", action="store_true")
    group.add_argument("--range", metavar="LOG_OPTS")
    args = parser.parse_args(argv)
    if args.staged:
        return report(check(Mode.STAGED))
    if args.history:
        return report(check(Mode.HISTORY))
    return report(check(Mode.RANGE, log_opts=args.range))


if __name__ == "__main__":
    raise SystemExit(main())
