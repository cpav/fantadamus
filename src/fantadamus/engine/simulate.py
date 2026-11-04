"""Simulating a round under the league's real rules (mvp-lineup design C7; R4; method §A2, §A7).

Pure, seeded and standard library only. Each round is drawn once for the whole squad and scored for every
arrangement, so comparisons between formations share their luck. A match's goals are drawn once, which is what
links a striker's goal to the keeper who concedes it. The simulation adds spread, not value: a player's mean
over many rounds is what his model says (P4)."""

from __future__ import annotations

import bisect
import math
import random
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import LineupRules, formation_lines
from fantadamus.engine.constants import (
    CAMEO_FLAT,
    CAMEO_GOAL_VALUE,
    CAMEO_RATED,
    CAMEO_RATING,
    GOAL_VOTE_LIFT,
    KEEPER_BETA,
    KEEPER_VOTE_NOISE,
    MINUTES_CAMEO,
    SIMULATION_SEED,
    SIMULATIONS,
    THRESHOLDS_SHOWN,
    VOTE_NOISE,
)
from fantadamus.engine.keepers import KeeperInputs, KeeperValue
from fantadamus.engine.lineup import Arrangement
from fantadamus.engine.outfield import OutfieldInputs, OutfieldValue, penalty_goals, priors
from fantadamus.engine.rank import Scoring

Side = tuple[int, int]
"""A match's place in the list of matches, and which team: 0 at home, 1 away."""
Move = tuple[int, int]
"""The player without a rating, and who replaces him."""
Scores = Mapping[int, float | None]
"""By player ID; None without a rating."""
_NOT_PLAYING, _STARTS, _COMES_ON = 0, 1, 2
_LINE = {"D": 0, "C": 1, "A": 2}


@dataclass(frozen=True, slots=True)
class Outfielder:
    """What a simulated round needs about an outfield player."""

    player_id: int
    side: Side | None
    p_start: float
    p_cameo: float
    lowered_vote: float
    """His expected vote less the lift his expected goals will add back, so that it doesn't change."""
    per_goal: float
    """His chance of scoring a given goal of his team if he starts."""
    per_assist: float
    cameo_per_goal: float
    penalties: float
    """Penalty goals expected if he starts."""
    cameo_penalties: float
    p_yellow: float
    priced_cameo: bool
    scoring: Scoring


@dataclass(frozen=True, slots=True)
class Keeper:
    """What a simulated round needs about a keeper."""

    player_id: int
    club: str
    side: Side | None
    p_start: float
    skill: float
    scoring: Scoring


SimPlayer = Outfielder | Keeper


def outfield_player(
    player_id: int, inputs: OutfieldInputs, value: OutfieldValue, scoring: Scoring, side: Side | None
) -> Outfielder:
    prior = priors(inputs.role, inputs.mantra_role)
    return Outfielder(
        player_id=player_id,
        side=side,
        p_start=value.p_start,
        p_cameo=value.p_cameo,
        lowered_vote=value.expected_vote - GOAL_VOTE_LIFT * value.e_goals,
        per_goal=value.goal_share * prior.minutes,
        per_assist=value.assist_share * prior.minutes,
        cameo_per_goal=value.goal_share * MINUTES_CAMEO if prior.priced_cameo else 0.0,
        penalties=penalty_goals(minutes=prior.minutes, taker=inputs.penalty_taker),
        cameo_penalties=penalty_goals(minutes=MINUTES_CAMEO, taker=inputs.penalty_taker),
        p_yellow=value.p_yellow,
        priced_cameo=prior.priced_cameo,
        scoring=scoring,
    )


def keeper_player(
    player_id: int, inputs: KeeperInputs, value: KeeperValue, scoring: Scoring, side: Side | None
) -> Keeper:
    return Keeper(
        player_id=player_id,
        club=inputs.club,
        side=side,
        p_start=value.p_start,
        skill=value.skill,
        scoring=scoring,
    )


def outfield_points(
    player: Outfielder, noise: float, open_goals: int, penalties: int, assists: int, yellow: bool
) -> float:
    """A starter's score: his vote plus noise, lifted by each goal, and his bonuses."""
    scoring = player.scoring
    vote = player.lowered_vote + noise + GOAL_VOTE_LIFT * (open_goals + penalties)
    bonuses = scoring.goal * open_goals + scoring.penalty_scored * penalties + scoring.assist * assists
    return vote + bonuses + (scoring.yellow if yellow else 0.0)


def keeper_points(keeper: Keeper, noise: float, conceded: int) -> float:
    """A starter's score: his skill less what each goal conceded costs his vote, plus noise and bonuses."""
    scoring = keeper.scoring
    vote = keeper.skill - KEEPER_BETA * conceded + noise
    return vote + (scoring.clean_sheet if not conceded else 0.0) + scoring.goal_conceded * conceded


