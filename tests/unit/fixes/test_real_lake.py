"""mvp-fixes task 6.2: the real lake's answers compared field by field, each change counted by kind, and only
kinds, places and counts printed (design, real check; AT-8)."""

from __future__ import annotations

from typing import Any

from tests.real_lake import ABSENT, Change, Result, changes, field_lines, kind

BEFORE: dict[str, Any] = {
    "status": "lineup",
    "notes": ["Rossi takes Inter's penalties if Bianchi misses the start: they count at 100%.", "Unchanged."],
    "sources": [{"label": "Fantacalcio.it, table"}],
    "record": {"rounds": 2},
    "value": {"p_start": 0.87},
}
AFTER: dict[str, Any] = {
    "status": "lineup",
    "notes": [
        "Bianchi, first on Inter's list, is out, so Rossi takes the penalties: counted in full.",
        "Unchanged.",
    ],
    "sources": [{"label": "Fantacalcio.it, table"}, {"label": "Fantacalcio.it, statistics"}],
    "record": {"rounds": 2, "app_rounds": 0, "app_note": None},
    "value": {"p_start": 0.88},
}


def test_changes_are_listed_by_kind() -> None:
    found = changes(BEFORE, AFTER)
    assert [(change.path, kind(change)) for change in found] == [
        (("notes", "[]"), "penalty notes"),
        (("record", "app_note"), "new fields, empty"),
        (("record", "app_rounds"), "new fields, empty"),
        (("sources", "[]"), "sources"),
        (("value", "p_start"), "other: value/p_start"),
    ]
    assert found[3].before is ABSENT
    assert changes(BEFORE, BEFORE) == []
    assert kind(Change(("lineup", "updated", "oldest"), "a", "b")) == "updated, from the sources"
    assert kind(Change(("players", "[]", "Rossi"), "a", "b")) == "other: players/[]/…"  # never a name


def test_only_kinds_and_counts_are_printed() -> None:
    results = [
        Result(0, "best_lineup", "lineup", 10, 0.1, ""),
        Result(1, "round_overview", "overview", 10, 0.1, ""),
    ]
    lines = field_lines(results, [changes(BEFORE, AFTER), []])
    assert lines == [
        "00 best_lineup lineup: new fields, empty 2, other: value/p_start 1, penalty notes 1, sources 1",
        "01 round_overview overview: identical",
        "2 answers, 1 identical",
        "new fields, empty: 2 in 1 of 2 answers",
        "other: value/p_start: 1 in 1 of 2 answers",
        "penalty notes: 1 in 1 of 2 answers",
        "sources: 1 in 1 of 2 answers",
    ]
    assert not any("Rossi" in line or "0.8" in line for line in lines)
