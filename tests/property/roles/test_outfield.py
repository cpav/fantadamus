"""mvp-roles P5 and P6: shares start at the role's priors and rise with his goals and assists; a bigger goal
bonus for his role never lowers his value (design C6; R2.1 to R2.3, R2.5)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.contracts.types import Role
from fantadamus.engine import outfield
from fantadamus.engine.constants import ROLE_PRIORS
from fantadamus.engine.rank import Scoring
from tests.roles_data import outfield as player

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
roles: st.SearchStrategy[Role] = st.sampled_from(["D", "C", "A"])
mantra = st.sampled_from(sorted(ROLE_PRIORS))


@given(
    role=roles,
    mantra_role=mantra,
    games=st.integers(1, 38),
    goals=st.integers(0, 10),
    assists=st.integers(0, 10),
)
def test_p5_priors_without_games(role: Role, mantra_role: str, games: int, goals: int, assists: int) -> None:
    prior = ROLE_PRIORS[mantra_role]
    fresh = outfield.value(player(role, mantra_role), CLASSIC)
    assert abs(fresh.goal_share - prior.goal) < 1e-12
    assert abs(fresh.assist_share - prior.assist) < 1e-12
    played = {"appearances": games, "rated_appearances": games, "average_rating": 6.0}
    before = outfield.value(player(role, mantra_role, **played, goals=goals, assists=assists), CLASSIC)
    after = outfield.value(player(role, mantra_role, **played, goals=goals + 1, assists=assists + 1), CLASSIC)
    assert after.goal_share > before.goal_share
    assert after.assist_share > before.assist_share


@given(role=roles, mantra_role=mantra, goal=st.floats(0, 9), more=st.floats(0, 1), goals=st.integers(0, 10))
def test_p6_goal_bonus_never_lowers(
    role: Role, mantra_role: str, goal: float, more: float, goals: int
) -> None:
    someone = player(role, mantra_role, appearances=10, rated_appearances=10, average_rating=6.2, goals=goals)
    low = outfield.value(someone, CLASSIC.model_copy(update={"goal": goal}))
    high = outfield.value(someone, CLASSIC.model_copy(update={"goal": goal + more}))
    assert high.e_start >= low.e_start
