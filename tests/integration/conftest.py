"""Fixtures for integration tests that need a real, throwaway git repository."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from scripts.checks._common import run_command

Git = Callable[..., str]


@pytest.fixture
def git_repo(tmp_path: Path) -> tuple[Path, Git]:
    """An empty git repository with a local identity, and a `git(*args)` helper that returns stdout."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> str:
        completed = run_command(["git", "-C", str(repo), *args])
        assert completed.returncode == 0, completed.stderr
        return completed.stdout

    git("init", "-q", "-b", "main")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.org")
    git("config", "commit.gpgsign", "false")
    return repo, git
