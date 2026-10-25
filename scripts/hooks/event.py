"""Claude Code hook events (R17.1): the JSON on standard input, parsed into one `HookEvent`.

The payload shape is recorded in ADR-0001 and in `tests/fixtures/hooks/`. Only `hook_event_name` is
required and unknown fields are kept, so a Claude Code release that adds or drops a field doesn't break the
hooks. Each entry point also records the payload's shape (field names only, never values) in the git
directory, for the live comparison with the fixtures in task 9.7.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from scripts.checks._common import run_command

ROOT = Path(__file__).resolve().parents[2]
SHAPES_FILE = "fantadamus-hook-shapes.jsonl"


class HookEventError(ValueError):
    """The input isn't a Claude Code hook event."""


class HookEvent(BaseModel):
    """The fields the hooks use; anything else in the payload is kept but ignored."""

    model_config = ConfigDict(extra="allow", frozen=True)

    hook_event_name: str
    session_id: str = ""
    transcript_path: str = ""
    cwd: str = ""
    permission_mode: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, JsonValue] = Field(default_factory=dict)
    stop_hook_active: bool = False

    @property
    def command(self) -> str | None:
        """The shell command of a Bash tool call."""
        value = self.tool_input.get("command")
        return value if isinstance(value, str) else None

    @property
    def file_path(self) -> str | None:
        """The file a Write, Edit, MultiEdit or NotebookEdit tool call touches."""
        for key in ("file_path", "notebook_path"):
            value = self.tool_input.get(key)
            if isinstance(value, str):
                return value
        return None


def parse(text: str) -> HookEvent:
    try:
        return HookEvent.model_validate_json(text)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(map(str, first["loc"])) or "payload"
        raise HookEventError(f"not a Claude Code hook event ({where}: {first['msg']})") from error


def shape(raw: dict[str, JsonValue]) -> dict[str, object]:
    """The payload's field names, without any values."""
    tool_input = raw.get("tool_input")
    return {
        "event": raw.get("hook_event_name"),
        "tool": raw.get("tool_name"),
        "keys": sorted(raw),
        "tool_input_keys": sorted(tool_input) if isinstance(tool_input, dict) else [],
    }


def record_shape(text: str, path: Path) -> None:
    """Append the payload's shape to `path` unless it is already there. Never fails the hook."""
    try:
        raw = json.loads(text)
        if not isinstance(raw, dict):
            return
        line = json.dumps(shape(raw), sort_keys=True)
        seen = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        if line not in seen:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except (OSError, ValueError):
        return


def shapes_path(root: Path) -> Path:
    """Where shapes are recorded: $FANTADAMUS_HOOK_SHAPES (tests), else the git directory."""
    override = os.environ.get("FANTADAMUS_HOOK_SHAPES")
    return Path(override) if override else git_dir(root) / SHAPES_FILE


@dataclass(frozen=True)
class HookResult:
    """What a hook tells Claude Code: an exit code (0 ok, 2 block, other: a non-blocking error) and output."""

    code: int
    stdout: str = ""
    stderr: str = ""


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or ROOT)


def git_dir(root: Path) -> Path:
    completed = run_command(["git", "-C", str(root), "rev-parse", "--absolute-git-dir"])
    return Path(completed.stdout.strip()) if completed.returncode == 0 else root / ".git"


def run_hook(
    handler: Callable[[HookEvent], HookResult],
    *,
    invalid_code: int,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Read the event, record its shape, run the handler and write its output. Returns the exit code."""
    text = (stdin or sys.stdin).read()
    record_shape(text, shapes_path(project_root()))
    try:
        result = handler(parse(text))
    except HookEventError as error:
        result = HookResult(invalid_code, stderr=f"{error}\n")
    (stdout or sys.stdout).write(result.stdout)
    (stderr or sys.stderr).write(result.stderr)
    return result.code
