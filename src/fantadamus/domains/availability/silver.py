"""Silver `lineup_views` and `official_lineups`: every listed name with its status, as the outlet wrote it
(R3.1, R4.1); and silver `injuries` and `suspensions`, who the injured and suspended pages list and why
(mvp-sources C4). Names are resolved to players on read, so a name becomes a player once his profile is in."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from fantadamus.contracts.xy.lineups import OfficialLineupPayload, OutletLineupPayload, ProbableLineupPayload
from fantadamus.contracts.xy.unavailable import InjuriesPayload, SuspensionsPayload
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
    unnamed_starters: int
    """His club's starters this lineup can't name: a player it leaves out may be one (mvp-x-or-y R4.2)."""


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
        OfficialLineupRow(
            **source.model_dump(),
            home=home,
            away=away,
            club=club,
            name=name,
            status=status,
            unnamed_starters=team.unnamed_starters,
        )
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
    ),
    newest_by=("home", "away", "outlet"),
)
OFFICIAL_LINEUPS = Domain(
    "official_lineup",
    OfficialLineupPayload,
    OfficialLineupRow,
    _official_rows,
    Table(
        "official_lineups",
        f"CREATE TEMP TABLE official_lineups ({PROVENANCE_COLUMNS}, home VARCHAR, away VARCHAR, "
        "club VARCHAR, name VARCHAR, status VARCHAR, unnamed_starters BIGINT)",
    ),
    newest_by=("home", "away"),
)


class OutletViewRow(SilverRow):
    """One outlet's percentage for one player, or the page's word that he's unavailable (mvp-collect C5)."""

    home: str
    away: str
    outlet: str
    club: str
    name: str
    role: str | None
    percent: float | None
    unavailable: bool


def _outlet_rows(payload: OutletLineupPayload, clubs: Clubs, source: Source) -> list[OutletViewRow]:
    home, away = _match(payload.home, payload.away, clubs)

    def row(club: str, name: str, role: str | None, percent: float | None) -> OutletViewRow:
        return OutletViewRow(
            **source.model_dump(),
            home=home,
            away=away,
            outlet=payload.outlet,
            club=club,
            name=name,
            role=role,
            percent=percent,
            unavailable=percent is None,
        )

    return [
        *(
            row(club, player.name, player.role, player.percent)
            for club, team in ((home, payload.home_team), (away, payload.away_team))
            for player in team.players
        ),
        *(
            row(club, name, None, None)
            for club, team in ((home, payload.home_team), (away, payload.away_team))
            for name in team.unavailable
        ),
    ]


OUTLET_VIEWS = Domain(
    "outlet_lineup",
    OutletLineupPayload,
    OutletViewRow,
    _outlet_rows,
    Table(
        "outlet_views",
        f"CREATE TEMP TABLE outlet_views ({PROVENANCE_COLUMNS}, home VARCHAR, away VARCHAR, outlet VARCHAR, "
        "club VARCHAR, name VARCHAR, role VARCHAR, percent DOUBLE, unavailable BOOLEAN)",
    ),
    newest_by=("home", "away", "outlet"),
)


class InjuryRow(SilverRow):
    club: str
    name: str
    kind: str
    body_part: str | None
    back_from: dt.date | None
    back_until: dt.date | None
    to_be_assessed: bool


def _injury_rows(payload: InjuriesPayload, clubs: Clubs, source: Source) -> list[InjuryRow]:
    return [
        InjuryRow(**source.model_dump(), club=clubs.key(row.club), **player.model_dump())
        for row in payload.clubs
        for player in row.players
    ]


INJURIES = Domain(
    "injuries",
    InjuriesPayload,
    InjuryRow,
    _injury_rows,
    Table(
        "injuries",
        f"CREATE TEMP TABLE injuries ({PROVENANCE_COLUMNS}, club VARCHAR, name VARCHAR, kind VARCHAR, "
        "body_part VARCHAR, back_from DATE, back_until DATE, to_be_assessed BOOLEAN)",
    ),
)
"""`InjuriesPayload`: each club's injured players, with the kind, body part and return the rules found."""


class SuspensionRow(SilverRow):
    club: str
    name: str
    status: Literal["banned", "one booking"]
    round: int | None
    """A round a banned player misses; None for one booking from a ban, or a ban whose rounds aren't given."""


def _rounds(rounds: list[int]) -> list[int | None]:
    """Each round banned; a ban whose rounds the page doesn't give is one row without a round."""
    return [*rounds] if rounds else [None]


def _suspension_rows(payload: SuspensionsPayload, clubs: Clubs, source: Source) -> list[SuspensionRow]:
    rows: list[SuspensionRow] = []
    for row in payload.clubs:
        club = clubs.key(row.club)
        for banned in row.banned:
            rows += [
                SuspensionRow(
                    **source.model_dump(), club=club, name=banned.name, status="banned", round=round
                )
                for round in _rounds(banned.rounds)
            ]
        rows += [
            SuspensionRow(**source.model_dump(), club=club, name=name, status="one booking", round=None)
            for name in row.one_booking
        ]
    return rows


SUSPENSIONS = Domain(
    "suspensions",
    SuspensionsPayload,
    SuspensionRow,
    _suspension_rows,
    Table(
        "suspensions",
        f"CREATE TEMP TABLE suspensions ({PROVENANCE_COLUMNS}, club VARCHAR, name VARCHAR, status VARCHAR, "
        "round BIGINT)",
    ),
)
"""`SuspensionsPayload`: a row per round each banned player misses, and one for each player a booking from a
ban."""
