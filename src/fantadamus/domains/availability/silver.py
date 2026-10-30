"""Silver `lineup_views` and `official_lineups`: every listed name with its status, as the outlet wrote it
(R3.1, R4.1). Names are resolved to players on read, so a name becomes a player once his profile is in."""

from __future__ import annotations

from typing import Literal

from fantadamus.contracts.xy.lineups import OfficialLineupPayload, ProbableLineupPayload
from fantadamus.core.clubs import Clubs
from fantadamus.domains.availability.consensus import Listed
from fantadamus.domains.facts import PROVENANCE_COLUMNS, Domain, RefusedError, SilverRow, Source
from fantadamus.lake.duckdb_store import Table


class LineupViewRow(SilverRow):
    home: str
    away: str
    outlet: str
    club: str
    name: str
    status: Listed
    share: float | None
    """His ballottaggio percentage."""
    contest: int | None = None
    """Which of his team's ballottaggi he's in, so his rivals can be named (R10.8)."""


class OfficialLineupRow(SilverRow):
    home: str
    away: str
    club: str
    name: str
    status: Literal["starter", "bench"]


def _match(home: str, away: str, clubs: Clubs) -> tuple[str, str]:
    keys = clubs.key(home), clubs.key(away)
    if keys[0] == keys[1]:
        raise RefusedError(f"{home} plays itself")
    return keys


def _probable_rows(payload: ProbableLineupPayload, clubs: Clubs, source: Source) -> list[LineupViewRow]:
    home, away = _match(payload.home, payload.away, clubs)
    rows: list[LineupViewRow] = []
    for club, team in ((home, payload.home_team), (away, payload.away_team)):
        listed: list[tuple[str, Listed, float | None, int | None]] = [
            *((name, "starter", None, None) for name in team.starters),
            *(
                (share.name, "ballottaggio", share.percent, index)
                for index, contest in enumerate(team.ballottaggi)
                for share in contest.players
            ),
            *((name, "bench", None, None) for name in team.bench),
            *((name, "unavailable", None, None) for name in team.unavailable),
        ]
        rows += [
            LineupViewRow(
                **source.model_dump(),
                home=home,
                away=away,
                outlet=payload.outlet,
                club=club,
                name=name,
                status=status,
                share=share,
                contest=contest,
            )
            for name, status, share, contest in listed
        ]
    return rows


def _official_rows(payload: OfficialLineupPayload, clubs: Clubs, source: Source) -> list[OfficialLineupRow]:
    home, away = _match(payload.home, payload.away, clubs)
    return [
        OfficialLineupRow(**source.model_dump(), home=home, away=away, club=club, name=name, status=status)
        for club, team in ((home, payload.home_team), (away, payload.away_team))
        for status, names in (("starter", team.starters), ("bench", team.bench))
        for name in names
    ]


LINEUP_VIEWS = Domain(
    "probable_lineups",
    ProbableLineupPayload,
    LineupViewRow,
    _probable_rows,
    Table(
        "lineup_views",
        f"CREATE TEMP TABLE lineup_views ({PROVENANCE_COLUMNS}, home VARCHAR, away VARCHAR, outlet VARCHAR, "
        "club VARCHAR, name VARCHAR, status VARCHAR, share DOUBLE, contest BIGINT)",
        "INSERT INTO lineup_views VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    ),
)
OFFICIAL_LINEUPS = Domain(
    "official_lineup",
    OfficialLineupPayload,
    OfficialLineupRow,
    _official_rows,
    Table(
        "official_lineups",
        f"CREATE TEMP TABLE official_lineups ({PROVENANCE_COLUMNS}, home VARCHAR, away VARCHAR, "
        "club VARCHAR, name VARCHAR, status VARCHAR)",
        "INSERT INTO official_lineups VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    ),
)
