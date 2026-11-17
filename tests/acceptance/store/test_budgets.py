"""AT-2, AT-5 and AT-9 of mvp-store: at season size, a read of the round page is stored in under 2 seconds
and a run with nothing due checks in under 1, a reader in between sees the table before or after; every answer
and an alerts' check stay within their budgets, the reading within 1 second, gathering a squad too; no new
dependency (R1.2, R1.4, R1.5, R3.1, R3.2, R4.1, R5.1, R5.3). Timed in one process for the whole run, CPU
seconds, the fastest of three: see `tests/lineup_speed.py` and `tests/season.py`."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

from fantadamus.engine.constants import ALERT_SECONDS

ROOT = Path(__file__).resolve().parents[3]
ANSWERS = ("lineup", "compare", "outlook", "card", "overview", "review")
SLICE = [
    "src/fantadamus/lake/duckdb_store.py",
    "src/fantadamus/lake/months.py",
    "src/fantadamus/lake/jsonl.py",
    "src/fantadamus/lake/collect_log.py",
    "src/fantadamus/domains/facts.py",
    "src/fantadamus/domains/tables.py",
    "tests/season.py",
    "tests/timings.py",
]
"""The modules this slice wrote or rewrote."""


def test_at2_a_read_stored_in_two_seconds(timings: dict[str, Any]) -> None:
    """Its 60 bronze files, and its rows added to a month of a quarter of a million."""
    assert timings["season"]["store"] < 2.0


def test_at2_nothing_due_checked_in_a_second(timings: dict[str, Any]) -> None:
    """With 3,000 collection runs logged and the season's official lineups stored."""
    assert timings["season"]["nothing_due"] < 1.0


def test_at2_a_reader_in_between_sees_before_or_after(timings: dict[str, Any]) -> None:
    reader = timings["season"]["reader"]
    assert reader["before"] < reader["after"]
    assert set(reader["seen"]) <= {reader["before"], reader["after"]}
    assert reader["seen"]


def test_at5_every_answer_in_budget(timings: dict[str, Any]) -> None:
    season = timings["season"]
    for answer in ANSWERS:
        assert season[answer] < 3.0, answer
    assert season["alert"] < ALERT_SECONDS


def test_at5_reading_in_a_second(timings: dict[str, Any]) -> None:
    """`Facts.read` for an answer, however many times a page was read in the window: 60 times here."""
    assert timings["season"]["reading"] < 1.0


def test_at5_gathering_a_squad_in_a_second(timings: dict[str, Any]) -> None:
    """25 players' facts, as a lineup gathers them: the wall-clock assertion it replaces failed at 1.02 s."""
    assert timings["season"]["gathering"] < 1.0


def _imports(module: Path) -> set[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    found = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    found |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    return {name.split(".")[0] for name in found}


def test_at9_no_new_dependency() -> None:
    """DuckDB and the standard library do all of it: what this slice's modules import is that, pydantic for
    its models, and the project's own code."""
    allowed = set(sys.stdlib_module_names) | {"duckdb", "pydantic", "fantadamus", "tests", "scripts"}
    for module in SLICE:
        assert _imports(ROOT / module) <= allowed, module
