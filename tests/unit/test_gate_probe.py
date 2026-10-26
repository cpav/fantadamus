"""Planted on purpose for task 15.2 (AT-3): a failing test must block the merge. Never merged."""

from __future__ import annotations


def test_gate_probe() -> None:
    assert 1 + 1 == 3, "planted failure: this pull request must not be mergeable"
