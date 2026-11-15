"""mvp-alerts task 3.1: an alert shown through macOS's own `osascript`, the text passed as arguments, never as
code; a failure comes back as its reason (design C6; R3.1, R4.1)."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

import pytest

from fantadamus.cli.notify import OSASCRIPT, TIMEOUT_SECONDS, _run, notify

TRICKY = 'Start "Rossi" instead of Bianchi\'s cover: do shell script "rm -rf ~" -- end run'


class Runs:
    """A runner that records each command and gives back `result`, or raises `error`."""

    def __init__(self, result: int = 0, stderr: str = "", error: BaseException | None = None) -> None:
        self.commands: list[list[str]] = []
        self.result, self.stderr, self.error = result, stderr, error

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        if self.error is not None:
            raise self.error
        return subprocess.CompletedProcess(command, self.result, "", self.stderr)


def test_the_text_goes_in_as_arguments() -> None:
    runs = Runs()
    assert notify("Fantadamus · Round 12", "Official lineup out", TRICKY, run=runs) is None
    [command] = runs.commands
    assert command[0] == OSASCRIPT == "/usr/bin/osascript"
    assert command[-3:] == ["Fantadamus · Round 12", "Official lineup out", TRICKY]
    script = command[1:-3]
    assert script[::2] == ["-e", "-e", "-e"]
    assert not any("Rossi" in line or "Fantadamus" in line for line in script)
    assert "display notification (item 3 of argv)" in script[3]


def test_a_failure_returns_its_reason() -> None:
    assert notify("t", "s", "x", run=Runs(1, "execution error: Not authorised (-1743)\n")) == (
        "osascript failed: execution error: Not authorised (-1743)"
    )
    assert notify("t", "s", "x", run=Runs(1)) == "osascript failed: exit code 1"
    assert notify("t", "s", "x", run=Runs(error=FileNotFoundError())) == (
        "osascript isn't on this computer: alerts need a Mac"
    )
    assert notify("t", "s", "x", run=Runs(error=PermissionError(13, "Permission denied"))) == (
        "osascript couldn't start: Permission denied"
    )


def test_a_timeout_returns_its_reason() -> None:
    late = subprocess.TimeoutExpired([OSASCRIPT], TIMEOUT_SECONDS)
    assert notify("t", "s", "x", run=Runs(error=late)) == "osascript took more than 5 seconds"


def test_the_runner_runs_a_command_and_waits_for_it(monkeypatch: pytest.MonkeyPatch) -> None:
    done = _run([sys.executable, "-c", "import sys; print(sys.argv[1])", "an argument"])
    assert (done.returncode, done.stdout.strip()) == (0, "an argument")
    monkeypatch.setattr("fantadamus.cli.notify.TIMEOUT_SECONDS", 0.2)
    with pytest.raises(subprocess.TimeoutExpired):
        _run([sys.executable, "-c", "import time; time.sleep(5)"])
