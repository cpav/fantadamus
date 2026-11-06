"""P11: for any forward, the chance of a rating and the key reproduce his simulated mean, so they can be
trusted for ordering (design C1; R8.3)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine import outfield
from fantadamus.engine.rank import Scoring
from fantadamus.engine.simulate import draw_rounds, outfield_player
from tests.roles_data import outfield as outfield_inputs

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
ROUNDS = 6000


@given(
    p_start=st.sampled_from((0.0, 0.3, 0.7)),
    comes_on=st.sampled_from((0.1, 0.3)),
    team_xg=st.sampled_from((0.8, 2.0)),
    taker=st.booleans(),
    mantra=st.sampled_from(("Pc", "W", "Dc")),
)
def test_p11_chance_and_key_reproduce_the_simulated_mean(
    p_start: float, comes_on: float, team_xg: float, taker: bool, mantra: str
) -> None:
    inputs = outfield_inputs(
        "D" if mantra == "Dc" else "A",
        mantra,
        appearances=8,
        goals=3,
        team_xg=team_xg,
        penalty_share=float(taker),
        p_start=p_start,
        p_cameo=comes_on,
    )
    value = outfield.value(inputs, CLASSIC)
    player = outfield_player(1, inputs, value, CLASSIC, (0, 0))
    scores = [scores[1] for scores, _ in draw_rounds([player], [(team_xg, 1.0)], rounds=ROUNDS, seed=43)]
    rated = [score for score in scores if score is not None]
    chance = value.p_start + value.p_cameo
    assert len(rated) / ROUNDS == pytest.approx(chance, abs=0.035)
    assert sum(rated) / ROUNDS == pytest.approx(chance * value.key, abs=0.25)
