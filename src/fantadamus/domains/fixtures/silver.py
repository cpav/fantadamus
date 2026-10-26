"""Silver `fixtures`: every submitted match with its kickoff, clubs by canonical key (R2.1)."""

from __future__ import annotations

import datetime as dt

from fantadamus.contracts.xy import once_each
from fantadamus.contracts.xy.fixtures import FixturesPayload
from fantadamus.core.clubs import Clubs
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
