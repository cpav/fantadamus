"""Private data can't be committed: these paths are git-ignored, shared files aren't (R2.10)."""

from __future__ import annotations

import json
import plistlib
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


def test_player_guide_setup() -> None:
    """mvp-x-or-y task 9.2 (R13.4): a second player can set Fantadamus up from the guide alone."""
    guide = (ROOT / "docs" / "player-setup.md").read_text(encoding="utf-8")
    assert "git clone https://github.com/cpav/fantadamus.git" in guide
    block = guide.split("```json\n", 1)[1].split("```", 1)[0]
    server = json.loads(block)["mcpServers"]["fantadamus"]
    assert server["command"].endswith("/.local/bin/uv")
    assert server["args"][0] == "--directory"
    assert server["args"][2:] == ["run", "--frozen", "--no-dev", "fantadamus", "serve", "--user", "your-name"]
    assert "Project" in guide
    assert "docs/agent-prompt.md" in guide


def test_player_guide_schedule() -> None:
    """mvp-collect task 7.2 (R7.2): the guide has the player install a launchd agent that runs `collect --due`
    every 15 minutes, with their own paths filled in by the shell, and shows how to switch it off."""
    guide = (ROOT / "docs" / "player-setup.md").read_text(encoding="utf-8")
    heredoc = guide.split("<<EOF\n", 1)[1].split("\nEOF\n", 1)[0]
    filled = heredoc.replace("$(which uv)", "/Users/you/.local/bin/uv").replace("$HOME", "/Users/you")
    plist = plistlib.loads(filled.encode())
    assert plist["StartInterval"] == 900
    assert plist["ProgramArguments"] == [
        "/Users/you/.local/bin/uv",
        "--directory",
        "/Users/you/fantadamus",
        "run",
        "--frozen",
        "--no-dev",
        "fantadamus",
        "collect",
        "--due",
    ]
    switch_on = guide.split("launchctl bootstrap", 1)[1].split("\n", 1)[0]
    assert f"{plist['Label']}.plist" in switch_on
    assert f"launchctl bootout gui/$(id -u)/{plist['Label']}" in guide
