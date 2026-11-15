"""Showing an alert on the Mac, through macOS's own `osascript`, and the switch that turns alerts off
(mvp-alerts C6, C7; R3.1, R3.4, R4.1). Nothing to install and no account.

The text is passed to a fixed script as arguments, never put into the script, so a name can't change what
runs.
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

OSASCRIPT = "/usr/bin/osascript"
TIMEOUT_SECONDS = 5
_SCRIPT = (
    "on run argv",
    "display notification (item 3 of argv) with title (item 1 of argv) subtitle (item 2 of argv)",
    "end run",
)
CONFIG_VAR = "FANTADAMUS_PRIVATE_CONFIG"
DEFAULT_CONFIG = Path.home() / ".config" / "fantadamus" / "private.toml"

Run = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    # reason: a fixed command at an absolute path; the text goes in as arguments, never as code
    return subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False)  # noqa: S603


def notify(title: str, subtitle: str, text: str, *, run: Run = _run) -> str | None:
    """Show the notification: None once macOS has taken it, else why it couldn't. Never raises."""
    command = [OSASCRIPT, *(part for line in _SCRIPT for part in ("-e", line)), title, subtitle, text]
    try:
        done = run(command)
    except FileNotFoundError:
        return "osascript isn't on this computer: alerts need a Mac"
    except subprocess.TimeoutExpired:
        return f"osascript took more than {TIMEOUT_SECONDS} seconds"
    except OSError as error:
        return f"osascript couldn't start: {error.strerror or error}"
    if done.returncode != 0:
        return f"osascript failed: {done.stderr.strip() or f'exit code {done.returncode}'}"
    return None


def alerts_enabled(environ: Mapping[str, str] | None = None) -> tuple[bool, str | None]:
    """Whether alerts are on, and why not or what went wrong: `[alerts] enabled = false` in the private
    configuration turns them off; without it, or when the file can't be read, they stay on (design C7)."""
    environ = os.environ if environ is None else environ
    path = Path(environ.get(CONFIG_VAR, str(DEFAULT_CONFIG))).expanduser()
    if not path.is_file():
        return True, None
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        return True, f"Alerts stay on: the private configuration can't be read ({type(error).__name__})."
    section = config.get("alerts", {})
    enabled = section.get("enabled", True) if isinstance(section, dict) else True
    if enabled is False:
        return False, "Alerts are switched off in the private configuration."
    if enabled is not True:
        return True, "Alerts stay on: `enabled` under [alerts] must be true or false."
    return True, None
