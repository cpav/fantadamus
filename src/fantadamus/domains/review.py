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
import datetime as dt
import math
import statistics
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import BaseModel

from fantadamus.contracts.types import Role, UtcDatetime
from fantadamus.contracts.xy.league import EventName, LeagueRules, LineupRules
from fantadamus.core.names import name_key
from fantadamus.domains.season.silver import PlayerSeasonRow
from fantadamus.engine.constants import COIN_FLIP
from fantadamus.engine.formula import Mark, formula_points
from fantadamus.engine.lineup import ROLES, Arrangement, Candidate
from fantadamus.engine.simulate import Move, Plan, Simulated, fantasy_goals, field
from fantadamus.lake.decision_log import Decision

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


@dataclass(frozen=True)
class Picked:
    """A lineup by player ID: what was advised, what was fielded, or the advice with one choice applied."""

    formation: str
    starters: tuple[int, ...]
    bench: tuple[int, ...]
    """In the order the substitutes are asked."""
    captain: int | None
    vice: int | None


@dataclass(frozen=True)
class Advice:
    """The lineup Fantadamus advised for a round (design C5)."""

    formation: str
    starters: list[int]
    bench: list[int]
    captain: int | None
    vice: int | None
    as_of: dt.datetime
    replayed: bool = False
    """Replayed at the lock, because the user asked for no lineup before it."""

    def picked(self) -> Picked:
        return Picked(self.formation, tuple(self.starters), tuple(self.bench), self.captain, self.vice)


def last_advice(
    decisions: Iterable[Decision], *, user: str, team: str, round: int, lock: dt.datetime
) -> Advice | None:
    """The last lineup answer the user was given for the team before the lock. An override is logged with the
    advice it was priced against; an older override line without it is passed over for the answer before."""
    answers = sorted(
        (
            decision
            for decision in decisions
            if decision.kind == "lineup"
            and decision.user == user
            and decision.round == round
            and name_key(decision.team or "") == name_key(team)
            and decision.logged_at < lock
        ),
        key=lambda decision: decision.logged_at,
        reverse=True,
    )
    for answer in answers:
        if answer.override_cost is None and answer.formation and answer.starters is not None:
            return Advice(
                answer.formation,
                answer.starters,
                answer.bench or [],
                answer.captain,
                answer.vice,
                answer.as_of,
            )
        if (
            answer.advised_formation
            and answer.advised_starters is not None
            and answer.advised_bench is not None
        ):
            return Advice(
                answer.advised_formation,
                answer.advised_starters,
                answer.advised_bench,
                answer.advised_captain,
                answer.advised_vice,
                answer.as_of,
            )
    return None


def advice_for(
    decisions: Iterable[Decision],
    *,
    user: str,
    team: str,
    round: int,
    lock: dt.datetime,
    replay: Callable[[], Advice | None],
) -> Advice | None:
    """The advice the user was given, or, if they asked for none, the advice replayed at the lock (R3.5)."""
    told = last_advice(decisions, user=user, team=team, round=round, lock=lock)
    if told is not None:
        return told
    replayed = replay()
    return dataclasses.replace(replayed, replayed=True) if replayed is not None else None


ChoiceKind = Literal["player", "formation", "bench", "captain"]


@dataclass(frozen=True)
class Choice:
    """One way the fielded lineup differs from the advice, with what it was expected to cost at the lock and
    what it really did (design C6)."""

    kind: ChoiceKind
    fielded: tuple[int, ...]
    """Who the user picked: the player, the players, the first substitute, or the captain and vice."""
    advised: tuple[int, ...]
    """Whom that replaced; for the captain, the best pair for the eleven fielded."""
    expected_cost: float = 0.0
    """Expected points given up: positive costs, negative gains."""
    real_gain: float | None = None
    """What it really gave this round; None where a round isn't known."""
    unknown: tuple[int, ...] = ()
    """Whose unknown round hides the real result."""
    mattered: bool | None = None
    """The bench only: whether a substitute really came on for that role."""
    judged: Literal["cost", "even", "gain"] = "even"