def _poisson(limit: float, draw: Callable[[], float]) -> int:
    """A Poisson count, given e^(-rate): Knuth's method, quick at the small rates of a football match."""
    count, product = 0, draw()
    while product > limit:
        count += 1
        product *= draw()
    return count


def _cameo_points(player: Outfielder, open_goals: int, draw: Callable[[], float]) -> float | None:
    """As the model prices it: a flat rating, or an attacker's goal, or else a rating some of the time."""
    if not player.priced_cameo:
        return CAMEO_FLAT
    if open_goals or _poisson(math.exp(-player.cameo_penalties), draw):
        return CAMEO_GOAL_VALUE
    return CAMEO_RATING if draw() < CAMEO_RATED else None


def draw_rounds(
    players: Sequence[SimPlayer], matches: Sequence[tuple[float, float]], *, rounds: int, seed: int
) -> Iterator[tuple[dict[int, float | None], list[tuple[int, int]]]]:
    """Each round's scores by player ID, and each match's goals."""
    # reason: a seeded generator makes a lineup repeatable (R4.6); nothing here is a secret
    generator = random.Random(seed)  # noqa: S311
    draw, gauss = generator.random, generator.gauss
    limits = [(math.exp(-home), math.exp(-away)) for home, away in matches]
    outfield = [player for player in players if isinstance(player, Outfielder)]
    clubs: dict[str, list[Keeper]] = {}
    for player in players:
        if isinstance(player, Keeper):
            clubs.setdefault(player.club, []).append(player)
    keeper_units = [(unit, max(sum(keeper.p_start for keeper in unit), 1.0)) for unit in clubs.values()]
    sides: dict[Side, list[tuple[int, Outfielder]]] = {}
    for index, player in enumerate(outfield):
        if player.side is not None:
            sides.setdefault(player.side, []).append((index, player))
    state = [_NOT_PLAYING] * len(outfield)
    open_goals = [0] * len(outfield)
    assists = [0] * len(outfield)
    penalty_limits = [math.exp(-player.penalties) for player in outfield]
    for _ in range(rounds):
        goals = [(_poisson(home, draw), _poisson(away, draw)) for home, away in limits]
        for index, player in enumerate(outfield):
            chance = draw()
            state[index] = (
                _STARTS
                if chance < player.p_start
                else _COMES_ON
                if chance < player.p_start + player.p_cameo
                else _NOT_PLAYING
            )
            open_goals[index] = assists[index] = 0
        for (match, team), members in sides.items():
            for _ in range(goals[match][team]):
                chance, reach = draw(), 0.0
                for index, player in members:
                    if state[index]:
                        reach += player.per_goal if state[index] == _STARTS else player.cameo_per_goal
                        if chance < reach:
                            open_goals[index] += 1
                            break
                chance, reach = draw(), 0.0
                for index, player in members:
                    if state[index] == _STARTS:
                        reach += player.per_assist
                        if chance < reach:
                            assists[index] += 1
                            break
        scores: dict[int, float | None] = {}
        for index, player in enumerate(outfield):
            if state[index] == _STARTS:
                penalties = _poisson(penalty_limits[index], draw) if player.penalties else 0
                scores[player.player_id] = outfield_points(
                    player,
                    gauss(0.0, VOTE_NOISE),
                    open_goals[index],
                    penalties,
                    assists[index],
                    draw() < player.p_yellow,
                )
            elif state[index] == _COMES_ON:
                scores[player.player_id] = _cameo_points(player, open_goals[index], draw)
            else:
                scores[player.player_id] = None
        for unit, total in keeper_units:
            chance, reach, starter = draw() * total, 0.0, None
            for keeper in unit:
                reach += keeper.p_start
                if chance < reach:
                    starter = keeper
                    break
            for keeper in unit:
                if keeper is starter and keeper.side is not None:
                    conceded = goals[keeper.side[0]][1 - keeper.side[1]]
                    scores[keeper.player_id] = keeper_points(keeper, gauss(0.0, KEEPER_VOTE_NOISE), conceded)
                else:
                    scores[keeper.player_id] = None
        yield scores, goals


@dataclass(frozen=True)
class Plan:
    """An arrangement and the league's rules, ready to score round after round."""

    starters: tuple[int, ...]
    role: Mapping[int, Role]
    options: Mapping[Role, tuple[int, ...]]
    """Who may come on for each role, in the order they're asked."""
    lines: tuple[int, int, int]
    allowed: frozenset[tuple[int, int, int]]
    cap: int
    empty_place: float
    """What a place nobody fills scores."""


