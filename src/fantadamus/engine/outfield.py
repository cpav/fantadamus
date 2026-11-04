"""The outfield model: what a defender, midfielder or forward is worth if he starts and if he comes on, his
key, and how two of one role compare (mvp-x-or-y design C8; method §A3, §A4; R9, R10; mvp-roles C6, R2).

One function per formula, each with its inputs passed in. The forward model carries over to every outfield
player: only the priors change, by his first Mantra role, and a defender's shares shrink with more weight. A
forward listed first as `Pc`, `A`, `W` or with no Mantra role is valued exactly as before (mvp-roles R2.6).
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from fantadamus.contracts.types import Role
from fantadamus.engine.constants import (
    CAMEO_FLAT,
    CAMEO_GOAL_VALUE,
    CAMEO_RATED,
    CAMEO_RATING,
    DEFENDER_SHARE_WEIGHT,
    FIXTURE_EFFECT,
    MINUTES_CAMEO,
    PENALTY_CONVERSION,
    PENALTY_RATE,
    ROLE_PRIORS,
    SHARE_WEIGHT,
    USUAL_MANTRA_ROLE,
    VOTE_BASELINE,
    VOTE_WEIGHT,
    YELLOW_PRIOR,
    YELLOW_WEIGHT,
    RolePriors,
)
from fantadamus.engine.rank import Option, Scoring, Verdict, flip, key, no_cover, verdict


class OutfieldInputs(BaseModel):
    """Everything the model needs about one outfield player for one match."""

    model_config = ConfigDict(frozen=True)

    name: str
    role: Role
    """His Classic role: a defender's shares shrink with more weight (mvp-roles R2.3)."""
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


class OutfieldValue(Option):
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


class Comparison(BaseModel):
    values: list[OutfieldValue]
    """Both players, in the order asked."""
    verdict: Verdict
    flip_p_start: float | None
    """The leader's p_start below which the order changes; None if only not playing would change it."""
    flip_team_xg: float | None
    """His team xG below which the order changes; None if no team xG would."""


def priors(role: Role, mantra_role: str | None) -> RolePriors:
    """His first Mantra role's priors, or his Classic role's usual one's (mvp-roles R2.1, R2.2)."""
    return ROLE_PRIORS.get(mantra_role or "") or ROLE_PRIORS[USUAL_MANTRA_ROLE.get(role, "A")]


def expected_vote(rated: int, average: float | None, *, p_win: float, p_loss: float) -> float:
    """6.0 shrunk toward his average by n / (n + 10), plus 0.3 x (P(win) - P(loss)) (R9.2)."""
    form = 0.0 if average is None else rated / (rated + VOTE_WEIGHT) * (average - VOTE_BASELINE)
    return VOTE_BASELINE + form + FIXTURE_EFFECT * (p_win - p_loss)


def share(prior: float, *, events: int, team_goals: float, weight: float = SHARE_WEIGHT) -> float:
    """His share of the team's goals (or assists), shrunk toward the prior (R9.4; mvp-roles R2.3)."""
    return (prior * weight + events) / (weight + team_goals)


def expected_goals(team_xg: float, share: float, *, minutes: float) -> float:
    """Open-play goals (or assists) expected in his minutes (R9.3)."""
    return team_xg * share * minutes


def penalty_goals(*, minutes: float, taker: bool) -> float:
    """Penalty goals expected for his club's first taker, in his minutes (R9.5; mvp-roles R2.4)."""
    return PENALTY_RATE * PENALTY_CONVERSION * minutes if taker else 0.0


def p_scores(goals: float) -> float:
    return 1 - math.exp(-goals)


def p_yellow(cards: int, *, appearances: int) -> float:
    """Yellow cards per appearance, shrunk toward 0.15 with the weight of 10 appearances (R9.6)."""
    return (YELLOW_PRIOR * YELLOW_WEIGHT + cards) / (YELLOW_WEIGHT + appearances)


def e_cameo(goals: float) -> float:
    """An attacker's cameo: 9.8 with a goal, else a 60 % chance of a 5.75 rating (R9.7)."""
    scored = p_scores(goals)
    return scored * CAMEO_GOAL_VALUE + (1 - scored) * CAMEO_RATED * CAMEO_RATING


def value(player: OutfieldInputs, scoring: Scoring) -> OutfieldValue:
    """Every step of the model for one player (R9.1 to R9.7; mvp-roles R2.1 to R2.5)."""
    prior = priors(player.role, player.mantra_role)
    weight = DEFENDER_SHARE_WEIGHT if player.role == "D" else SHARE_WEIGHT
    team_goals = player.club_goals_per_match * player.appearances
    goal_share = share(prior.goal, events=player.goals, team_goals=team_goals, weight=weight)
    assist_share = share(prior.assist, events=player.assists, team_goals=team_goals, weight=weight)
    open_goals = expected_goals(player.team_xg, goal_share, minutes=prior.minutes)
    penalties = penalty_goals(minutes=prior.minutes, taker=player.penalty_taker)
    assists = expected_goals(player.team_xg, assist_share, minutes=prior.minutes)
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
    cameo = e_cameo(cameo_goals) if prior.priced_cameo else CAMEO_FLAT
    return OutfieldValue(
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


def compare(a: OutfieldInputs, b: OutfieldInputs, scoring: Scoring) -> Comparison:
    """The verdict with both breakdowns and what would flip it (R9.8, R10.1, R10.2, R10.4, R10.6)."""
    values = [value(a, scoring), value(b, scoring)]
    result = verdict(*values)
    leader, trailer = (a, values[1]) if result.first == values[0].name else (b, values[0])

    def worth(player: OutfieldInputs) -> OutfieldValue:
        return value(player, scoring)

    return Comparison(
        values=values,
        verdict=result,
        flip_p_start=flip(leader, worth, "p_start", 0.01, trailer.key),
        flip_team_xg=flip(leader, worth, "team_xg", 0.0, trailer.key),
    )