@dataclass(frozen=True)
class Reviewed:
    """A round's review: the advice and the fielded lineup, expected and real, and each choice between
    them."""

    advice: Simulated
    fielded: Simulated
    advice_real: RealScore
    fielded_real: RealScore
    choices: list[Choice]
    total_cost: float
    total_gain: float | None
    position: Literal["below", "inside", "above"] | None
    """The fielded lineup's real score against its range of eight rounds out of ten."""
    replayed: bool = False


def formation_of(roles: Mapping[int, Role], eleven: Iterable[int]) -> str:
    """Defenders, midfielders and forwards, as `3-4-3`."""
    players = list(eleven)
    return "-".join(str(sum(roles[player] == role for player in players)) for role in ("D", "C", "A"))


def applied(lineup: Picked, choice: Choice, roles: Mapping[int, Role]) -> Picked:
    """`lineup` with only that choice made: a swap puts each fielded player in the advised one's place, and
    him in the fielded one's place on the bench; a captain or vice taken off the eleven goes."""
    if choice.kind == "captain":
        return dataclasses.replace(lineup, captain=choice.fielded[0], vice=(*choice.fielded, None)[1])
    if choice.kind == "bench":
        mine, theirs = choice.fielded[0], choice.advised[0]
        swap = {mine: theirs, theirs: mine} if mine in lineup.bench else {theirs: mine}
        return dataclasses.replace(lineup, bench=tuple(swap.get(player, player) for player in lineup.bench))
    into = dict(zip(choice.advised, choice.fielded, strict=True))
    back = {new: old for old, new in into.items()}
    starters = tuple(into.get(player, player) for player in lineup.starters)
    captain = lineup.captain if lineup.captain in starters else None
    return Picked(
        formation=formation_of(roles, starters),
        starters=starters,
        bench=tuple(back.get(player, player) for player in lineup.bench),
        captain=captain,
        vice=lineup.vice if captain is not None and lineup.vice in starters else None,
    )


def review_choices(
    advice: Picked,
    fielded: Picked,
    squad: Sequence[Candidate],
    rules: LineupRules,
    *,
    price: Callable[[Sequence[Arrangement]], Sequence[Simulated]],
    score: Callable[[Arrangement, int | None, int | None], RealScore],
    replayed: bool = False,
) -> Reviewed:
    """Each way the fielded lineup differs from the advice, priced over one simulation at the lock's facts,
    with what it really did (design C6). `price` simulates arrangements; `score` gives one's real score with a
    captain and vice."""
    by_id = {player.player_id: player for player in squad}
    roles = {player.player_id: player.role for player in squad}
    swaps = _swaps(advice, fielded, by_id)
    swapped = advice
    for choice in swaps:
        swapped = applied(swapped, choice, roles)
    benches = [
        Choice("bench", (mine,), (theirs,))
        for role in ROLES
        if (mine := _first(fielded.bench, role, by_id)) is not None
        and (theirs := _first(swapped.bench, role, by_id)) is not None
        and mine != theirs
    ]
    pair = tuple(player for player in (fielded.captain, fielded.vice) if player is not None)
    captain = fielded.captain is not None and (fielded.captain, fielded.vice) != (
        swapped.captain,
        swapped.vice,
    )
    undone = [applied(fielded, Choice("bench", choice.advised, choice.fielded), roles) for choice in benches]
    best_for_fielded = dataclasses.replace(fielded, captain=None, vice=None)
    lineups = [
        advice,
        fielded,
        best_for_fielded,
        *(applied(advice, choice, roles) for choice in swaps),
        *undone,
    ]
    priced = price([_arranged(lineup, by_id) for lineup in lineups])
    reals = [
        score(_arranged(lineup, by_id), found.captain, found.vice)
        for lineup, found in zip(lineups, priced, strict=True)
    ]
    advice_sim, fielded_sim, best_sim = priced[:3]
    advice_real, fielded_real, best_real = reals[:3]
    reviewed = [
        _judged(choice, advice_sim.mean - found.mean, real, advice_real, None)
        for choice, found, real in zip(swaps, priced[3:], reals[3:], strict=False)
    ]
    for choice, found, real in zip(benches, priced[3 + len(swaps) :], reals[3 + len(swaps) :], strict=True):
        role = roles[choice.fielded[0]]
        mattered = (
            any(roles[out] == role for out, _ in fielded_real.moves)
            if fielded_real.total is not None
            else None
        )
        reviewed.append(_judged(choice, found.mean - fielded_sim.mean, fielded_real, real, mattered))
    if captain:
        best = tuple(player for player in (best_sim.captain, best_sim.vice) if player is not None)
        choice = Choice("captain", pair, best)
        reviewed.append(_judged(choice, best_sim.mean - fielded_sim.mean, fielded_real, best_real, None))
    return Reviewed(
        advice=advice_sim,
        fielded=fielded_sim,
        advice_real=advice_real,
        fielded_real=fielded_real,
        choices=reviewed,
        total_cost=advice_sim.mean - fielded_sim.mean,
        total_gain=_gain(fielded_real, advice_real),
        position=_position(fielded_real.total, fielded_sim),
        replayed=replayed,
    )


