"""mvp-collect task 7.1: when each of the round page's facts is due for a fresh read (design C7; R7.1)."""

from __future__ import annotations

import datetime as dt

from fantadamus.web.cadence import due

KICKOFF = dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC)
HOUR, MINUTE = dt.timedelta(hours=1), dt.timedelta(minutes=1)


def test_cadence_table() -> None:
    # Probable lineups: nothing before 72 hours out; twice a day from then; every 3 hours in the last 24.
    assert not due("probable_lineups", None, KICKOFF - 73 * HOUR, KICKOFF)
    assert due("probable_lineups", None, KICKOFF - 71 * HOUR, KICKOFF)
    assert not due("probable_lineups", KICKOFF - 40 * HOUR, KICKOFF - 30 * HOUR, KICKOFF)
    assert due("probable_lineups", KICKOFF - 42 * HOUR, KICKOFF - 30 * HOUR, KICKOFF)
    assert not due("probable_lineups", KICKOFF - 22 * HOUR, KICKOFF - 20 * HOUR, KICKOFF)
    assert due("probable_lineups", KICKOFF - 23 * HOUR, KICKOFF - 20 * HOUR, KICKOFF)
    assert not due("probable_lineups", None, KICKOFF, KICKOFF)  # kicked off: nothing left to forecast
    # Odds: daily from 72 hours out; every 3 hours in the last 24.
    assert not due("match_odds", KICKOFF - 60 * HOUR, KICKOFF - 40 * HOUR, KICKOFF)
    assert due("match_odds", KICKOFF - 64 * HOUR, KICKOFF - 40 * HOUR, KICKOFF)
    assert due("match_odds", KICKOFF - 15 * HOUR, KICKOFF - 12 * HOUR, KICKOFF)
    # Official lineups: every 15 minutes from 75 minutes before kickoff, until confirmed.
    assert not due("official_lineups", None, KICKOFF - 76 * MINUTE, KICKOFF)
    assert due("official_lineups", None, KICKOFF - 75 * MINUTE, KICKOFF)
    assert not due("official_lineups", KICKOFF - 70 * MINUTE, KICKOFF - 60 * MINUTE, KICKOFF)
    assert due("official_lineups", KICKOFF - 75 * MINUTE, KICKOFF - 60 * MINUTE, KICKOFF)
    assert not due("official_lineups", None, KICKOFF - 60 * MINUTE, KICKOFF, confirmed=True)
    # Fixtures: weekly, whatever the matches.
    assert due("fixtures", None, KICKOFF, None)
    assert not due("fixtures", KICKOFF - 6 * 24 * HOUR, KICKOFF, None)
    assert due("fixtures", KICKOFF - 7 * 24 * HOUR, KICKOFF, None)
