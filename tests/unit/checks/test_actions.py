"""The actionlint wrapper passes while there are no workflows and reports actionlint's findings otherwise."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from scripts.checks import actions
from scripts.checks._common import Runner


def _runner(code: int, output: str = "") -> Runner:
    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        assert args[0].endswith("bin/actionlint")
        return subprocess.CompletedProcess(list(args), code, stdout=output, stderr="")

    return run


def test_no_workflows_passes(tmp_path: Path) -> None:
    assert actions.check(tmp_path, run=_runner(1)).message == "no workflows yet"


def test_workflow_findings_fail(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("on: push\n", encoding="utf-8")
    assert actions.check(tmp_path, run=_runner(0)).ok
    result = actions.check(tmp_path, run=_runner(1, "ci.yml:1:1: jobs section is missing"))
    assert not result.ok
    assert "jobs section is missing" in result.message
