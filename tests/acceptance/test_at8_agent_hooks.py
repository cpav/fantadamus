"""AT-8: the agent hooks, fed recorded Claude Code events (R17.3, R17.5, R17.6).

The guard runs exactly as `.claude/settings.json` wires it, through the shell. The stop hook's logic runs
with a stubbed `make check`, because running the real one here would run this test again.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from scripts.checks import hook_config
from scripts.checks._common import run_command
from scripts.hooks import post_edit, stop_check
from scripts.hooks.event import HookEvent, parse

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "hooks"
RED = "PASS format\nFAIL lint: ruff found 1 problem\n17 passed, 1 failed\n"


def _fixture(name: str) -> dict[str, object]:
    payload: dict[str, object] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return payload


def _wired_command(event: str, module: str) -> str:
    settings = json.loads(hook_config.SETTINGS.read_text(encoding="utf-8"))
    for group in settings["hooks"][event]:
        for handler in group["hooks"]:
            if f"scripts.hooks.{module}" in handler["command"]:
                command: str = handler["command"]
                return command
    raise AssertionError(f"{event} does not run scripts.hooks.{module}")


def _run_guard(payload: dict[str, object], shapes: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT), "FANTADAMUS_HOOK_SHAPES": str(shapes)}
    command = ["/bin/bash", "-c", _wired_command("PreToolUse", "guard")]
    return run_command(command, stdin_text=json.dumps(payload), env=env, timeout=60)


def _bash(command: str) -> dict[str, object]:
    payload = _fixture("pre_tool_use_bash_harmless")
    payload["tool_input"] = {"command": command, "description": "test"}
    return payload


def test_at8_agent_hooks(tmp_path: Path) -> None:
    assert (
        hook_config.problems(
            json.loads(hook_config.SETTINGS.read_text(encoding="utf-8")), ROOT / "scripts" / "hooks"
        )
        == []
    )
    shapes = tmp_path / "shapes.jsonl"

    # R17.5: every owner-only action is blocked, through the wired command; a harmless one runs.
    private = _fixture("pre_tool_use_write_private_config")
    private["tool_input"] = {
        "file_path": str(Path.home() / ".config/fantadamus/private.toml"),
        "content": "x",
    }
    blocked = [
        _fixture("pre_tool_use_bash_git_push"),
        _bash("terraform apply"),
        _bash("make deploy"),
        _bash("make bootstrap"),
        private,
    ]
    for payload in blocked:
        result = _run_guard(payload, shapes)
        assert result.returncode == 2, (payload, result.stderr)
        assert "Blocked by the project guard" in result.stderr
    assert _run_guard(_fixture("pre_tool_use_bash_harmless"), shapes).returncode == 0
    assert shapes.read_text(encoding="utf-8").count("PreToolUse") >= 2

    # R17.3: a red `make check` goes back to the agent; a second red lets the turn end, visibly.
    stop = parse((FIXTURES / "stop.json").read_text(encoding="utf-8"))
    stop_again = parse((FIXTURES / "stop_active.json").read_text(encoding="utf-8"))

    def red() -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["make", "check"], 2, stdout=RED, stderr="")

    last_green = tmp_path / "last-green"
    first = stop_check.handle(stop, state="changed", last_green=last_green, run_check=red)
    assert (first.code, "FAIL lint" in first.stderr) == (2, True)
    again = stop_check.handle(stop_again, state="changed", last_green=last_green, run_check=red)
    assert (again.code, "FAIL lint" in again.stderr) == (1, True)
    last_green.write_text("unchanged\n", encoding="utf-8")
    quiet = stop_check.handle(stop, state="unchanged", last_green=last_green, run_check=red)
    assert (quiet.code, "no check needed" in quiet.stdout) == (0, True)

    # R17.2: an edited Python file with problems ruff can't fix goes back to the agent.
    source = tmp_path / "edited.py"
    source.write_text("print(undefined_name)\n", encoding="utf-8")
    edit = HookEvent.model_validate(
        _fixture("post_tool_use_edit_python") | {"tool_input": {"file_path": str(source)}}
    )
    assert post_edit.handle(edit, root=tmp_path).code == 2


@pytest.mark.parametrize("event", ["PreToolUse", "PostToolUse", "Stop"])
def test_at8_settings_wire_each_event(event: str) -> None:
    module = {"PreToolUse": "guard", "PostToolUse": "post_edit", "Stop": "stop_check"}[event]
    assert f"scripts.hooks.{module}" in _wired_command(event, module)
