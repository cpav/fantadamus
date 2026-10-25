"""The shared runner: a timeout ends the whole command, children included, and keeps the output so far."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest
from scripts.checks._common import run_command


def test_timeout_kills_children_holding_the_output_open() -> None:
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired) as expired:
        run_command(["bash", "-c", "echo '==> audit'; sleep 30 & sleep 30"], timeout=1)
    assert time.monotonic() - started < 10
    assert expired.value.output == "==> audit\n"


def test_stdin_env_and_cwd_reach_the_command(tmp_path: Path) -> None:
    done = run_command(
        ["bash", "-c", 'read line; echo "$line $GREETING $(pwd)"'],
        stdin_text="hello\n",
        env={"GREETING": "world", "PATH": "/usr/bin:/bin"},
        cwd=tmp_path,
        timeout=10,
    )
    assert done.returncode == 0
    assert done.stdout.startswith("hello world ")
