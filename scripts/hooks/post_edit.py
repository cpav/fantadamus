"""PostToolUse on Edit, Write and MultiEdit: format and lint the edited Python file (R17.2).

Remaining lint findings go back to the agent (exit 2 feeds stderr to Claude). pre-commit and `make check`
run the same tools, so this is the fast loop, not the gate of record (R17.9).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from scripts.checks._common import run_command
from scripts.hooks.event import HookEvent, HookResult, project_root, run_hook

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
RUFF = (sys.executable, "-m", "ruff")


def handle(event: HookEvent, *, root: Path, run: Runner = run_command) -> HookResult:
    path_text = event.file_path
    if path_text is None or not path_text.endswith(".py"):
        return HookResult(0)
    path = Path(path_text).resolve()
    if not path.is_file() or root.resolve() not in path.parents:
        return HookResult(0)
    run([*RUFF, "format", "--quiet", str(path)])
    checked = run([*RUFF, "check", "--fix", "--output-format=concise", str(path)])
    if checked.returncode != 0:
        relative = path.relative_to(root.resolve())
        return HookResult(
            2, stderr=f"ruff still reports problems in {relative}:\n{checked.stdout}{checked.stderr}"
        )
    return HookResult(0)


def main() -> int:
    root = project_root()
    return run_hook(lambda event: handle(event, root=root), invalid_code=1)


if __name__ == "__main__":
    raise SystemExit(main())
