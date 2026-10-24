"""Task 4.1: format, lint and type checks are configured as the requirements demand (R4, R5, R6.1, R6.4)."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _pyproject() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_ruff_selects_bugbear_and_bandit() -> None:
    lint = _pyproject()["tool"]["ruff"]["lint"]
    selected = set(lint["select"])
    assert {"B", "S"} <= selected, "bugbear and bandit rules are required (R4.2)"
    assert {"PGH", "RUF"} <= selected, "blanket and unused suppressions must be caught (R6.1, R6.4)"
    assert not lint.get("ignore"), "no project-wide ignores: exceptions are per file and registered (R6.3)"


def test_mypy_strict_paths() -> None:
    mypy = _pyproject()["tool"]["mypy"]
    assert mypy["strict"] is True
    assert {"src", "scripts", "tests"} <= set(mypy["files"])
    assert mypy["warn_unused_ignores"] is True
    assert "ignore-without-code" in mypy["enable_error_code"]


def test_linters_configured() -> None:
    assert "dialect = duckdb" in (ROOT / ".sqlfluff").read_text(encoding="utf-8")
    assert "extends: default" in (ROOT / ".yamllint.yaml").read_text(encoding="utf-8")
    assert "config:" in (ROOT / ".markdownlint-cli2.yaml").read_text(encoding="utf-8")
    assert "actionlint" in (ROOT / "tool-versions.toml").read_text(encoding="utf-8")
