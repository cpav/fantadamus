"""The forward model: what a forward is worth if he starts and if he comes on, his key, and how two compare
(design C8; method §A3, §A4; R9, R10).

One function per formula, each with its inputs passed in. Bonuses and maluses are the league's signed
values, so a yellow card at -0.5 lowers the score (R9.1).
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict

from fantadamus.engine.constants import (
    ASSIST_SHARE_PRIOR,
    CAMEO_GOAL_VALUE,
    CAMEO_RATED,
    CAMEO_RATING,
    CLEAR,
    COIN_FLIP,
    FIXTURE_EFFECT,
    GOAL_SHARE_PRIOR,
    GOAL_SHARE_PRIOR_UNKNOWN,
    MINUTES_CAMEO,
    MINUTES_START,
    PENALTY_CONVERSION,
    PENALTY_RATE,
    SHARE_WEIGHT,
    VOTE_BASELINE,
    VOTE_WEIGHT,
    YELLOW_PRIOR,
    YELLOW_WEIGHT,
)

Label = Literal["coin flip", "lean", "clear"]
_BISECTIONS = 40


class Scoring(BaseModel):
    """The league's signed values this model uses (R12.5)."""

    model_config = ConfigDict(frozen=True)

    goal: float
    penalty_scored: float
    assist: float
    yellow: float


class ForwardInputs(BaseModel):
    """Everything the model needs about one forward for one match."""

    model_config = ConfigDict(frozen=True)

    name: str
    mantra_role: str | None
    appearances: int
    rated_appearances: int
    average_rating: float | None
    goals: int
    assists: int
    yellow_cards: int
    club_goals_per_match: float
    penalty_taker: bool
    """His club's first penalty taker."""
    team_xg: float
    p_win: float
    p_loss: float
    p_start: float
    p_cameo: float


class Option(BaseModel):
    """A player as the ordering rule sees him."""

    model_config = ConfigDict(frozen=True)

    name: str
    p_start: float
    p_cameo: float
    e_start: float
    e_cameo: float

    def figures(self) -> dict[str, float]:
        return {
            "p_start": self.p_start,
            "e_start": self.e_start,
            "p_cameo": self.p_cameo,
            "e_cameo": self.e_cameo,
        }


class ForwardValue(Option):
    """An option with every intermediate value, for the answer's breakdown (R9.8)."""

    expected_vote: float
    goal_share: float
    assist_share: float
    e_goals: float
    e_assists: float
    p_scores: float
    p_yellow: float
    cameo_e_goals: float
    p_scores_cameo: float
    key: float
    no_cover: float


class Verdict(BaseModel):
    first: str
    """Start him."""
    second: str
    """Put him first on the bench."""
    margin: float
    """The difference in keys, in points."""
    label: Label
    no_cover_first: str
    """Who to start if the bench can't cover (R10.6)."""
    no_cover_differs: bool


class Comparison(BaseModel):
    values: list[ForwardValue]
    """Both players, in the order asked."""
    verdict: Verdict
    flip_p_start: float | None
    """The leader's p_start below which the order changes; None if only not playing would change it."""
    flip_team_xg: float | None
    """His team xG below which the order changes; None if no team xG would."""


def expected_vote(rated: int, average: float | None, *, p_win: float, p_loss: float) -> float:
    """6.0 shrunk toward his average by n / (n + 10), plus 0.3 x (P(win) - P(loss)) (R9.2)."""
    form = 0.0 if average is None else rated / (rated + VOTE_WEIGHT) * (average - VOTE_BASELINE)
    return VOTE_BASELINE + form + FIXTURE_EFFECT * (p_win - p_loss)


def share(prior: float, *, events: int, team_goals: float) -> float:
    """His share of the team's goals (or assists), shrunk toward the prior (R9.4)."""
    return (prior * SHARE_WEIGHT + events) / (SHARE_WEIGHT + team_goals)


def expected_goals(team_xg: float, share: float, *, minutes: float) -> float:
    """Open-play goals (or assists) expected in his minutes (R9.3)."""
    return team_xg * share * minutes


def penalty_goals(*, minutes: float, taker: bool) -> float:
    """Penalty goals expected for his club's first taker (R9.5)."""
    return PENALTY_RATE * PENALTY_CONVERSION * minutes if taker else 0.0


def p_scores(goals: float) -> float:
    return 1 - math.exp(-goals)


def p_yellow(cards: int, *, appearances: int) -> float:
    """Yellow cards per appearance, shrunk toward 0.15 with the weight of 10 appearances (R9.6)."""
    return (YELLOW_PRIOR * YELLOW_WEIGHT + cards) / (YELLOW_WEIGHT + appearances)


def e_cameo(goals: float) -> float:
    """A cameo's value: 9.8 with a goal, else a 60 % chance of a 5.75 rating (R9.7)."""
    scored = p_scores(goals)
    return scored * CAMEO_GOAL_VALUE + (1 - scored) * CAMEO_RATED * CAMEO_RATING


