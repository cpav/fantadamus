"""mvp-roles task 4.3: the keeper model, read net of his goals conceded (design C7; method §A6; R3.1 to R3.4,
R4.1)."""

from __future__ import annotations

import math

import pytest

from fantadamus.engine import keepers
from fantadamus.engine.rank import Scoring
from tests.roles_data import keeper

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)


def test_keeper_value_steps() -> None:
    value = keepers.value(keeper(), CLASSIC)
    prior = 6.0 + 0.35 * 1.3
    skill = prior + 8 / 17 * (6.2 + 0.35 * 9 / 8 - prior)
    assert value.skill == pytest.approx(skill)
    assert value.expected_vote == pytest.approx(skill - 0.35 * 1.1)
    assert value.p_clean_sheet == pytest.approx(math.exp(-1.1))
    assert value.expected_conceded == 1.1
    assert value.e_start == pytest.approx(skill - 0.35 * 1.1 + math.exp(-1.1) - 1.1)
    assert value.p_cameo == 0.0  # R3.4: no cameo
    assert value.key == pytest.approx(value.e_start)
    assert value.no_cover == pytest.approx(0.95 * value.e_start)
    unknown = keepers.value(keeper(goals_conceded=None), CLASSIC)  # an average defence assumed
    assert unknown.skill == pytest.approx(prior + 8 / 17 * (6.2 + 0.35 * 1.3 - prior))
    unrated = keepers.value(keeper(rated_appearances=0, average_rating=None, goals_conceded=0), CLASSIC)
    assert unrated.skill == pytest.approx(prior)
    out = keepers.value(keeper(p_start=0.0), CLASSIC)
    assert (out.key, out.no_cover) == (0.0, 0.0)


def test_flip_on_opponent_xg() -> None:
    leader, trailer = (
        keeper(name="Leader", opponent_xg=0.9),
        keeper(name="Trailer", club="beta", opponent_xg=1.3),
    )
    result = keepers.compare(leader, trailer, CLASSIC)
    assert result.verdict.first == "Leader"
    assert result.flip_opponent_xg is not None
    assert result.flip_opponent_xg == pytest.approx(1.3, abs=1e-6)  # equal skill: level once the matches are
    far = keepers.compare(
        keeper(name="Leader", average_rating=7.5), keeper(name="Trailer", club="beta"), CLASSIC
    )
    assert far.flip_opponent_xg is not None
    assert far.flip_opponent_xg > 1.1
