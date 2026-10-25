"""Task 9.6: `.claude/settings.json` follows Claude Code's hooks format and wires our hooks (R17.1, R17.7)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from scripts.checks import hook_config

ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = ROOT / "scripts" / "hooks"


def _committed() -> dict[str, Any]:
    settings: dict[str, Any] = json.loads(hook_config.SETTINGS.read_text(encoding="utf-8"))
    return settings


def test_configs_valid() -> None:
    assert hook_config.problems(_committed(), HOOKS_DIR) == []
    assert hook_config.check().ok


def _broken(change: str) -> dict[str, Any]:
    settings = copy.deepcopy(_committed())
    hooks = settings["hooks"]
    guard_handler = hooks["PreToolUse"][0]["hooks"][0]
    if change == "unknown event":
        hooks["BeforeEverything"] = hooks.pop("Stop")
    elif change == "bad type":
        guard_handler["type"] = "script"
    elif change == "bad timeout":
        hooks["Stop"][0]["hooks"][0]["timeout"] = 60
    elif change == "narrow matcher":
        hooks["PreToolUse"][0]["matcher"] = "Bash"
    elif change == "bad regex":
        hooks["PreToolUse"][0]["matcher"] = "Bash|("
    elif change == "missing module":
        guard_handler["command"] = guard_handler["command"].replace(
            "scripts.hooks.guard", "scripts.hooks.gaurd"
        )
    elif change == "fail open":
        guard_handler["command"] = guard_handler["command"].replace(" || exit 2", "")
    elif change == "no post edit":
        del hooks["PostToolUse"]
    elif change == "extra key":
        guard_handler["shell"] = "zsh"
    return settings


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("unknown event", "BeforeEverything: not a documented hook event"),
        ("bad type", 'type must be "command"'),
        ("bad timeout", "Stop runs scripts.hooks.stop_check with a timeout under"),
        ("narrow matcher", "PreToolUse must run scripts.hooks.guard for the Write tool"),
        ("bad regex", "matcher is not a valid regular expression"),
        ("missing module", "scripts.hooks.gaurd does not exist"),
        ("fail open", "must end with `|| exit 2`"),
        ("no post edit", "PostToolUse must run scripts.hooks.post_edit"),
        ("extra key", "unknown field shell"),
    ],
)
def test_broken_configs_fail(change: str, expected: str) -> None:
    issues = hook_config.problems(_broken(change), HOOKS_DIR)
    assert any(expected in issue for issue in issues), issues


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ([], "settings must be a JSON object"),
        ({"hooks": []}, '"hooks" must be an object'),
        ({"hooks": {"Stop": []}}, "Stop: must be a non-empty list"),
        ({"hooks": {"Stop": ["x"]}}, "Stop[0]: must be an object"),
        ({"hooks": {"Stop": [{"hooks": []}]}}, "Stop[0]: hooks must be a non-empty list"),
        ({"hooks": {"Stop": [{"hooks": ["x"]}]}}, "Stop[0].hooks[0]: must be an object"),
        (
            {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": " "}]}]}},
            "command must be a non-empty string",
        ),
        (
            {"hooks": {"Stop": [{"matcher": 1, "hooks": [{"type": "command", "command": "x"}]}]}},
            "matcher must be a string",
        ),
    ],
)
def test_malformed_settings_fail(settings: object, expected: str) -> None:
    issues = hook_config.problems(settings, HOOKS_DIR)
    assert any(expected in issue for issue in issues), issues


def test_unreadable_settings_fail(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    assert "not valid JSON" in hook_config.check(path).message
    assert "missing" in hook_config.check(tmp_path / "absent.json").message
