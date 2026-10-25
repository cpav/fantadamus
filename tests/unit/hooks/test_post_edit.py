"""Task 9.2: after the agent edits a Python file, format and lint it and report what remains (R17.2)."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from scripts.hooks import post_edit
from scripts.hooks.event import HookEvent


def _edit(path: Path, tool: str = "Edit") -> HookEvent:
    return HookEvent(hook_event_name="PostToolUse", tool_name=tool, tool_input={"file_path": str(path)})


def _runner(check_code: int, findings: str = "") -> tuple[list[list[str]], post_edit.Runner]:
    calls: list[list[str]] = []

    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        code = check_code if "check" in args else 0
        return subprocess.CompletedProcess(list(args), code, stdout=findings if code else "", stderr="")

    return calls, run


def test_formats_and_reports_remaining(tmp_path: Path) -> None:
    source = tmp_path / "src" / "module.py"
    source.parent.mkdir()
    source.write_text("import os\n", encoding="utf-8")
    calls, run = _runner(1, "src/module.py:1:8: F401 [*] `os` imported but unused\n")
    result = post_edit.handle(_edit(source), root=tmp_path, run=run)
    assert [call[-4:] for call in calls] == [
        ["ruff", "format", "--quiet", str(source)],
        ["check", "--fix", "--output-format=concise", str(source)],
    ]
    assert result.code == 2
    assert "ruff still reports problems in src/module.py" in result.stderr
    assert "F401" in result.stderr


def test_clean_file_passes_quietly(tmp_path: Path) -> None:
    source = tmp_path / "ok.py"
    source.write_text("x = 1\n", encoding="utf-8")
    calls, run = _runner(0)
    result = post_edit.handle(_edit(source, "Write"), root=tmp_path, run=run)
    assert (result.code, result.stderr) == (0, "")
    assert len(calls) == 2


def test_other_files_are_ignored(tmp_path: Path) -> None:
    calls, run = _runner(1)
    notes = tmp_path / "notes.md"
    notes.write_text("# notes\n", encoding="utf-8")
    outside = tmp_path.parent / "elsewhere.py"
    for event in (
        _edit(notes),
        _edit(tmp_path / "missing.py"),
        _edit(outside),
        HookEvent(hook_event_name="PostToolUse", tool_name="Bash", tool_input={"command": "ls"}),
    ):
        assert post_edit.handle(event, root=tmp_path, run=run).code == 0
    assert calls == []