def key(p_start: float, e_start: float, p_cameo: float, e_cameo: float) -> float:
    """Method §A3: the value of his rating, whichever way he gets it; 0 if he can't get one."""
    chance = p_start + p_cameo
    return (p_start * e_start + p_cameo * e_cameo) / chance if chance else 0.0


def no_cover(p_start: float, e_start: float, p_cameo: float, e_cameo: float) -> float:
    """His expected points when no bench player covers a missing rating (R10.6)."""
    return p_start * e_start + p_cameo * e_cameo


def label(margin: float) -> Label:
    if margin < COIN_FLIP:
        return "coin flip"
    return "lean" if margin <= CLEAR else "clear"


def value(player: ForwardInputs, scoring: Scoring) -> ForwardValue:
    """Every step of the forward model for one player (R9.1 to R9.7)."""
    team_goals = player.club_goals_per_match * player.appearances
    prior = GOAL_SHARE_PRIOR.get(player.mantra_role or "", GOAL_SHARE_PRIOR_UNKNOWN)
    goal_share = share(prior, events=player.goals, team_goals=team_goals)
    assist_share = share(ASSIST_SHARE_PRIOR, events=player.assists, team_goals=team_goals)
    open_goals = expected_goals(player.team_xg, goal_share, minutes=MINUTES_START)
    penalties = penalty_goals(minutes=MINUTES_START, taker=player.penalty_taker)
    assists = expected_goals(player.team_xg, assist_share, minutes=MINUTES_START)
    yellow = p_yellow(player.yellow_cards, appearances=player.appearances)
    vote = expected_vote(
        player.rated_appearances, player.average_rating, p_win=player.p_win, p_loss=player.p_loss
    )
    start = (
        vote
        + scoring.goal * open_goals
        + scoring.penalty_scored * penalties
        + scoring.assist * assists
        + scoring.yellow * yellow
    )
    cameo_goals = expected_goals(player.team_xg, goal_share, minutes=MINUTES_CAMEO) + penalty_goals(
        minutes=MINUTES_CAMEO, taker=player.penalty_taker
    )
    cameo = e_cameo(cameo_goals)
    return ForwardValue(
        name=player.name,
        p_start=player.p_start,
        p_cameo=player.p_cameo,
        e_start=start,
        e_cameo=cameo,
        expected_vote=vote,
        goal_share=goal_share,
        assist_share=assist_share,
        e_goals=open_goals + penalties,
        e_assists=assists,
        p_scores=p_scores(open_goals + penalties),
        p_yellow=yellow,
        cameo_e_goals=cameo_goals,
        p_scores_cameo=p_scores(cameo_goals),
        key=key(player.p_start, start, player.p_cameo, cameo),
        no_cover=no_cover(player.p_start, start, player.p_cameo, cameo),
    )


def _rank(option: Option) -> tuple[float, float, str]:
    return key(**option.figures()), no_cover(**option.figures()), option.name


def verdict(a: Option, b: Option) -> Verdict:
    """Start the higher key, put the other first on the bench (R10.1, R10.2, R10.6)."""
    first, second = sorted((a, b), key=_rank, reverse=True)
    covered = max((a, b), key=lambda option: (no_cover(**option.figures()), option.name))
    return Verdict(
        first=first.name,
        second=second.name,
        margin=_rank(first)[0] - _rank(second)[0],
        label=label(_rank(first)[0] - _rank(second)[0]),
        no_cover_first=covered.name,
        no_cover_differs=covered.name != first.name,
    )


def _flip(leader: ForwardInputs, trailer: float, field: str, low: float, scoring: Scoring) -> float | None:
    """The value of the leader's `field`, between `low` and now, at which his key falls to `trailer`."""

    def ahead(at: float) -> bool:
        return value(leader.model_copy(update={field: at}), scoring).key >= trailer

    high = float(getattr(leader, field))
    if ahead(low):
        return None
    for _ in range(_BISECTIONS):
        middle = (low + high) / 2
        low, high = (low, middle) if ahead(middle) else (middle, high)
    return high


def compare(a: ForwardInputs, b: ForwardInputs, scoring: Scoring) -> Comparison:
    """The verdict with both breakdowns and what would flip it (R9.8, R10.1, R10.2, R10.4, R10.6)."""
    values = [value(a, scoring), value(b, scoring)]
    result = verdict(*values)
    leader, trailer = (a, values[1]) if result.first == values[0].name else (b, values[0])
    return Comparison(
        values=values,
        verdict=result,
        flip_p_start=_flip(leader, trailer.key, "p_start", 0.01, scoring),
        flip_team_xg=_flip(leader, trailer.key, "team_xg", 0.0, scoring),
    )
