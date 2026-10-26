"""Task 7.1: how long each fact stays fresh (R7.3)."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.domains.freshness import Fact, is_fresh, target

KICKOFF = dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC)
HOUR, DAY = dt.timedelta(hours=1), dt.timedelta(days=1)


@pytest.mark.parametrize(
    ("fact", "early", "late"),
    [
        ("probable_lineups", 12 * HOUR, 3 * HOUR),
        ("match_odds", 24 * HOUR, 6 * HOUR),
        ("player_season", 7 * DAY, 7 * DAY),
        ("team_season", 7 * DAY, 7 * DAY),
        ("penalty_takers", 7 * DAY, 7 * DAY),
        ("fixtures", 7 * DAY, 7 * DAY),
    ],
)
def test_targets_tighten_near_the_match(fact: Fact, early: dt.timedelta, late: dt.timedelta) -> None:
    assert target(fact, as_of=KICKOFF - 30 * HOUR, kickoff=KICKOFF) == early
    assert target(fact, as_of=KICKOFF - 24 * HOUR, kickoff=KICKOFF) == late
    assert target(fact, as_of=KICKOFF + HOUR, kickoff=KICKOFF) == late
    assert target(fact, as_of=KICKOFF, kickoff=None) == early
    as_of = KICKOFF - 2 * DAY
    assert is_fresh(as_of - early, fact, as_of=as_of, kickoff=KICKOFF)
    assert not is_fresh(as_of - early - dt.timedelta(seconds=1), fact, as_of=as_of, kickoff=KICKOFF)
