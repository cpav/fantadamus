"""Task 3.2: a stale uv.lock fails the check (R3.4)."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

from scripts.checks import lockfile


def _runner(returncode: int, stderr: str = "") -> lockfile.Runner:
    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        assert list(args) == ["uv", "lock", "--check"]
        return subprocess.CompletedProcess(list(args), returncode, stdout="", stderr=stderr)

    return run


def test_stale_lock_fails() -> None:
    result = lockfile.check(run=_runner(1, "error: The lockfile at `uv.lock` needs to be updated"))
    assert not result.ok
    assert "uv lock" in result.message


def test_fresh_lock_passes() -> None:
    result = lockfile.check(run=_runner(0))
    assert result.ok
    assert result.name == "lockfile"


def test_stale_lock_without_output_still_explains() -> None:
    result = lockfile.check(run=_runner(2))
    assert not result.ok
    assert result.message.startswith("uv.lock is out of date")
