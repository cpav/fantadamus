"""mvp-store task 1.2: the month a row is stored under, and the months a window touches (design C1)."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.lake.months import MONTH, month_of, months_in

ROME = dt.timezone(dt.timedelta(hours=1))
NAMES = ["2026-09", "2026-10", "2026-11", "2026-12", "2027-01"]


def at(year: int, month: int, day: int, hour: int = 12) -> dt.datetime:
    return dt.datetime(year, month, day, hour, tzinfo=dt.UTC)


def test_a_row_goes_to_the_month_it_was_captured_in() -> None:
    assert month_of(at(2026, 11, 15)) == "2026-11"
    assert month_of(at(2027, 1, 1, 0)) == "2027-01"
    # The month is UTC's: half past midnight on 1 December in Rome is still November.
    assert month_of(dt.datetime(2026, 12, 1, 0, 30, tzinfo=ROME)) == "2026-11"
    with pytest.raises(ValueError, match=r"^a month needs a timezone-aware time$"):
        month_of(dt.datetime(2026, 11, 15, 12))
    assert MONTH.fullmatch("2026-11")
    assert not MONTH.fullmatch("2026-13")
    assert not MONTH.fullmatch("numbers")


def test_the_files_of_a_window() -> None:
    assert months_in(NAMES, at(2026, 10, 20), at(2026, 11, 3)) == ["2026-10", "2026-11"]
    assert months_in(NAMES, at(2026, 11, 1, 0), at(2026, 11, 30, 23)) == ["2026-11"]
    assert months_in(NAMES, since=at(2026, 12, 5)) == ["2026-12", "2027-01"]
    assert months_in(NAMES, until=at(2026, 9, 30)) == ["2026-09"]
    assert months_in(NAMES, at(2025, 1, 1), at(2025, 2, 1)) == []
    assert months_in(reversed(NAMES), at(2026, 10, 20), at(2026, 11, 3)) == [
        "2026-10",
        "2026-11",
    ]  # oldest first


def test_without_a_window_every_file() -> None:
    assert months_in(NAMES) == NAMES
    assert months_in([]) == []
