"""Task 3.4: task 1's repository rules as tests (R2.1, R2.8, R2.10, R21.1, R6.3)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

MUST_BE_IGNORED = [
    "private.toml",
    "config.private.toml",
    ".env",
    ".env.local",
    "data/private/rosters.csv",
    "data/local/lake/bronze/x.parquet",
    "bin/terraform",
    "infra/bootstrap/terraform.tfstate",
    "infra/bootstrap/terraform.tfstate.backup",
    "infra/stack/.terraform/providers/x",
    "plan.tfplan",
    ".claude/settings.local.json",
    ".claude/launch.json",
]
MUST_BE_TRACKABLE = [
    ".terraform.lock.hcl",
    "infra/bootstrap/.terraform.lock.hcl",
    "private.example.toml",
    ".claude/settings.json",
]


def _ignored(path: str) -> bool:
    completed = subprocess.run(  # noqa: S603  # reason: fixed git command with test-defined paths
        ["git", "check-ignore", "--no-index", "-q", path],  # noqa: S607  # reason: git is resolved from PATH like in every developer shell
        cwd=ROOT,
        check=False,
    )
    return completed.returncode == 0


@pytest.mark.parametrize("path", MUST_BE_IGNORED)
def test_private_paths_ignored(path: str) -> None:
    assert _ignored(path), f"{path} must be git-ignored"


@pytest.mark.parametrize("path", MUST_BE_TRACKABLE)
def test_committed_paths_not_ignored(path: str) -> None:
    assert not _ignored(path), f"{path} must stay committable"


def test_readme_states_no_licence() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "No licence is granted. All rights reserved." in readme


def test_pr_template_fields() -> None:
    template = (ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    for field in ("**Task:**", "**Requirements:**", "**Tests:**", "**ADRs:**", "## Definition of Done"):
        assert field in template, f"PR template lacks {field}"


def test_suppression_register_columns() -> None:
    register = (ROOT / "docs" / "quality" / "suppressions.md").read_text(encoding="utf-8")
    assert "| ID | Path | Rule | Reason | Approved |" in register


def test_leak_runbook_sections() -> None:
    runbook = (ROOT / "docs" / "runbooks" / "leak.md").read_text(encoding="utf-8")
    for heading in (
        "## A secret reached GitHub",
        "## A FantaCreator identity reached GitHub",
        "## Afterwards",
    ):
        assert heading in runbook, f"leak runbook lacks {heading}"
    assert "rotate" in runbook.casefold()
