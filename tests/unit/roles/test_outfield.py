"""mvp-roles task 4.2: every outfield player on the forward model, with his first Mantra role's priors (design
C6; R2.1 to R2.5)."""

from __future__ import annotations

import pytest

from fantadamus.contracts.types import Role
from fantadamus.engine import outfield
from fantadamus.engine.rank import Scoring
from tests.roles_data import outfield as player

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
TABLE: list[
    tuple[Role, str | None, float, float, float, bool]
] = [  # R2.1: goal share, assist share, minutes share if he starts, priced cameo
    ("A", "Pc", 0.30, 0.11, 0.85, True),
    ("A", "A", 0.20, 0.11, 0.85, True),
    ("A", "W", 0.15, 0.11, 0.85, True),
    ("C", "T", 0.15, 0.11, 0.80, True),
    ("C", "C", 0.06, 0.08, 0.85, False),
    ("C", "M", 0.06, 0.08, 0.85, False),
    ("C", "E", 0.04, 0.08, 0.85, False),
    ("D", "Dd", 0.03, 0.06, 0.95, False),
    ("D", "Ds", 0.03, 0.06, 0.95, False),
    ("D", "Dc", 0.05, 0.02, 0.95, False),
    ("D", "B", 0.05, 0.02, 0.95, False),
    ("A", None, 0.20, 0.11, 0.85, True),  # R2.2: a forward's usual role, A
    ("C", None, 0.06, 0.08, 0.85, False),  # a midfielder's, C
    ("D", None, 0.05, 0.02, 0.95, False),  # a defender's, Dc
]


@pytest.mark.parametrize(("role", "mantra", "goal", "assist", "minutes", "priced"), TABLE)
def test_priors_by_role(
    role: Role, mantra: str | None, goal: float, assist: float, minutes: float, priced: bool
) -> None:
    value = outfield.value(player(role, mantra), CLASSIC)
    assert value.goal_share == pytest.approx(goal)
    assert value.assist_share == pytest.approx(assist)
    assert value.e_goals == pytest.approx(1.4 * goal * minutes)
    taker = outfield.value(player(role, mantra, penalty_taker=True), CLASSIC)
    assert taker.e_goals - value.e_goals == pytest.approx(0.15 * 0.78 * minutes)  # R2.4: at his own minutes
    rated, worth = outfield.cameo_rating(value.cameo_e_goals) if priced else (1.0, 5.5)
    assert value.e_cameo == pytest.approx(worth)
    assert value.p_cameo == pytest.approx(player(role, mantra).p_cameo * rated)
    weight = 25 if role == "D" else 15  # R2.3: ten team goals in his games
    played = outfield.value(
        player(
            role, mantra, appearances=5, rated_appearances=5, average_rating=6.0, club_goals_per_match=2.0
        ),
        CLASSIC,
    )
    assert played.goal_share == pytest.approx(goal * weight / (weight + 10))


def test_t_takes_attacking_midfielder_priors() -> None:
    """R2.6: a forward listed first as T moves from the forward model's 0.20 to an attacking midfielder's."""
    value = outfield.value(player("A", "T"), CLASSIC)
    assert value.goal_share == pytest.approx(0.15)
    assert value.e_goals == pytest.approx(1.4 * 0.15 * 0.80)
