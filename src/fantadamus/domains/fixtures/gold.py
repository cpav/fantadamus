"""As-of reads of the fixtures (design C6; R2.2, R7.4). For each match the highest-ranked source wins, with
its newest read, so a postponed match moves to its new round or kickoff (mvp-collect R5.1)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from fantadamus.domains.fixtures.silver import FixtureRow
from fantadamus.domains.sources import best_by


def matches(rows: Sequence[FixtureRow], as_of: dt.datetime) -> list[FixtureRow]:
    """Every match as known at `as_of`, by kickoff."""
    latest = best_by(rows, as_of, key=lambda row: (row.home, row.away))
    return sorted(latest.values(), key=lambda row: (row.kickoff_at, row.home))


def fixture(rows: Sequence[FixtureRow], club: str, round: int, as_of: dt.datetime) -> FixtureRow | None:
    """The club's match in the round, or None if it has none (R2.3)."""
    return next(
        (row for row in matches(rows, as_of) if row.round == round and club in (row.home, row.away)), None
    )


def deadline(rows: Sequence[FixtureRow], round: int, as_of: dt.datetime) -> dt.datetime | None:
    """The round's deadline: the kickoff of its first match (R2.2)."""
    return min((row.kickoff_at for row in matches(rows, as_of) if row.round == round), default=None)


def next_round(rows: Sequence[FixtureRow], as_of: dt.datetime) -> int | None:
    """The round being asked about: the next one whose deadline is after `as_of`."""
    deadlines: dict[int, dt.datetime] = {}
    for row in matches(rows, as_of):
        deadlines[row.round] = min(deadlines.get(row.round, row.kickoff_at), row.kickoff_at)
    upcoming = sorted((when, round) for round, when in deadlines.items() if when > as_of)
    return upcoming[0][1] if upcoming else None
