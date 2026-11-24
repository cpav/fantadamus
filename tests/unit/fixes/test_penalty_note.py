"""mvp-fixes task 4.1: when everyone listed ahead of a taker is out, the note says so; when anyone ahead may
start, it keeps the share (design C7; R4.1, R4.2)."""

from __future__ import annotations

from fantadamus.mcp.advisor import share_note


def test_everyone_ahead_out() -> None:
    assert share_note("Beta Nove", "Beta", ["Beta Quattordici"], 1.0) == (
        "Beta Quattordici, first on Beta's list, is out, so Beta Nove takes the penalties: counted in full."
    )


def test_two_ahead_out() -> None:
    assert share_note("Beta Dieci", "Beta", ["Beta Quattordici", "Beta Nove"], 1.0) == (
        "Beta Quattordici and Beta Nove, listed ahead of him on Beta's list, are out, so Beta Dieci takes "
        "the penalties: counted in full."
    )


def test_someone_ahead_may_start() -> None:
    assert share_note("Beta Dieci", "Beta", ["Beta Nove"], 0.4) == (
        "Beta Dieci takes Beta's penalties if Beta Nove misses the start: they count at 40%."
    )
    assert share_note("Beta Dieci", "Beta", ["Beta Nove"], 0.995) == (
        "Beta Dieci takes Beta's penalties if Beta Nove misses the start: they count at 100%."
    )  # rounded to 100%, but Beta Nove may still start: not "out"
    assert share_note("Beta Dieci", "Beta", ["Beta Nove"], 0.05) is None  # below what's worth a word
    assert share_note("Beta Nove", "Beta", [], 1.0) is None  # first on the list: nothing to say
