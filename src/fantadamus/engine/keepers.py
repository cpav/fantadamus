"""The keeper model: a keeper judged on his own work and his match, not on his defence's season (mvp-roles
design C7; method §A6; R3.1 to R3.6, R4.1).

His skill is his average rating with his goals conceded added back, shrunk toward an average keeper's; his
expected vote takes back what the opponent is expected to score. The clean-sheet chance is the opponent's
chance of scoring none, from the same fit as the match's odds: the Dixon-Coles correction leaves it at
Poisson's e^(-xG). A keeper gets no cameo, so his key is his value if he starts.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict

from fantadamus.engine.constants import KEEPER_BETA, KEEPER_SKILL_WEIGHT, VOTE_BASELINE, XG_RANGE
from fantadamus.engine.points import PENALTIES_SAVED, event_points, rare_points
from fantadamus.engine.rank import Option, Scoring, Verdict, covering, flip, key, no_cover, verdict


class KeeperInputs(BaseModel):
    """Everything the model needs about one keeper for one match."""

    model_config = ConfigDict(frozen=True)

    name: str
    club: str
    rated_appearances: int
    average_rating: float | None
    goals_conceded: int | None
    """None when his page didn't say: an average defence is assumed."""
    league_goals_per_match: float
    """Each team's goals per match across the league, from the table."""
    opponent_xg: float
    p_start: float


class KeeperValue(Option):
    """An option with every intermediate value, for the answer's breakdown (R3.5)."""

    kind: Literal["keeper"] = "keeper"
    skill: float
    expected_vote: float
    p_clean_sheet: float
    expected_conceded: float
    key: float
    no_cover: float


class KeeperComparison(BaseModel):
    values: list[KeeperValue]
    """Both keepers, in the order asked."""
    verdict: Verdict
    flip_opponent_xg: float | None
    """His opponent's xG above which the order changes; None if none up to the top of the range would, or
    if they're of one club. His p_start can't flip it: with no cameo, his key doesn't depend on it."""


def skill(keeper: KeeperInputs) -> float:
    """Average rating + 0.35 x goals conceded per rated appearance, shrunk with n / (n + 9) toward an average
    keeper behind an average defence (R3.3)."""
    prior = VOTE_BASELINE + KEEPER_BETA * keeper.league_goals_per_match
    rated = keeper.rated_appearances
    if keeper.average_rating is None or not rated:
        return prior
    per_match = (
        keeper.goals_conceded / rated if keeper.goals_conceded is not None else keeper.league_goals_per_match
    )
    own = keeper.average_rating + KEEPER_BETA * per_match
    return prior + rated / (rated + KEEPER_SKILL_WEIGHT) * (own - prior)


def value(keeper: KeeperInputs, scoring: Scoring) -> KeeperValue:
    """Every step of the model for one keeper (R3.1 to R3.4)."""
    shrunk = skill(keeper)
    conceded = keeper.opponent_xg
    vote = shrunk - KEEPER_BETA * conceded
    clean_sheet = math.exp(-conceded)
    start = (
        vote
        + event_points(scoring, clean_sheets=clean_sheet, conceded=conceded)
        + rare_points(scoring, "P", penalties_saved=PENALTIES_SAVED)
    )
    return KeeperValue(
        name=keeper.name,
        p_start=keeper.p_start,
        p_cameo=0.0,
        e_start=start,
        e_cameo=0.0,
        skill=shrunk,
        expected_vote=vote,
        p_clean_sheet=clean_sheet,
        expected_conceded=conceded,
        key=key(keeper.p_start, start, 0.0, 0.0),
        no_cover=no_cover(keeper.p_start, start, 0.0, 0.0),
    )


def compare(a: KeeperInputs, b: KeeperInputs, scoring: Scoring) -> KeeperComparison:
    """The verdict with both breakdowns and what would flip it (R4.1). Two keepers of one club cover each
    other exactly: the likelier starter goes first, and no opponent can change that (R3.6)."""
    values = [value(a, scoring), value(b, scoring)]
    if a.club == b.club:
        return KeeperComparison(values=values, verdict=covering(*values), flip_opponent_xg=None)
    result = verdict(*values)
    leader, trailer = (a, values[1]) if result.first == values[0].name else (b, values[0])

    def worth(keeper: KeeperInputs) -> KeeperValue:
        return value(keeper, scoring)

    return KeeperComparison(
        values=values,
        verdict=result,
        flip_opponent_xg=flip(leader, worth, "opponent_xg", XG_RANGE[1], trailer.key),
    )
