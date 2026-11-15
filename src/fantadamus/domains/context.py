"""A match's context, shown beside the numbers and never in them (mvp-sources design C3; R2.2, R2.3).

Rest days: for one side of a Serie A match, its nearest matches before and after in any competition, from the
Serie A fixtures and the other competitions' pages, with the whole days between them in Italian time, and
whether either is a European match within `EUROPEAN_WEEK_DAYS`. Nothing here moves a chance or a value
(decision 2): rest days are said, and their pages are at the bottom with the sources.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from fantadamus.domains.facts import Source
from fantadamus.domains.fixtures.silver import FixtureRow, OtherFixtureRow
from fantadamus.engine.constants import EUROPEAN_WEEK_DAYS

ROME = ZoneInfo("Europe/Rome")
SERIE_A = "Serie A"
EUROPEAN = frozenset({"Champions League", "Europa League", "Conference League"})
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
"""In English whatever the machine's locale: answers are."""


class Played(BaseModel):
    """One of a club's matches beside the one asked about."""

    competition: str
    opponent: str
    home: bool
    kickoff: dt.datetime
    """In Europe/Rome."""


class RestDays(BaseModel):
    """One side's rest before a Serie A match, and its time to the next."""

    previous: Played | None
    next: Played | None
    days_since: int | None
    days_to: int | None
    """Whole days between the dates of the kickoffs, in Italian time."""
    european_week: bool
    """A European match is within `EUROPEAN_WEEK_DAYS` of this one, before or after."""
    line: str | None
    """What to say: "Inter: 3 days' rest since the Champions League on Wednesday 28 October; …"."""


@dataclass(frozen=True)
class Rested:
    days: RestDays
    sources: list[Source]
    """The pages of the matches it names, the previous one's first."""


@dataclass(frozen=True)
class _Game:
    competition: str
    home: str
    away: str
    kickoff_at: dt.datetime
    source: Source


def rest_days(
    club: str,
    kickoff: dt.datetime,
    serie_a: Sequence[FixtureRow],
    other: Sequence[OtherFixtureRow],
    names: Mapping[str, str],
) -> Rested:
    """`club`'s rest days before its match at `kickoff`: from its other Serie A matches and its matches in the
    other competitions, each club by its key or, outside Serie A, its name; `names` gives the clubs' names."""
    games = [
        *(_Game(SERIE_A, row.home, row.away, row.kickoff_at, row.source) for row in serie_a),
        *(_Game(row.competition, row.home, row.away, row.kickoff_at, row.source) for row in other),
    ]
    mine = [game for game in games if club in (game.home, game.away)]
    previous = max((game for game in mine if game.kickoff_at < kickoff), key=_when, default=None)
    following = min((game for game in mine if game.kickoff_at > kickoff), key=_when, default=None)
    days_since = _days(previous.kickoff_at, kickoff) if previous else None
    days_to = _days(kickoff, following.kickoff_at) if following else None
    european_week = any(
        game is not None and gap is not None and game.competition in EUROPEAN and gap <= EUROPEAN_WEEK_DAYS
        for game, gap in ((previous, days_since), (following, days_to))
    )
    days = RestDays(
        previous=_played(previous, club, names) if previous else None,
        next=_played(following, club, names) if following else None,
        days_since=days_since,
        days_to=days_to,
        european_week=european_week,
        line=_line(names.get(club, club), previous, days_since, following, days_to),
    )
    shown = dict.fromkeys(game.source for game in (previous, following) if game is not None)
    return Rested(days, list(shown))


def _when(game: _Game) -> dt.datetime:
    return game.kickoff_at


def _days(earlier: dt.datetime, later: dt.datetime) -> int:
    return (later.astimezone(ROME).date() - earlier.astimezone(ROME).date()).days


def _played(game: _Game, club: str, names: Mapping[str, str]) -> Played:
    home = game.home == club
    rival = game.away if home else game.home
    return Played(
        competition=game.competition,
        opponent=names.get(rival, rival),
        home=home,
        kickoff=game.kickoff_at.astimezone(ROME),
    )


def _competition(name: str) -> str:
    return name if name == SERIE_A else f"the {name}"


def _day(at: dt.datetime) -> str:
    local = at.astimezone(ROME)
    return f"{WEEKDAYS[local.weekday()]} {local.day} {MONTHS[local.month - 1]}"


def _count(days: int) -> str:
    return f"{days} day" if days == 1 else f"{days} days"


def _line(
    name: str, previous: _Game | None, days_since: int | None, following: _Game | None, days_to: int | None
) -> str | None:
    said = []
    if previous is not None and days_since is not None:
        rest = f"{_count(days_since)}'s rest" if days_since == 1 else f"{_count(days_since)}' rest"
        said.append(f"{rest} since {_competition(previous.competition)} on {_day(previous.kickoff_at)}")
    if following is not None and days_to is not None:
        said.append(
            f"{_count(days_to)} to {_competition(following.competition)} on {_day(following.kickoff_at)}"
        )
    return f"{name}: {'; '.join(said)}." if said else None
