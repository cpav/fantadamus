"""Task 9.1: Claude Code hook payloads parse into one `HookEvent` (R17.1; contract in ADR-0001)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.hooks.event import SHAPES_FILE, HookEventError, parse, record_shape

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "hooks"


def test_recorded_events_parse() -> None:
    events = {path.stem: parse(path.read_text(encoding="utf-8")) for path in sorted(FIXTURES.glob("*.json"))}
    assert set(events) == {
        "post_tool_use_edit_python",
        "pre_tool_use_bash_git_push",
        "pre_tool_use_bash_harmless",
        "pre_tool_use_write_private_config",
        "stop",
        "stop_active",
    }
    for event in events.values():
        assert event.cwd == "/workspace/fantadamus"
    push = events["pre_tool_use_bash_git_push"]
    assert (push.hook_event_name, push.tool_name, push.command) == (
        "PreToolUse",
        "Bash",
        "git push origin main",
    )
    edit = events["post_tool_use_edit_python"]
    assert edit.hook_event_name == "PostToolUse"
    assert edit.file_path == "/workspace/fantadamus/src/fantadamus/core/hashing.py"
    assert edit.command is None
    assert (
        events["pre_tool_use_write_private_config"].file_path == "/home/owner/.config/fantadamus/private.toml"
    )
    assert events["stop_active"].stop_hook_active
    assert not events["stop"].stop_hook_active
    assert events["stop"].file_path is None


def test_unknown_fields_are_tolerated() -> None:
    event = parse('{"hook_event_name": "Stop", "added_in_a_later_release": 1}')
    assert event.hook_event_name == "Stop"
    assert not event.stop_hook_active


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not json",
        "[]",
        '{"tool_name": "Bash"}',
        '{"hook_event_name": 3}',
        '{"hook_event_name": "Stop", "tool_input": "x"}',
    ],
)
def test_invalid_events_fail(text: str) -> None:
    with pytest.raises(HookEventError, match="not a Claude Code hook event"):
        parse(text)


def test_shape_records_field_names_never_values(tmp_path: Path) -> None:
    text = (FIXTURES / "pre_tool_use_bash_git_push.json").read_text(encoding="utf-8")
    shapes = tmp_path / SHAPES_FILE
    record_shape(text, shapes)
    record_shape(text, shapes)
    record_shape("not json", shapes)
    record_shape("[1, 2]", shapes)
    lines = shapes.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "event": "PreToolUse",
        "tool": "Bash",
        "keys": [
            "cwd",
            "hook_event_name",
            "permission_mode",
            "session_id",
            "tool_input",
            "tool_name",
            "tool_use_id",
            "transcript_path",
        ],
        "tool_input_keys": ["command", "description"],
    }
    assert "git push" not in lines[0]
