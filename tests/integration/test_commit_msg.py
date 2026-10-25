"""Task 6.2: a non-Conventional commit message is rejected by the commit-msg hook (R9.2, R9.3)."""

from __future__ import annotations

import stat
from pathlib import Path

import yaml
from scripts.checks._common import run_command

from tests.integration.conftest import Git

ROOT = Path(__file__).resolve().parents[2]


def _commit_msg_entry() -> str:
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = [hook for repo in config["repos"] for hook in repo["hooks"]]
    entry: str = next(hook["entry"] for hook in hooks if "commit-msg" in hook.get("stages", []))
    return entry


def _install_hook(repo: Path) -> None:
    hooks = repo / ".git" / "hooks"
    script = hooks / "commit-msg"
    script.write_text(
        "#!/bin/sh\n"
        'msg="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"\n'
        f'cd "{ROOT}" && exec {_commit_msg_entry()} "$msg"\n',
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)


def test_non_conventional_message_rejected(git_repo: tuple[Path, Git]) -> None:
    repo, git = git_repo
    _install_hook(repo)
    (repo / "a.md").write_text("a\n", encoding="utf-8")
    git("add", "a.md")
    rejected = run_command(["git", "-C", str(repo), "commit", "-q", "-m", "added some stuff"])
    assert rejected.returncode != 0
    accepted = run_command(["git", "-C", str(repo), "commit", "-q", "-m", "docs: add a"])
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
