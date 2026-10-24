"""Task 3.3: an installed tool whose version differs from its pin fails `make check` (R1.9)."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from scripts.checks import tool_versions
from scripts.tools.install import Tool

TERRAFORM = Tool(
    name="terraform",
    version="1.17.0",
    url="https://example.org/{version}/{asset}.zip",
    binary="terraform",
    version_args=("version",),
    assets={"darwin_amd64": "darwin_amd64"},
    sha256={"darwin_amd64": "0" * 64},
)


def _runner(output: str) -> tool_versions.Runner:
    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(args), 0, stdout=output, stderr="")

    return run


def _installed(tmp_path: Path) -> Path:
    (tmp_path / "terraform").write_text("#!/bin/sh\n")
    return tmp_path


def test_version_mismatch_fails(tmp_path: Path) -> None:
    result = tool_versions.check([TERRAFORM], _installed(tmp_path), run=_runner("Terraform v1.16.2\non darwin_amd64\n"))
    assert not result.ok
    assert "terraform: expected 1.17.0, found 1.16.2" in result.message


def test_matching_versions_pass(tmp_path: Path) -> None:
    result = tool_versions.check([TERRAFORM], _installed(tmp_path), run=_runner("Terraform v1.17.0\n"))
    assert result.ok


def test_missing_tool_fails_with_setup_hint(tmp_path: Path) -> None:
    result = tool_versions.check([TERRAFORM], tmp_path, run=_runner(""))
    assert not result.ok
    assert "make setup" in result.message
