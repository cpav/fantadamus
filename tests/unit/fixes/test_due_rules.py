"""mvp-fixes task 6.3: each rule of the cadence's table at its edges, as pure tests, for the mutation run of
`web/cadence.py`. Until now the rules mvp-sources added were tested only through the lake (design, testing
strategy; R1.2)."""

from __future__ import annotations

import datetime as dt

from fantadamus.web.cadence import due, may_read_after

NOW = dt.datetime(2026, 11, 24, 9, 0, tzinfo=dt.UTC)
HOUR = dt.timedelta(hours=1)
DAY = 24 * HOUR


def test_ratings_the_morning_after() -> None:
    """Due once a round, 12 hours after its last kickoff, and not again once read then."""
    last = NOW - 12 * HOUR  # the round's last kickoff: the morning after is now
    assert not due("match_ratings", None, NOW, None)  # no round just played
    assert due("match_ratings", None, NOW, last)
    assert not due("match_ratings", None, NOW, last + HOUR)  # an hour before the morning
    assert due("match_ratings", last + HOUR, NOW, last)  # read before the morning
    assert not due("match_ratings", NOW, NOW, last)  # read at the morning itself
    assert not due("match_ratings", NOW, NOW + HOUR, last)  # and an hour later, nothing new


def test_other_competitions_daily_in_a_match_week() -> None:
    """Daily while one of their matches is in the coming week, its edges included; weekly otherwise."""
    for kickoff in (NOW, NOW + 2 * DAY, NOW + 7 * DAY):
        assert due("other_fixtures", NOW - DAY, NOW, kickoff), kickoff
        assert not due("other_fixtures", NOW - 23 * HOUR, NOW, kickoff), kickoff
    for outside in (None, NOW - HOUR, NOW + 7 * DAY + HOUR):
        assert not due("other_fixtures", NOW - DAY, NOW, outside), outside
        assert due("other_fixtures", NOW - 7 * DAY, NOW, outside), outside


def test_injuries_twice_a_day_before_the_round() -> None:
    """Every 12 hours in the 48 before the round's first kickoff, its edges included; daily otherwise."""
    for fact in ("injuries", "suspensions"):
        for kickoff in (NOW, NOW + 10 * HOUR, NOW + 48 * HOUR):
            assert due(fact, NOW - 12 * HOUR, NOW, kickoff), (fact, kickoff)
            assert not due(fact, NOW - 11 * HOUR, NOW, kickoff), (fact, kickoff)
        for outside in (None, NOW - HOUR, NOW + 49 * HOUR):
            assert not due(fact, NOW - 12 * HOUR, NOW, outside), (fact, outside)
            assert due(fact, NOW - DAY, NOW, outside), (fact, outside)


def test_lineups_every_three_hours_in_the_last_day() -> None:
    """From 24 hours before the kickoff, the lineups and the odds every 3 hours; before it, 12 and 24."""
    for fact in ("probable_lineups", "match_odds"):
        assert due(fact, NOW - 3 * HOUR, NOW, NOW + DAY), fact  # exactly a day before
        assert not due(fact, NOW - 3 * HOUR, NOW, NOW + 25 * HOUR), fact
    assert due("probable_lineups", NOW - 12 * HOUR, NOW, NOW + 25 * HOUR)
    assert due("match_odds", NOW - DAY, NOW, NOW + 25 * HOUR)


def test_an_answer_may_read_at_the_interval() -> None:
    """Its shortest interval since the site last answered, the edge included."""
    assert may_read_after("injuries", NOW - 12 * HOUR, None, NOW)
    assert not may_read_after("injuries", NOW - 11 * HOUR, None, NOW)
    assert may_read_after("statistics", NOW - DAY, NOW - dt.timedelta(minutes=15), NOW)
