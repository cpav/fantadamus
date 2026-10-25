"""Lint the GitHub Actions workflows with the pinned actionlint (R4.4); passes while there are none."""

from __future__ import annotations

from pathlib import Path

from scripts.checks._common import CheckResult, Runner, report, run_command

ROOT = Path(__file__).resolve().parents[2]


def check(root: Path = ROOT, run: Runner = run_command) -> CheckResult:
    workflows = root / ".github" / "workflows"
    files = sorted(workflows.glob("*.y*ml")) if workflows.is_dir() else []
    if not files:
        return CheckResult("actions", ok=True, message="no workflows yet")
    completed = run([str(root / "bin" / "actionlint"), *(str(f) for f in files)])
    if completed.returncode == 0:
        return CheckResult("actions", ok=True)
    output = (completed.stdout + completed.stderr).strip()
    return CheckResult("actions", ok=False, message=output or "actionlint failed")


if __name__ == "__main__":
    raise SystemExit(report(check()))
