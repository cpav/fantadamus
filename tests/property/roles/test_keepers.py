"""mvp-roles P3 and P4: a keeper is read net of his goals conceded, and his clean sheet and value fall as the
opponent's expected goals rise (design C7; R3.1 to R3.3)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine import keepers
from fantadamus.engine.rank import Scoring
from tests.roles_data import keeper

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
xg = st.floats(min_value=0.2, max_value=4.0)


@given(
    games=st.integers(min_value=1, max_value=38),
    skill=st.floats(min_value=5.5, max_value=7.5),
    conceded=st.tuples(st.integers(min_value=0, max_value=3), st.integers(min_value=0, max_value=3)),
    opponent=xg,
)
def test_p3_skill_net_of_conceded(
    games: int, skill: float, conceded: tuple[int, int], opponent: float
) -> None:
    votes = [
        keepers.value(
            keeper(
                rated_appearances=games,
                goals_conceded=per_game * games,
                average_rating=skill - 0.35 * per_game,
                opponent_xg=opponent,
            ),
            CLASSIC,
        ).expected_vote
        for per_game in conceded
    ]
    assert abs(votes[0] - votes[1]) < 1e-9


@given(
    xgs=st.tuples(xg, xg),
    clean_sheet=st.floats(min_value=0, max_value=10),
    goal_conceded=st.floats(min_value=-10, max_value=0),
)
def test_p4_clean_sheet_falls_with_opponent_xg(
    xgs: tuple[float, float], clean_sheet: float, goal_conceded: float
) -> None:
    low, high = sorted(xgs)
    scoring = CLASSIC.model_copy(update={"clean_sheet": clean_sheet, "goal_conceded": goal_conceded})
    easier, harder = (keepers.value(keeper(opponent_xg=rate), scoring) for rate in (low, high))
    assert 0 < harder.p_clean_sheet <= easier.p_clean_sheet <= 1
    assert harder.e_start <= easier.e_start + 1e-12
