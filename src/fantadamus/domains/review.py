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
from collections.abc import Mapping
from dataclasses import dataclass
from typing import get_args

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import EventName, LeagueRules
from fantadamus.domains.season.silver import PlayerSeasonRow
from fantadamus.engine.formula import Mark, formula_points
from fantadamus.engine.simulate import Move, Plan, fantasy_goals, field

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


@dataclass(frozen=True)
class RealScore:
    """What a lineup really scored, or None where a player's unknown round could change it (design C3)."""

    total: float | None
    fantasy_goals: int | None
    points: dict[int, float | None]
    """Each fielded player's real points, and None for a starter without a rating."""
    moves: list[Move]
    rules: dict[str, float]
    """What each formula rule really gave."""
    unknown: list[int]
    """Whoever's unknown round makes the score unknown."""
    not_counted: list[str]
    """The league's events the reads can't count for someone fielded, in the table's order."""


def real_score(
    rounds: Mapping[int, Round | Unknown],
    lineup: Plan,
    rules: LeagueRules,
    *,
    conceded: Mapping[int, int | None] | None = None,
    captain: int | None = None,
    vice: int | None = None,
) -> RealScore:
    """The lineup's real score as the league scores it: each player's rating and events at the table's
    values, the league's substitutions, its formula rules and captain on the real votes, and its thresholds.
    `conceded` is each outfield player's team's goals against in the round, for a league that scores them."""
    unknown = [player for player in lineup.starters if not isinstance(rounds.get(player), Round)]
    if unknown:
        return RealScore(None, None, {}, [], {}, unknown, [])
    bench = list(dict.fromkeys(player for options in lineup.options.values() for player in options))
    scored = {
        player: _points(found, lineup.role[player], rules, (conceded or {}).get(player))
        for player in (*lineup.starters, *bench)
        if isinstance(found := rounds.get(player), Round)
    }
    scores = {
        player: scored[player][0] if player in scored else None for player in (*lineup.starters, *bench)
    }
    total, moves = field(scores, lineup)
    unsure = [player for player in bench if player not in scored]
    if unsure:
        _, could_be = field({**scores, **dict.fromkeys(unsure, 0.0)}, lineup)
        if could_be != moves:
            return RealScore(None, None, {}, [], {}, [new for _, new in could_be if new in unsure], [])
    fielded = [player for player in lineup.starters if scores[player] is not None]
    fielded += [new for _, new in moves]
    marks = {  # every fielded player has a round with a rating
        player: _mark(found.rating, found.events, lineup.role[player])
        for player in fielded
        if isinstance(found := rounds[player], Round) and found.rating is not None
    }
    worth = {}
    for rule in rules.formula_rules:
        if rule.who == "captain":
            wearing = next((marks[player] for player in (captain, vice) if player in marks), None)
            worth[rule.name] = formula_points(rule, (), captain=wearing)
        else:
            worth[rule.name] = formula_points(rule, [marks[player] for player in fielded])
    total += math.fsum(worth.values())
    missing = {event for player in fielded for event in scored[player][1]}
    thresholds = rules.lineup.thresholds if rules.lineup is not None else None
    return RealScore(
        total=total,
        fantasy_goals=fantasy_goals(total, thresholds),
        points={player: scores[player] for player in (*lineup.starters, *(new for _, new in moves))},
        moves=moves,
        rules=worth,
        unknown=[],
        not_counted=[event for event in get_args(EventName) if event in missing],
    )


def _points(
    found: Round, role: Role, rules: LeagueRules, team_conceded: int | None
) -> tuple[float | None, set[str]]:
    """A player's real points, None without a rating, and the league's events the reads couldn't count."""
    if found.rating is None:
        return None, set()
    values: dict[str, float] = {row.event: row.points for row in rules.events if role in row.roles}
    events, missing = found.events, set()
    points = found.rating + math.fsum(
        values.get(event, 0.0) * count
        for event, count in (
            ("goal", events.open_goals),
            ("penalty_scored", events.penalties_scored),
            ("assist", events.assists),
            ("yellow_card", events.yellows),
            ("penalty_missed", events.penalties_missed),
        )
    )
    for event, maybe in (
        ("red_card", events.reds),
        ("own_goal", events.own_goals),
        ("penalty_saved", events.penalties_saved),
    ):
        if values.get(event):
            if maybe is None:
                missing.add(event)
            else:
                points += values[event] * maybe
    against = events.conceded if role == "P" else team_conceded
    for event in ("goal_conceded", "clean_sheet"):
        if values.get(event):
            if against is None:
                missing.add(event)
            else:
                points += values[event] * (against if event == "goal_conceded" else float(against == 0))
    if values.get("decisive_goal") and events.open_goals + events.penalties_scored:
        missing.add("decisive_goal")
    if values.get("set_piece_assist") and events.assists:
        missing.add("set_piece_assist")
    return points, missing


def _mark(rating: float, events: Events, role: Role) -> Mark:
    """What a formula rule reads of a fielded player: his real rating, and whether he scored, conceded or
    saved a penalty."""
    scored = events.open_goals + events.penalties_scored > 0
    kept = role == "P" and ((events.conceded or 0) > 0 or (events.penalties_saved or 0) > 0)
    return Mark(role, rating, scored or kept)
