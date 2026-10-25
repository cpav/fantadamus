"""Each check runs as `python -m scripts.checks.<name>` and exits 0 or 1 with its summary line."""

from __future__ import annotations

import runpy
import sys

import pytest


@pytest.mark.parametrize(
    "module",
    ["adr_lint", "suppressions", "thresholds", "coverage_gate", "lockfile", "tool_versions", "contracts"],
)
def test_module_exits_with_its_result(
    module: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Run it as a fresh __main__, as `python -m` would, rather than over the already-imported module.
    monkeypatch.delitem(sys.modules, f"scripts.checks.{module}", raising=False)
    monkeypatch.setattr(sys, "argv", [module])
    with pytest.raises(SystemExit) as exited:
        runpy.run_module(f"scripts.checks.{module}", run_name="__main__")
    assert exited.value.code in (0, 1)
    captured = capsys.readouterr()
    assert (captured.out + captured.err).startswith(("PASS ", "FAIL "))
