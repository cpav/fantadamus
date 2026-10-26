"""Silver `player_seasons`, `team_seasons` and `penalty_takers`, clubs by canonical key (R1.1, R6).

A player's identity (name, club, roles) is read from his latest profile row, so there is no separate
`players` table: a transfer shows up as soon as his new profile is submitted.
"""

from __future__ import annotations

from fantadamus.contracts.xy import once_each
from fantadamus.contracts.xy.season import PenaltyTakersPayload, PlayerSeasonPayload, TeamSeasonPayload
from fantadamus.core.clubs import Clubs
from fantadamus.domains.facts import PROVENANCE_COLUMNS, Domain, SilverRow, Source
from fantadamus.lake.duckdb_store import Table


class PlayerSeasonRow(SilverRow):
    player_id: int
    name: str
    club: str
    role: str
    mantra_role: str | None
    appearances: int
    rated_appearances: int
    average_rating: float | None
    goals: int
    assists: int
    yellow_cards: int
    penalties_scored: int
    penalties_taken: int


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


PLAYER_SEASONS = Domain(
    "player_season",
    PlayerSeasonPayload,
    PlayerSeasonRow,
    _player_rows,
    Table(
        "player_seasons",
        f"CREATE TEMP TABLE player_seasons ({PROVENANCE_COLUMNS}, player_id BIGINT, name VARCHAR, "
        "club VARCHAR, role VARCHAR, mantra_role VARCHAR, appearances BIGINT, rated_appearances BIGINT, "
        "average_rating DOUBLE, goals BIGINT, assists BIGINT, yellow_cards BIGINT, penalties_scored BIGINT, "
        "penalties_taken BIGINT)",
        "INSERT INTO player_seasons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
