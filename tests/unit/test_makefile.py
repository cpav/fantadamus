"""Task 7.1: `make check` runs every group, keeps going, summarises, and never sees AWS credentials (R1)."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
import yaml
from scripts.checks import run_all

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = (ROOT / "Makefile").read_text(encoding="utf-8")


def _recipe(target: str) -> str:
    match = re.search(rf"^{re.escape(target)}:.*\n((?:\t.*\n)+)", MAKEFILE, re.M)
    assert match, f"Makefile has no recipe for {target}"
    return match.group(1)


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
    assert run_all.run_checks(checks, run=run, env={}) == 1
    assert ran == ["good", "bad", "good"]
    out = capsys.readouterr().out
    assert out.endswith("PASS first\nFAIL second\nPASS third\n2 passed, 1 failed\n")


def test_check_is_union_of_subtargets() -> None:
    union = [
        *run_all.GROUPS["static"],
        *run_all.GROUPS["tests"],
        *run_all.GROUPS["infra"],
        *run_all.GROUPS["audit"],
    ]
    assert run_all.GROUPS["all"] == union
    assert "scripts.checks.run_all all" in _recipe("check")
    for group in ("static", "tests", "infra", "audit"):
        assert f"scripts.checks.run_all {group}" in _recipe(f"check-{group}")


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


def test_setup_installs_all_hook_types() -> None:
    recipe = _recipe("setup")
    assert "uv sync --locked" in recipe
    assert "scripts.tools.install" in recipe
    assert "pre-commit install" in recipe
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    assert set(config["default_install_hook_types"]) == {"pre-commit", "commit-msg", "pre-push"}


def test_test_fast_uses_the_dev_profile_and_fast_layers() -> None:
    recipe = _recipe("test-fast")
    assert "HYPOTHESIS_PROFILE=dev" in recipe
    assert "unit or property" in recipe


def test_mutation_target_lists_core_modules() -> None:
    assert "mutmut run" in _recipe("mutation")
    import tomllib

    mutmut = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["mutmut"]
    assert mutmut["paths_to_mutate"], "core modules for mutation testing must be listed"
    assert "src/fantadamus/core/" in mutmut["paths_to_mutate"]


def test_skeleton_target_checks_the_golden_file() -> None:
    recipe = _recipe("skeleton")
    assert "fantadamus skeleton run" in recipe
    assert "--golden tests/golden/skeleton/role_counts.json" in recipe


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
