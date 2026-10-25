"""Task 6.4: the gitleaks wrapper scans staged files, a commit range or the whole history (R10.1, R10.2)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from scripts.checks import secrets
from scripts.checks._common import CheckResult

FINDING = json.dumps(
    [
        {
            "RuleID": "aws-access-token",
            "File": "a.py",
            "StartLine": 3,
            "Commit": "0123456789abcdef",
            "Secret": "REDACTED",
        }
    ]
)


def _runner(returncode: int, output: str = "") -> tuple[list[list[str]], secrets.Runner]:
    calls: list[list[str]] = []

    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        return subprocess.CompletedProcess(list(args), returncode, stdout=output, stderr="")

    return calls, run


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (secrets.Mode.STAGED, ["--pre-commit", "--staged"]),
        (secrets.Mode.HISTORY, []),
        (secrets.Mode.RANGE, ["--log-opts", "main..HEAD"]),
    ],
)
def test_builds_the_gitleaks_command(mode: secrets.Mode, expected: list[str], tmp_path: Path) -> None:
    calls, run = _runner(0)
    result = secrets.check(mode, log_opts="main..HEAD", run=run, root=tmp_path)
    assert result.ok
    command = calls[0]
    assert command[:2] == [str(tmp_path / "bin" / "gitleaks"), "git"]
    assert {"--redact", "--no-banner"} <= set(command)
    assert command[command.index("--report-format") + 1] == "json"
    assert command[command.index("--config") + 1] == str(tmp_path / ".gitleaks.toml")
    for option in expected:
        assert option in command
    assert command[-1] == str(tmp_path)


def test_findings_fail_with_locations_only(tmp_path: Path) -> None:
    _, run = _runner(1, FINDING)
    result = secrets.check(secrets.Mode.HISTORY, run=run, root=tmp_path)
    assert not result.ok
    assert result.message == "secrets found (redacted): aws-access-token at 0123456789ab a.py:3"


def test_gitleaks_errors_fail(tmp_path: Path) -> None:
    _, run = _runner(126, "permission denied")
    result = secrets.check(secrets.Mode.HISTORY, run=run, root=tmp_path)
    assert not result.ok
    assert result.message.startswith("gitleaks failed (exit 126)")


@pytest.mark.parametrize(
    ("argv", "mode", "opts"),
    [
        (["--staged"], secrets.Mode.STAGED, ""),
        (["--history"], secrets.Mode.HISTORY, ""),
        (["--range", "a..b"], secrets.Mode.RANGE, "a..b"),
    ],
)
def test_main_dispatches_each_mode(
    argv: list[str], mode: secrets.Mode, opts: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[secrets.Mode, str]] = []

    def fake_check(m: secrets.Mode, log_opts: str = "") -> CheckResult:
        seen.append((m, log_opts))
        return CheckResult("secrets", ok=True)

    monkeypatch.setattr(secrets, "check", fake_check)
    assert secrets.main(argv) == 0
    assert seen == [(mode, opts)]


def test_gitleaks_error_without_output_suggests_setup(tmp_path: Path) -> None:
    _, run = _runner(127, "")
    assert "make setup" in secrets.check(secrets.Mode.HISTORY, run=run, root=tmp_path).message
