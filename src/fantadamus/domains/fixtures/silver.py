"""Silver `fixtures`: every submitted match with its kickoff, clubs by canonical key (R2.1); and silver
`other_fixtures`: the Serie A clubs' matches in the other competitions (mvp-sources C2)."""

from __future__ import annotations

import datetime as dt

from fantadamus.contracts.xy import once_each
from fantadamus.contracts.xy.fixtures import FixturesPayload, OtherFixturesPayload
from fantadamus.core.clubs import Clubs, UnknownClubError
from fantadamus.domains.facts import PROVENANCE_COLUMNS, Domain, SilverRow, Source
from fantadamus.lake.duckdb_store import Table


class FixtureRow(SilverRow):
    round: int
    home: str
    away: str
    kickoff_at: dt.datetime


def _rows(payload: FixturesPayload, clubs: Clubs, source: Source) -> list[FixtureRow]:
    rows = [
        FixtureRow(
            **source.model_dump(),
            round=payload.round,
            home=clubs.key(match.home),
            away=clubs.key(match.away),
            kickoff_at=match.kickoff_at,
        )
        for match in payload.matches
    ]
    once_each((club for row in rows for club in (row.home, row.away)), "{name} plays twice")
    return rows


TABLE = Table(
    "fixtures",
    f"CREATE TEMP TABLE fixtures ({PROVENANCE_COLUMNS}, round BIGINT, home VARCHAR, away VARCHAR, "
    "kickoff_at TIMESTAMPTZ)",
    "INSERT INTO fixtures VALUES (?, ?, ?, ?, ?, ?, ?)",
)
FIXTURES = Domain("fixtures", FixturesPayload, FixtureRow, _rows, TABLE)


class OtherFixtureRow(SilverRow):
    competition: str
    home: str
    """A Serie A club by its key, any other by the name the page gives it; as `away`."""
    away: str
    kickoff_at: dt.datetime


def _serie_a(clubs: Clubs, name: str) -> str | None:
    try:
        return clubs.key(name)
    except UnknownClubError:
        return None


def _other_rows(payload: OtherFixturesPayload, clubs: Clubs, source: Source) -> list[OtherFixtureRow]:
    """A row for each match with a Serie A club: the others' matches aren't ours to keep."""
    rows = []
    for match in payload.matches:
        home, away = _serie_a(clubs, match.home), _serie_a(clubs, match.away)
        if home is not None or away is not None:
            rows.append(
                OtherFixtureRow(
                    **source.model_dump(),
                    competition=payload.competition,
                    home=home or match.home,
                    away=away or match.away,
                    kickoff_at=match.kickoff_at,
                )
            )
    return rows


OTHER_TABLE = Table(
    "other_fixtures",
    f"CREATE TEMP TABLE other_fixtures ({PROVENANCE_COLUMNS}, competition VARCHAR, home VARCHAR, "
    "away VARCHAR, kickoff_at TIMESTAMPTZ)",
    "INSERT INTO other_fixtures VALUES (?, ?, ?, ?, ?, ?, ?)",
)
OTHER_FIXTURES = Domain("other_fixtures", OtherFixturesPayload, OtherFixtureRow, _other_rows, OTHER_TABLE)
