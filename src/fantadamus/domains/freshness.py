"""How long each fact stays fresh before `compare_players` asks for it again (R7.3)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fantadamus.engine.constants import FRESH_FOR_HOURS, FRESH_NEAR_MATCH_HOURS, NEAR_MATCH_HOURS

Fact = Literal["fixtures", "probable_lineups", "match_odds", "player_season", "team_season", "penalty_takers"]


def target(fact: Fact, *, as_of: dt.datetime, kickoff: dt.datetime | None) -> dt.timedelta:
    """The fact's freshness target; lineups and odds tighten within 24 hours of the kickoff."""
    near = kickoff is not None and kickoff - as_of <= dt.timedelta(hours=NEAR_MATCH_HOURS)
    hours = FRESH_NEAR_MATCH_HOURS.get(fact, FRESH_FOR_HOURS[fact]) if near else FRESH_FOR_HOURS[fact]
    return dt.timedelta(hours=hours)


def is_fresh(
    captured_at: dt.datetime, fact: Fact, *, as_of: dt.datetime, kickoff: dt.datetime | None
) -> bool:
    return as_of - captured_at <= target(fact, as_of=as_of, kickoff=kickoff)
