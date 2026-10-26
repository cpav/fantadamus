"""Private data can't be committed: these paths are git-ignored, shared files aren't (R2.10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.checks._common import run_command

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
    return run_command(["git", "-C", str(ROOT), "check-ignore", "--no-index", "-q", path]).returncode == 0


@pytest.mark.parametrize("path", MUST_BE_IGNORED)
def test_private_paths_ignored(path: str) -> None:
    assert _ignored(path), f"{path} must be git-ignored"


@pytest.mark.parametrize("path", MUST_BE_TRACKABLE)
def test_committed_paths_not_ignored(path: str) -> None:
    assert not _ignored(path), f"{path} must stay committable"


def test_readme_claude_desktop_setup() -> None:
    """mvp-x-or-y task 7.4 (R13.3): the README shows the Claude Desktop entry, with uv's full path."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    block = readme.split("claude_desktop_config.json", 1)[1].split("```json\n", 1)[1].split("```", 1)[0]
    server = json.loads(block)["mcpServers"]["fantadamus"]
    assert server["command"].startswith("/")
    assert server["command"].endswith("/uv")
    assert server["args"][:2] == ["--directory", "/path/to/fantadamus"]
    assert server["args"][2:] == ["run", "--frozen", "fantadamus", "serve", "--user", "owner"]