def plan(arrangement: Arrangement, rules: LineupRules) -> Plan:
    role = {player.player_id: player.role for player in (*arrangement.starters, *arrangement.bench)}
    bench = [player.player_id for player in arrangement.bench]
    keepers = tuple(player for player in bench if role[player] == "P")
    outfield = [player for player in bench if role[player] != "P"]

    def options(of: Role) -> tuple[int, ...]:
        own = tuple(player for player in outfield if role[player] == of)
        if rules.substitution_mode == "bench_order":
            return tuple(outfield)
        if rules.substitution_mode == "role_first":
            return (*own, *(player for player in outfield if role[player] != of))
        return own

    return Plan(
        starters=tuple(player.player_id for player in arrangement.starters),
        role=role,
        options={"P": keepers, "D": options("D"), "C": options("C"), "A": options("A")},
        lines=formation_lines(arrangement.formation),
        allowed=frozenset(formation_lines(allowed) for allowed in rules.formations or ()),
        cap=rules.substitutions or 0,
        empty_place=rules.no_rating_vote or 0.0,
    )


def field(scores: Scores, lineup: Plan) -> tuple[float, list[Move]]:
    """The arrangement's score in one round, and the substitutions made: keepers, then defenders, midfielders
    and forwards, each replaced by the first who may come on and has a rating, until the cap (R4.1)."""
    total = 0.0
    missing = []
    for player in lineup.starters:
        score = scores[player]
        if score is None:
            missing.append(player)
        else:
            total += score
    moves: list[Move] = []
    if not missing:
        return total, moves
    used: set[int] = set()
    lines = list(lineup.lines)
    for out in missing:
        replaced = False
        if len(moves) < lineup.cap:
            role = lineup.role[out]
            for player in lineup.options[role]:
                score = scores[player]
                if score is None or player in used:
                    continue
                other = lineup.role[player]
                if other != role:
                    after = list(lines)
                    after[_LINE[role]] -= 1
                    after[_LINE[other]] += 1
                    if tuple(after) not in lineup.allowed:
                        continue
                    lines = after
                used.add(player)
                moves.append((out, player))
                total += score
                replaced = True
                break
        if not replaced:
            total += lineup.empty_place
    return total, moves


def fantasy_goals(score: float, thresholds: Sequence[float] | None) -> int:
    """How many fantasy goals `score` converts to. Past the last threshold, its last step repeats."""
    if not thresholds:
        return 0
    reached = bisect.bisect_right(thresholds, score)
    if reached < len(thresholds):
        return reached
    step = thresholds[-1] - thresholds[-2]
    return reached + math.floor((score - thresholds[-1]) / step)


def _shown(thresholds: Sequence[float] | None) -> list[float]:
    """The thresholds worth a chance in the answer: the league's, and past them, its last step repeated."""
    if not thresholds:
        return []
    shown = list(thresholds)
    step = thresholds[-1] - thresholds[-2]
    while len(shown) < THRESHOLDS_SHOWN:
        shown.append(shown[-1] + step)
    return shown


class Reached(BaseModel):
    points: float
    chance: float


class Simulated(BaseModel):
    """What one arrangement does over the rounds (R4.5)."""

    formation: str
    mean: float
    low: float
    high: float
    """Eight rounds out of ten fall from `low` to `high`; `high` is the ceiling."""
    fantasy_goals: float
    thresholds: list[Reached]


def summarize(formation: str, totals: Sequence[float], thresholds: Sequence[float] | None) -> Simulated:
    ordered = sorted(totals)
    count = len(ordered)
    tenth = count // 10
    return Simulated(
        formation=formation,
        mean=math.fsum(ordered) / count,
        low=ordered[tenth],
        high=ordered[count - 1 - tenth],
        fantasy_goals=sum(fantasy_goals(total, thresholds) for total in ordered) / count,
        thresholds=[
            Reached(points=points, chance=(count - bisect.bisect_left(ordered, points)) / count)
            for points in _shown(thresholds)
        ],
    )


def simulate(
    players: Sequence[SimPlayer],
    matches: Sequence[tuple[float, float]],
    arrangements: Sequence[Arrangement],
    rules: LineupRules,
    *,
    rounds: int = SIMULATIONS,
    seed: int = SIMULATION_SEED,
) -> list[Simulated]:
    """Each arrangement over the same simulated rounds."""
    plans = [plan(arrangement, rules) for arrangement in arrangements]
    totals: list[list[float]] = [[] for _ in plans]
    for scores, _ in draw_rounds(players, matches, rounds=rounds, seed=seed):
        for lineup, kept in zip(plans, totals, strict=True):
            kept.append(field(scores, lineup)[0])
    return [
        summarize(arrangement.formation, kept, rules.thresholds)
        for arrangement, kept in zip(arrangements, totals, strict=True)
    ]
