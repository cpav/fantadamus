"""The git hooks: remote hooks pinned to a commit, leak guards wired, local tools from `.venv` (R9, R10)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _config() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    return loaded


def _hooks() -> dict[str, dict[str, Any]]:
    return {hook["id"]: hook for repo in _config()["repos"] for hook in repo["hooks"]}


def test_all_revs_pinned() -> None:
    remote = [repo for repo in _config()["repos"] if repo["repo"] not in ("local", "meta")]
    assert remote, "expected remote hook repositories"
    for repo in remote:
        assert re.fullmatch(r"[0-9a-f]{40}", repo["rev"]), f"{repo['repo']} must be pinned to a commit SHA"


def test_leak_guards_are_wired() -> None:
    # The preventive gates of a public repository: a secret or a creator name never leaves this machine.
    assert set(_config()["default_install_hook_types"]) == {"pre-commit", "commit-msg", "pre-push"}
    hooks = _hooks()
    assert {"gitleaks-staged", "identities-staged"} <= set(hooks)
    assert hooks["outgoing-secrets-and-identities"]["stages"] == ["pre-push"]
    assert hooks["conventional-commits"]["stages"] == ["commit-msg"]


def test_local_hooks_use_the_locked_environment() -> None:
    # The project's own environment (made by `make setup`) or the pinned binaries, never a tool found on
    # PATH: a terminal without `uv` on its PATH must still run every hook (found at the go-ahead push).
    local = next(repo for repo in _config()["repos"] if repo["repo"] == "local")
    for hook in local["hooks"]:
        entry = hook["entry"]
        assert entry.startswith((".venv/bin/", "bin/")), f"{hook['id']} must run locked or pinned tools"
