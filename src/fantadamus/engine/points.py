"""What a player's events are worth: the one place a league's points meet his counts (mvp-rules C2, C3).

The player models pass expected counts and the simulation passes drawn ones, for outfield players and keepers
alike. Events too rare to change the spread are a fixed term in both, so that a player's simulated mean stays
his model's.
"""

from __future__ import annotations

from fantadamus.contracts.types import Role
from fantadamus.engine.constants import (
    OWN_GOAL_RATE,
    PENALTY_CONVERSION,
    PENALTY_RATE,
    PENALTY_SAVED_SHARE,
    RED_RATE,
)
from fantadamus.engine.rank import Scoring

PENALTIES_SAVED = PENALTY_RATE * (1 - PENALTY_CONVERSION) * PENALTY_SAVED_SHARE
"""A keeper's expected saves in a start: the chance his opponents get a penalty, miss it, and he saved it."""


def event_points(
    scoring: Scoring,
    *,
    goals: float = 0.0,
    penalties: float = 0.0,
    assists: float = 0.0,
    yellows: float = 0.0,
    clean_sheets: float = 0.0,
    conceded: float = 0.0,
) -> float:
    return (
        scoring.goal * goals
        + scoring.penalty_scored * penalties
        + scoring.assist * assists
        + scoring.yellow * yellows
        + scoring.clean_sheet * clean_sheets
        + scoring.goal_conceded * conceded
    )


def rare_points(
    scoring: Scoring, role: Role, *, penalties_missed: float = 0.0, penalties_saved: float = 0.0
) -> float:
    """What the rare events are worth in a start, on average (R1.3)."""
    return (
        scoring.penalty_missed * penalties_missed
        + scoring.penalty_saved * penalties_saved
        + scoring.red * RED_RATE[role]
        + scoring.own_goal * OWN_GOAL_RATE[role]
    )
