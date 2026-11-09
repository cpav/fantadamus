"""The lineup review: what a round left behind, worked out from what the pages said (mvp-review design C2;
R2.1, R2.3).

Pure. The statistics page gives each player's season so far, so one round is the difference between a read
made before it and a read made after it. Ratings come in half points and the page shows averages to two
decimals, so the rise in the average times the rated games pins the rating while that rounding can't reach a
quarter point: up to 24 rated games. After that, the fantasy average gives a second reading once
Fantacalcio.it's standard bonuses are taken off; checked against a real read on 2026-11-09, they are the ones
below, with no clean-sheet bonus, and an own goal shows as two points missing. Nothing is guessed: what can't
be pinned is unknown, with the reason."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

from fantadamus.domains.season.silver import PlayerSeasonRow

HALF = 0.5
ROUNDING = 0.005
"""How far a shown average can be from the true one: it's rounded to two decimals."""
_TOLERANCE = 1e-9

# Fantacalcio.it's standard bonuses, as its fantasy average applies them.
GOAL = 3.0
ASSIST = 1.0
YELLOW = -0.5
RED = -1.0
PENALTY_MISSED = -3.0
PENALTY_SAVED = 3.0
CONCEDED = -1.0
OWN_GOAL = -2.0


@dataclass(frozen=True)
class Read:
    """A player's season so far in one read of the statistics page. The last three counts are None in a read
    stored before Fantadamus read them, as is the fantasy average."""

    rated: int
    average: float | None
    fantasy: float | None
    goals: int
    assists: int
    yellows: int
    penalties_scored: int
    penalties_taken: int
    reds: int | None
    saved: int | None
    conceded: int | None
    keeper: bool

    @classmethod
    def of(cls, row: PlayerSeasonRow) -> Read:
        return cls(
            rated=row.rated_appearances,
            average=row.average_rating,
            fantasy=row.fantasy_average,
            goals=row.goals,
            assists=row.assists,
            yellows=row.yellow_cards,
            penalties_scored=row.penalties_scored,
            penalties_taken=row.penalties_taken,
            reds=row.red_cards,
            saved=row.penalties_saved,
            conceded=row.goals_conceded,
            keeper=row.role == "P",
        )


@dataclass(frozen=True)
class Events:
    """What he did in the round. None where the reads can't say."""

    open_goals: int
    penalties_scored: int
    penalties_missed: int
    assists: int
    yellows: int
    reds: int | None
    penalties_saved: int | None
    conceded: int | None
    own_goals: int | None


@dataclass(frozen=True)
class Round:
    """One player's round: his rating, None without one, and his events."""

    rating: float | None
    events: Events


@dataclass(frozen=True)
class Unknown:
    """Why a player's round can't be known."""

    reason: str


CORRECTED = Unknown("the page corrected a figure")


def player_round(before: Read | None, after: Read | None) -> Round | Unknown:
    """What the player did between a read made before the round and one made after it."""
    if before is None:
        return Unknown("not in the read before the round")
    if after is None:
        return Unknown("not in the read after the round")
    games = after.rated - before.rated
    if games > 1:
        return Unknown("two matches between the reads")
    events = _events(before, after)
    if games < 0 or events is None:
        return CORRECTED
    if games == 0:
        known = before.fantasy is not None or before.rated == 0
        return Round(None, dataclasses.replace(events, own_goals=0 if known else None))
    margin = ROUNDING * (before.rated + after.rated) + _TOLERANCE
    by_average = _half_points(
        _total(after.average, after.rated) - _total(before.average, before.rated), margin
    )
    if not by_average:
        return Unknown("his rating isn't on a half point")
    fantasy = _fantasy_reading(before, after, events)
    if len(by_average) == 1:
        rating = by_average[0]
        return Round(rating, dataclasses.replace(events, own_goals=_own_goals(fantasy, rating, margin)))
    both = [rating for rating in _half_points(fantasy, margin) if rating in by_average] if fantasy else []
    if len(both) == 1:
        return Round(both[0], dataclasses.replace(events, own_goals=0))
    return Unknown(f"his rating could be {' or '.join(f'{rating:g}' for rating in by_average)}")


def _events(before: Read, after: Read) -> Events | None:
    """The round's counts; None if one went down, which only a correction can do."""

    def gained(now: int, then: int) -> int:
        return now - then

    def maybe(now: int | None, then: int | None) -> int | None:
        return None if now is None or then is None else now - then

    goals = gained(after.goals, before.goals)
    scored = gained(after.penalties_scored, before.penalties_scored)
    taken = gained(after.penalties_taken, before.penalties_taken)
    events = Events(
        open_goals=goals - scored,
        penalties_scored=scored,
        penalties_missed=taken - scored,
        assists=gained(after.assists, before.assists),
        yellows=gained(after.yellows, before.yellows),
        reds=maybe(after.reds, before.reds),
        penalties_saved=maybe(after.saved, before.saved),
        conceded=maybe(after.conceded, before.conceded),
        own_goals=None,
    )
    counts = [goals, scored, taken, *(value for value in dataclasses.astuple(events) if value is not None)]
    return None if min(counts) < 0 else events


def _total(average: float | None, rated: int) -> float:
    return 0.0 if average is None else average * rated


def _half_points(centre: float, margin: float) -> list[float]:
    """Every half point within `margin` of `centre`."""
    low, high = math.ceil((centre - margin) / HALF), math.floor((centre + margin) / HALF)
    return [steps * HALF for steps in range(low, high + 1)]


def _fantasy_reading(before: Read, after: Read, events: Events) -> float | None:
    """His rating as the fantasy averages say it, taking off the round's standard bonuses and assuming no own
    goal; None where a read doesn't have them."""
    totals = [
        read.fantasy * read.rated if read.fantasy is not None else (0.0 if read.rated == 0 else None)
        for read in (before, after)
    ]
    if totals[0] is None or totals[1] is None or events.reds is None or events.penalties_saved is None:
        return None
    bonus = (
        GOAL * (events.open_goals + events.penalties_scored)
        + ASSIST * events.assists
        + YELLOW * events.yellows
        + RED * events.reds
        + PENALTY_MISSED * events.penalties_missed
    )
    if after.keeper:
        if events.conceded is None:
            return None
        bonus += PENALTY_SAVED * events.penalties_saved + CONCEDED * events.conceded
    return totals[1] - totals[0] - bonus


def _own_goals(fantasy: float | None, rating: float, margin: float) -> int | None:
    """With the rating pinned, two points missing from the fantasy reading for each own goal."""
    if fantasy is None:
        return None
    missing = rating - fantasy
    own = round(missing / -OWN_GOAL)
    return own if own >= 0 and abs(missing + OWN_GOAL * own) <= margin else None
