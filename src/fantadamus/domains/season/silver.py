"""Silver `player_seasons`, `season_stats`, `team_seasons` and `penalty_takers`, clubs by canonical key (R1.1,
R6; mvp-roles R1.1).

A player's identity (name, club, roles) is read from his latest row, so there is no separate `players` table:
a transfer shows up as soon as his new profile or the next statistics read is stored. A profile is one record
per player; a read of the statistics page is one record for every player it lists (mvp-roles C2), and gold
reads both tables as one.
"""

from __future__ import annotations

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy import once_each
from fantadamus.contracts.xy.season import (
    PenaltyTakersPayload,
    PlayerSeasonPayload,
    SeasonStatsPayload,
    TeamSeasonPayload,
)
from fantadamus.core.clubs import Clubs
from fantadamus.domains.facts import PROVENANCE_COLUMNS, Domain, SilverRow, Source, read_silver
from fantadamus.lake.duckdb_store import LakeStore, Table


class PlayerSeasonRow(SilverRow):
    player_id: int
    name: str
    club: str
    role: Role
    mantra_role: str | None
    appearances: int
    rated_appearances: int
    average_rating: float | None
    goals: int
    assists: int
    yellow_cards: int
    penalties_scored: int
    penalties_taken: int
    goals_conceded: int | None = None
    """A keeper's; none where the page doesn't say, and on rows stored before it was read."""


class TeamSeasonRow(SilverRow):
    club: str
    played: int
    goals_for: int
    goals_against: int


class PenaltyTakerRow(SilverRow):
    club: str
    rank: int
    name: str


def _player_rows(payload: PlayerSeasonPayload, clubs: Clubs, source: Source) -> list[PlayerSeasonRow]:
    figures = payload.model_dump(exclude={"club"})
    return [PlayerSeasonRow(**source.model_dump(), **figures, club=clubs.key(payload.club))]


def _stats_rows(payload: SeasonStatsPayload, clubs: Clubs, source: Source) -> list[PlayerSeasonRow]:
    """Every player of one read. A read that misses a club, or a club's keepers, is refused (mvp-roles
    R1.6)."""
    rows = [
        PlayerSeasonRow(
            **source.model_dump(), **player.model_dump(exclude={"club"}), club=clubs.key(player.club)
        )
        for player in payload.players
    ]
    for key, name in clubs.names.items():
        roles = {row.role for row in rows if row.club == key}
        if not roles:
            raise ValueError(f"the read has no players of {name}")
        if "P" not in roles:
            raise ValueError(f"the read has no keeper of {name}")
    return rows


def _team_rows(payload: TeamSeasonPayload, clubs: Clubs, source: Source) -> list[TeamSeasonRow]:
    rows = [
        TeamSeasonRow(**source.model_dump(), **team.model_dump(exclude={"club"}), club=clubs.key(team.club))
        for team in payload.teams
    ]
    once_each((row.club for row in rows), "{name} is listed twice")
    return rows


def _taker_rows(payload: PenaltyTakersPayload, clubs: Clubs, source: Source) -> list[PenaltyTakerRow]:
    rows = [
        PenaltyTakerRow(**source.model_dump(), club=clubs.key(entry.club), rank=rank, name=name)
        for entry in payload.clubs
        for rank, name in enumerate(entry.takers, start=1)
    ]
    once_each((row.club for row in rows if row.rank == 1), "{name} is listed twice")
    return rows


_SEASON_COLUMNS = (
    "player_id BIGINT, name VARCHAR, club VARCHAR, role VARCHAR, mantra_role VARCHAR, appearances BIGINT, "
    "rated_appearances BIGINT, average_rating DOUBLE, goals BIGINT, assists BIGINT, yellow_cards BIGINT, "
    "penalties_scored BIGINT, penalties_taken BIGINT, goals_conceded BIGINT"
)


PLAYER_SEASONS = Domain(
    "player_season",
    PlayerSeasonPayload,
    PlayerSeasonRow,
    _player_rows,
    Table(
        "player_seasons",
        f"CREATE TEMP TABLE player_seasons ({PROVENANCE_COLUMNS}, {_SEASON_COLUMNS})",
        "INSERT INTO player_seasons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    ),
)
SEASON_STATS = Domain(
    "season_stats",
    SeasonStatsPayload,
    PlayerSeasonRow,
    _stats_rows,
    Table(
        "season_stats",
        f"CREATE TEMP TABLE season_stats ({PROVENANCE_COLUMNS}, {_SEASON_COLUMNS})",
        "INSERT INTO season_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    ),
)
TEAM_SEASONS = Domain(
    "team_season",
    TeamSeasonPayload,
    TeamSeasonRow,
    _team_rows,
    Table(
        "team_seasons",
        f"CREATE TEMP TABLE team_seasons ({PROVENANCE_COLUMNS}, club VARCHAR, played BIGINT, "
        "goals_for BIGINT, goals_against BIGINT)",
        "INSERT INTO team_seasons VALUES (?, ?, ?, ?, ?, ?, ?)",
    ),
)
PENALTY_TAKERS = Domain(
    "penalty_takers",
    PenaltyTakersPayload,
    PenaltyTakerRow,
    _taker_rows,
    Table(
        "penalty_takers",
        f"CREATE TEMP TABLE penalty_takers ({PROVENANCE_COLUMNS}, club VARCHAR, rank BIGINT, name VARCHAR)",
        "INSERT INTO penalty_takers VALUES (?, ?, ?, ?, ?, ?)",
    ),
)


def read_player_seasons(store: LakeStore) -> list[PlayerSeasonRow]:
    """Every season-figures row, from profiles and statistics-page reads alike (mvp-roles C2)."""
    return [*read_silver(store, PLAYER_SEASONS), *read_silver(store, SEASON_STATS)]