def _swaps(advice: Picked, fielded: Picked, by_id: Mapping[int, Candidate]) -> list[Choice]:
    """The players in others' places, each role's paired best key first, then the formation: those left
    over."""

    def best_first(player: int) -> tuple[float, int]:
        return -by_id[player].key, player

    swaps: list[Choice] = []
    left_out: list[int] = []
    brought_in: list[int] = []
    for role in ROLES:
        out = sorted(
            (
                player
                for player in advice.starters
                if by_id[player].role == role and player not in fielded.starters
            ),
            key=best_first,
        )
        into = sorted(
            (
                player
                for player in fielded.starters
                if by_id[player].role == role and player not in advice.starters
            ),
            key=best_first,
        )
        swaps += [Choice("player", (new,), (old,)) for old, new in zip(out, into, strict=False)]
        left_out += out[len(into) :]
        brought_in += into[len(out) :]
    if left_out:
        swaps.append(Choice("formation", tuple(brought_in), tuple(left_out)))
    return swaps


def _first(bench: Sequence[int], role: Role, by_id: Mapping[int, Candidate]) -> int | None:
    """The first substitute of a role: the first of his role on the bench."""
    return next((player for player in bench if by_id[player].role == role), None)


def _arranged(lineup: Picked, by_id: Mapping[int, Candidate]) -> Arrangement:
    """The lineup as the engine takes it: starters by role and key, so their order doesn't matter, the bench
    in the order given, and a captain and vice only if they start."""
    rank = {role: index for index, role in enumerate(ROLES)}
    starters = sorted(
        (by_id[player] for player in lineup.starters), key=lambda c: (rank[c.role], -c.key, c.player_id)
    )
    used = {*lineup.starters, *lineup.bench}
    captain = lineup.captain if lineup.captain in lineup.starters else None
    return Arrangement(
        formation=lineup.formation,
        starters=tuple(starters),
        bench=tuple(by_id[player] for player in lineup.bench),
        left_off=tuple(player for player in by_id.values() if player.player_id not in used),
        captain=captain,
        vice=lineup.vice if captain is not None and lineup.vice in lineup.starters else None,
    )


def _gain(made: RealScore, instead: RealScore) -> float | None:
    if made.total is None or instead.total is None:
        return None
    return made.total - instead.total


def _judged(
    choice: Choice, cost: float, made: RealScore, instead: RealScore, mattered: bool | None
) -> Choice:
    """The choice with its expected cost, its real result, and the judgement, which goes by the cost."""
    gain = _gain(made, instead)
    return dataclasses.replace(
        choice,
        expected_cost=cost,
        real_gain=gain,
        unknown=() if gain is not None else tuple(made.unknown or instead.unknown),
        mattered=mattered,
        judged="cost" if cost > COIN_FLIP else "gain" if cost < -COIN_FLIP else "even",
    )


def _position(total: float | None, expected: Simulated) -> Literal["below", "inside", "above"] | None:
    if total is None:
        return None
    return "below" if total < expected.low else "above" if total > expected.high else "inside"


class LoggedChoice(BaseModel):
    kind: ChoiceKind
    fielded: list[int]
    advised: list[int]
    expected_cost: float
    real_gain: float | None
    judged: Literal["cost", "even", "gain"]
    mattered: bool | None = None


