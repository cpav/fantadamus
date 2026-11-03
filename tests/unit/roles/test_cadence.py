"""mvp-roles task 3.2: the statistics page is due once a day, whatever the matches, and season figures stay
fresh for 48 hours (design C5; R1.4)."""

from __future__ import annotations

import datetime as dt

from fantadamus.domains.freshness import is_fresh
from fantadamus.web.cadence import due

NOW = dt.datetime(2026, 11, 3, 8, 0, tzinfo=dt.UTC)
HOUR = dt.timedelta(hours=1)


def test_statistics_daily() -> None:
    assert due("player_season", None, NOW, None)
    assert not due("player_season", NOW - 23 * HOUR, NOW, None)
    assert due("player_season", NOW - 24 * HOUR, NOW, None)
    assert not due("player_season", NOW - 23 * HOUR, NOW, NOW + 2 * HOUR)  # a kickoff changes nothing


def test_season_figures_fresh_for_48_hours() -> None:
    assert is_fresh(NOW - 47 * HOUR, "player_season", as_of=NOW, kickoff=None)
    assert not is_fresh(NOW - 49 * HOUR, "player_season", as_of=NOW, kickoff=None)
    assert not is_fresh(NOW - 49 * HOUR, "player_season", as_of=NOW, kickoff=NOW + HOUR)
