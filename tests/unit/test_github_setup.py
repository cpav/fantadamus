"""Task 13.4: the GitHub settings the gates rely on, as a checklist for the go-ahead (R2.12)."""

from __future__ import annotations

from pathlib import Path

import pytest

CHECKLIST = Path(__file__).resolve().parents[2] / "docs" / "runbooks" / "github-setup.md"

SETTINGS = [
    "Restrict deletions",
    "Block force pushes",
    "Require a pull request before merging",
    "Allowed merge methods: Squash",
    "Require status checks to pass",
    "Require branches to be up to date before merging",
    "`check`",
    "`pr`",
    "Bypass list: empty",
    "Secret scanning",
    "Push protection",
    "Require approval for all outside collaborators",
    "`FANTADAMUS_CREATOR_IDENTITIES`",
    "Dependabot secrets",
]


@pytest.mark.parametrize("setting", SETTINGS)
def test_checklist_covers_each_setting(setting: str) -> None:
    assert setting in CHECKLIST.read_text(encoding="utf-8")