class LoggedReview(BaseModel):
    """One review as the review log keeps it, privately (design C7; R4.1)."""

    user: str
    team: str
    round: int
    as_of: UtcDatetime
    """The lock, whose facts priced it."""
    logged_at: UtcDatetime
    replayed: bool
    advice_expected: float
    fielded_expected: float
    advice_real: float | None
    fielded_real: float | None
    total_cost: float
    total_gain: float | None
    choices: list[LoggedChoice]
    content_hashes: list[str]
    """The snapshots it used."""


def logged(
    reviewed: Reviewed,
    *,
    user: str,
    team: str,
    round: int,
    as_of: dt.datetime,
    logged_at: dt.datetime,
    content_hashes: Sequence[str],
) -> LoggedReview:
    return LoggedReview(
        user=user,
        team=team,
        round=round,
        as_of=as_of,
        logged_at=logged_at,
        replayed=reviewed.replayed,
        advice_expected=reviewed.advice.mean,
        fielded_expected=reviewed.fielded.mean,
        advice_real=reviewed.advice_real.total,
        fielded_real=reviewed.fielded_real.total,
        total_cost=reviewed.total_cost,
        total_gain=reviewed.total_gain,
        choices=[
            LoggedChoice(
                kind=choice.kind,
                fielded=list(choice.fielded),
                advised=list(choice.advised),
                expected_cost=choice.expected_cost,
                real_gain=choice.real_gain,
                judged=choice.judged,
                mattered=choice.mattered,
            )
            for choice in reviewed.choices
        ],
        content_hashes=list(content_hashes),
    )


FEWEST_TO_TELL = 3
"""*(start)* Rounds with an override and a known gain before the record says anything but "too early"."""
Verdict = Literal["too early", "mostly luck", "paid off", "cost"]


@dataclass(frozen=True)
class Record:
    """Whether going against the advice has paid off for a user's team, over the rounds reviewed (R4.2,
    R4.3)."""

    rounds: int
    overrides: int
    """Rounds where the user went against the advice."""
    expected_cost: float
    """What those overrides were expected to give up, in all."""
    real_gain: float
    """What they really gained, in all, over the rounds where it's known."""
    counted: int
    """Overrides whose real gain is known."""
    margin: float | None
    """About two standard errors of that total: within it, it's still mostly luck."""
    verdict: Verdict


def record(reviews: Iterable[LoggedReview], *, user: str, team: str) -> Record:
    """The record for one user's team: the latest review of each round, whatever order they come in."""
    latest: dict[int, LoggedReview] = {}
    for review in reviews:
        if review.user != user or name_key(review.team) != name_key(team):
            continue
        seen = latest.get(review.round)
        if seen is None or (review.logged_at, review.model_dump_json()) > (
            seen.logged_at,
            seen.model_dump_json(),
        ):
            latest[review.round] = review
    overrides = [review for review in latest.values() if review.choices]
    gains = sorted(review.total_gain for review in overrides if review.total_gain is not None)
    total = math.fsum(gains)
    margin = 2 * statistics.stdev(gains) * math.sqrt(len(gains)) if len(gains) >= FEWEST_TO_TELL else None
    verdict: Verdict = "too early"
    if margin is not None:
        verdict = "paid off" if total > margin else "cost" if total < -margin else "mostly luck"
    return Record(
        rounds=len(latest),
        overrides=len(overrides),
        expected_cost=math.fsum(sorted(review.total_cost for review in overrides)),
        real_gain=total,
        counted=len(gains),
        margin=margin,
        verdict=verdict,
    )


def goals_against(
    before: Mapping[int, PlayerSeasonRow] | None, after: Mapping[int, PlayerSeasonRow]
) -> dict[str, int | None]:
    """Each club's goals against between two reads, from its keepers' rows; None where one of its keepers
    isn't in both reads with his goals conceded."""
    by_club: dict[str, int | None] = {}
    if before is None:
        return by_club
    for row in after.values():
        if row.role != "P":
            continue
        then = before.get(row.player_id)
        if then is None or row.goals_conceded is None or then.goals_conceded is None:
            by_club[row.club] = None
        elif by_club.get(row.club, 0) is not None:
            by_club[row.club] = (by_club.get(row.club) or 0) + row.goals_conceded - then.goals_conceded
    return by_club
