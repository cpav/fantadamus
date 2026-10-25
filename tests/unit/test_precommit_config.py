"""Task 6.1: the git hooks cover every stage; every remote hook is pinned to a commit (R9.1, R9.3, R9.4)."""

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


def test_stages_present() -> None:
    assert set(_config()["default_install_hook_types"]) == {"pre-commit", "commit-msg", "pre-push"}
    hooks = _hooks()
    for hook_id in (
        "ruff-format",
        "ruff",
        "mypy",
        "yamllint",
        "markdownlint-cli2",
        "actionlint",
        "gitleaks-staged",
        "identities-staged",
        "check-added-large-files",
        "check-merge-conflict",
    ):
        assert hook_id in hooks, f"missing pre-commit hook {hook_id}"
    assert hooks["conventional-commits"]["stages"] == ["commit-msg"]
    assert hooks["outgoing-secrets-and-identities"]["stages"] == ["pre-push"]


def test_local_hooks_use_the_locked_environment() -> None:
    local = next(repo for repo in _config()["repos"] if repo["repo"] == "local")
    for hook in local["hooks"]:
        entry = hook["entry"]
        assert entry.startswith(("uv run --frozen ", "bin/")), f"{hook['id']} must run locked or pinned tools"
