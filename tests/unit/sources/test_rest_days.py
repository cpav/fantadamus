"""mvp-sources task 3.1: the rest-days line and its edges: whole days in Italian time, a European week's
bounds, and what's said when only one side of the match is known (design C3; R2.2)."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from fantadamus.domains.context import RestDays, rest_days
from fantadamus.domains.fixtures.silver import OtherFixtureRow
from fantadamus.domains.sources import describe

ROME = ZoneInfo("Europe/Rome")
KICKOFF = dt.datetime(2026, 10, 31, 15, 0, tzinfo=ROME)
CUP = "https://en.wikipedia.org/wiki/2026%E2%80%9327_Coppa_Italia?action=raw"
SOURCE = {
    "source_url": CUP,
    "captured_at": dt.datetime(2026, 10, 26, tzinfo=dt.UTC),
    "content_sha256": "0" * 64,
}


def _match(competition: str, at: dt.datetime, *, home: bool = True) -> OtherFixtureRow:
    rival = "Kessel"
    return OtherFixtureRow(
        **SOURCE,
        competition=competition,
        home="alfa" if home else rival,
        away=rival if home else "alfa",
        kickoff_at=at.astimezone(dt.UTC),
    )


def _days(*other: OtherFixtureRow) -> RestDays:
    return rest_days("alfa", KICKOFF.astimezone(dt.UTC), [], list(other), {"alfa": "Alfa"}).days


def test_nothing_known() -> None:
    assert _days().model_dump() == {
        "previous": None,
        "next": None,
        "days_since": None,
        "days_to": None,
        "european_week": False,
        "line": None,
    }


def test_one_day_and_one_side() -> None:
    """A day is said in the singular; with only the previous match known, only it is said."""
    days = _days(_match("Coppa Italia", dt.datetime(2026, 10, 30, 18, 0, tzinfo=ROME)))
    assert days.line == "Alfa: 1 day's rest since the Coppa Italia on Friday 30 October."
    later = _days(_match("Europa League", dt.datetime(2026, 11, 1, 18, 0, tzinfo=ROME), home=False))
    assert later.line == "Alfa: 1 day to the Europa League on Sunday 1 November."
    assert later.next is not None
    assert (later.next.opponent, later.next.home) == ("Kessel", False)


def test_whole_days_in_italian_time() -> None:
    """Days count between the dates in Italy: a kickoff at 00:30 on 28 October, Rome time, is 27 October in
    UTC, and still 3 days before Saturday 31 October."""
    days = _days(_match("Champions League", dt.datetime(2026, 10, 28, 0, 30, tzinfo=ROME)))
    assert days.days_since == 3
    assert days.previous is not None
    assert days.previous.kickoff == dt.datetime(2026, 10, 28, 0, 30, tzinfo=ROME)


@pytest.mark.parametrize(
    ("competition", "day", "european_week"),
    [
        ("Champions League", 28, True),  # 3 days before
        ("Conference League", 27, False),  # 4 days before
        ("Coppa Italia", 29, False),  # 2 days before, but not a European match
    ],
)
def test_a_european_week(competition: str, day: int, european_week: bool) -> None:
    """Within `EUROPEAN_WEEK_DAYS` (start: 3) of a European match, before or after."""
    assert (
        _days(_match(competition, dt.datetime(2026, 10, day, 21, 0, tzinfo=ROME))).european_week
        is european_week
    )
    after = _match(competition, dt.datetime(2026, 11, 31 - day, 21, 0, tzinfo=ROME))
    assert _days(after).european_week is european_week


def test_the_pages_are_labelled() -> None:
    """Each competition's page, at the bottom of an answer."""
    assert describe(CUP) == "Wikipedia, Coppa Italia"
    assert describe(CUP.replace("Coppa_Italia", "UEFA_Champions_League_league_phase")) == (
        "Wikipedia, Champions League"
    )
