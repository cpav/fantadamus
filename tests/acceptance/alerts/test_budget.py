"""AT-4 of mvp-alerts: a check stays within its time on the synthetic round, with all its simulated rounds;
sending needs nothing installed and no account (design C6; R4.1)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

from fantadamus.cli import notify
from fantadamus.engine.constants import ALERT_SECONDS
from fantadamus.mcp import alerts


def test_at4_a_check_in_budget(timings: dict[str, Any]) -> None:
    """Timed in a process of its own, the fastest of three, as `tests/lineup_speed.py` times a lineup."""
    assert timings["alert"] < ALERT_SECONDS


def _imports(module: Path) -> set[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    found = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    return found | {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }


def test_at4_no_install_and_no_account() -> None:
    """Sending uses macOS's own osascript and the standard library; the check fetches no page."""
    assert notify.OSASCRIPT == "/usr/bin/osascript"
    assert {name.split(".")[0] for name in _imports(Path(notify.__file__))} <= set(sys.stdlib_module_names)
    assert "fantadamus.web.fetch" not in _imports(Path(alerts.__file__))
