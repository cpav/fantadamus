"""Silver `match_ratings`: a row per player, match and desk that published, its base rating or None for s.v.
(mvp-sources design C6; R4.2). Clubs by canonical key; names as the page writes them, resolved on read."""

from __future__ import annotations

from fantadamus.contracts.xy.ratings import RatingsPayload
from fantadamus.core.clubs import Clubs
from fantadamus.domains.facts import PROVENANCE_COLUMNS, Domain, SilverRow, Source
from fantadamus.lake.duckdb_store import Table


class MatchRatingRow(SilverRow):
    round: int
    home: str
    away: str
    club: str
    name: str
    role: str
    came_on: bool
    minutes: int | None
    desk: str
    rating: float | None
    """None: the desk saw him and gave no rating (s.v.)."""


def _rows(payload: RatingsPayload, clubs: Clubs, source: Source) -> list[MatchRatingRow]:
    return [
        MatchRatingRow(
            **source.model_dump(),
            round=payload.round,
            home=clubs.key(match.home),
            away=clubs.key(match.away),
            club=clubs.key(player.club),
            name=player.name,
            role=player.role,
            came_on=player.came_on,
            minutes=player.minutes,
            desk=rated.desk,
            rating=rated.rating,
        )
        for match in payload.matches
        for player in match.players
        for rated in player.ratings
    ]


MATCH_RATINGS = Domain(
    "match_ratings",
    RatingsPayload,
    MatchRatingRow,
    _rows,
    Table(
        "match_ratings",
        f"CREATE TEMP TABLE match_ratings ({PROVENANCE_COLUMNS}, round BIGINT, home VARCHAR, away VARCHAR, "
        "club VARCHAR, name VARCHAR, role VARCHAR, came_on BOOLEAN, minutes BIGINT, desk VARCHAR, "
        "rating DOUBLE)",
    ),
)
"""`RatingsPayload`: a round's base ratings from the Fantacalcio.it, Roma and Torino desks."""
