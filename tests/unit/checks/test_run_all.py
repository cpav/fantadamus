"""`make check` (run_all) keeps going past failures, summarises, runs quick checks side by side, and never
sees AWS credentials (R1.1 to R1.3, R1.6)."""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Sequence

import pytest
from scripts.checks import run_all


def test_check_continues_and_summarises(capsys: pytest.CaptureFixture[str]) -> None:
    ran: list[str] = []

    def run(args: Sequence[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        ran.append(args[0])
        code = 1 if args[0] == "bad" else 0
        return subprocess.CompletedProcess(list(args), code, stdout="", stderr="it broke\n" if code else "")

    checks = [
        run_all.Check("first", ("good",)),
        run_all.Check("second", ("bad",)),
        run_all.Check("third", ("good",)),
    ]
    assert run_all.run_checks(checks, run=run, capture=run, env={}) == 1
    assert sorted(ran) == ["bad", "good", "good"]
    out = capsys.readouterr().out
    assert out.endswith("PASS first\nFAIL second\nPASS third\n2 passed, 1 failed\n")


def test_quick_checks_run_together_then_tests_alone(capsys: pytest.CaptureFixture[str]) -> None:
    barrier = threading.Barrier(2, timeout=5)
    order: list[str] = []

    def quick(args: Sequence[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        barrier.wait()  # passes only if both quick checks are running at the same time
        order.append(args[0])
        return subprocess.CompletedProcess(list(args), 0, stdout=f"{args[0]} output\n", stderr="")

    def serial(args: Sequence[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        order.append(args[0])
        return subprocess.CompletedProcess(list(args), 0, stdout="", stderr="")

    checks = [
        run_all.Check("lint", ("lint",)),
        run_all.Check("tests", ("tests",)),
        run_all.Check("coverage", ("coverage",)),
        run_all.Check("audit", ("audit",)),
    ]
    assert run_all.run_checks(checks, run=serial, capture=quick, env={}) == 0
    assert sorted(order[:2]) == ["audit", "lint"]
    assert order[2:] == ["tests", "coverage"]
    out = capsys.readouterr().out
    assert out.index("==> lint\nlint output") < out.index("==> audit\naudit output") < out.index("==> tests")
    assert out.endswith("PASS lint\nPASS tests\nPASS coverage\nPASS audit\n4 passed, 0 failed\n")


def test_check_env_has_no_aws_credentials() -> None:
    env = run_all.check_env(
        {
            "PATH": "/bin",
            "AWS_ACCESS_KEY_ID": "x",
            "AWS_SECRET_ACCESS_KEY": "y",
            "AWS_PROFILE": "admin",
            "HOME": "/h",
        }
    )
    assert not any(key.startswith("AWS_") and key not in run_all.AWS_BLOCKERS for key in env)
    assert env["AWS_CONFIG_FILE"] == env["AWS_SHARED_CREDENTIALS_FILE"] == "/dev/null"
    assert env["HYPOTHESIS_PROFILE"] == "ci"
    assert env["PATH"] == "/bin"


def test_run_all_rejects_unknown_groups(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_all.main(["everything"]) == 2
    assert "usage:" in capsys.readouterr().err


def test_empty_group_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_all.run_checks([], env={}) == 0
    assert "nothing to check in this group yet" in capsys.readouterr().out


def test_real_runner_passes_the_environment() -> None:
    completed = run_all._run(
        ["python3", "-c", "import os, sys; sys.exit(os.environ['MARK'] != 'on')"],
        {**run_all.check_env({"PATH": "/usr/bin:/bin"}), "MARK": "on"},
    )
    assert completed.returncode == 0


def test_main_runs_the_named_group(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[run_all.Check]] = []

    def fake_run_checks(checks: Sequence[run_all.Check]) -> int:
        seen.append(list(checks))
        return 0

    monkeypatch.setattr(run_all, "run_checks", fake_run_checks)
    assert run_all.main(["audit"]) == 0
    assert seen == [run_all.GROUPS["audit"]]
