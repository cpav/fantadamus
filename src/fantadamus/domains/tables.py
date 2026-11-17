"""Every domain, once: the silver tables a lake can hold, and so what `fantadamus rebuild` goes through
(mvp-store C4)."""

from __future__ import annotations

from typing import Any

from fantadamus.domains.availability.silver import (
    INJURIES,
    LINEUP_VIEWS,
    OFFICIAL_LINEUPS,
    OUTLET_VIEWS,
    SUSPENSIONS,
)
from fantadamus.domains.facts import Domain
from fantadamus.domains.fixtures.silver import FIXTURES, OTHER_FIXTURES
from fantadamus.domains.odds.silver import ODDS
from fantadamus.domains.ratings.silver import MATCH_RATINGS
from fantadamus.domains.season.silver import PENALTY_TAKERS, PLAYER_SEASONS, SEASON_STATS, TEAM_SEASONS

DOMAINS: tuple[Domain[Any, Any], ...] = (
    FIXTURES,
    OTHER_FIXTURES,
    ODDS,
    LINEUP_VIEWS,
    OUTLET_VIEWS,
    OFFICIAL_LINEUPS,
    INJURIES,
    SUSPENSIONS,
    PLAYER_SEASONS,
    SEASON_STATS,
    TEAM_SEASONS,
    PENALTY_TAKERS,
    MATCH_RATINGS,
)
BY_TABLE: dict[str, Domain[Any, Any]] = {domain.table.name: domain for domain in DOMAINS}
