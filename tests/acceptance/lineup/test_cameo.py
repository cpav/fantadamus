"""AT-16: a forward's cameo, by the method's three outcomes: he starts, he comes on and gets a rating, or he
has no rating and his substitute comes in (§A2; R8.3)."""

from __future__ import annotations

import math

import pytest

from fantadamus.engine import outfield, rank
from fantadamus.engine.constants import MINUTES_CAMEO
from fantadamus.engine.rank import Scoring
from fantadamus.engine.simulate import draw_rounds, outfield_player
from tests.roles_data import outfield as outfield_inputs

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
ROUNDS = 30_000


def _forward(**changes: float) -> outfield.OutfieldInputs:
    usual = {"appearances": 8, "rated_appearances": 8, "average_rating": 6.3, "goals": 3, "team_xg": 1.4}
    return outfield_inputs("A", "Pc", **(usual | changes))


def test_at16_a_cameo_by_hand() -> None:
    """His chance of scoring on the pitch for 0.28 of a match, then the method's own numbers."""
    inputs = _forward(p_start=0.4, p_cameo=0.3)
    value = outfield.value(inputs, CLASSIC)
    goals = 1.4 * value.goal_share * MINUTES_CAMEO
    scored = 1 - math.exp(-goals)
    rated = scored + (1 - scored) * 0.6
    assert value.p_cameo == pytest.approx(0.3 * rated)
    assert value.e_cameo == pytest.approx((scored * 9.8 + (1 - scored) * 0.6 * 5.75) / rated)
    assert 5.75 < value.e_cameo < 9.8  # a rating, never an average that counts no rating as 0
    assert value.key == pytest.approx(
        (0.4 * value.e_start + 0.3 * (scored * 9.8 + (1 - scored) * 0.6 * 5.75)) / (0.4 + 0.3 * rated)
    )


def _first_with_a_rating(first: outfield.OutfieldInputs, second: outfield.OutfieldInputs) -> float:
    """One place, one substitute: the simulated mean, whichever of them gets a rating first."""
    players = [
        outfield_player(1, first, outfield.value(first, CLASSIC), CLASSIC, (0, 0)),
        outfield_player(2, second, outfield.value(second, CLASSIC), CLASSIC, (1, 0)),
    ]
    total = 0.0
    for scores, _ in draw_rounds(players, [(1.4, 1.0), (1.4, 1.0)], rounds=ROUNDS, seed=41):
        score = scores[1] if scores[1] is not None else scores[2]
        total += score or 0.0
    return total / ROUNDS


def _by_formula(first: outfield.OutfieldInputs, second: outfield.OutfieldInputs) -> float:
    a, b = outfield.value(first, CLASSIC), outfield.value(second, CLASSIC)
    rated_a, rated_b = a.p_start + a.p_cameo, b.p_start + b.p_cameo
    return rated_a * a.key + (1 - rated_a) * rated_b * b.key


ROTATION = _forward(p_start=0.4, p_cameo=0.3)
REGULAR = _forward(p_start=0.92, p_cameo=0.04, average_rating=6.0, goals=1)


@pytest.mark.parametrize(("first", "second"), [(ROTATION, REGULAR), (REGULAR, ROTATION)])
def test_at16_either_order_matches_the_simulation(
    first: outfield.OutfieldInputs, second: outfield.OutfieldInputs
) -> None:
    """The chance of a rating and the key are what the ordering rule runs on: here they give what actually
    happens."""
    assert _first_with_a_rating(first, second) == pytest.approx(_by_formula(first, second), abs=0.06)


def test_at16_the_higher_key_is_the_better_one_to_field() -> None:
    """§A3, now true of a forward who often comes on: the key picks the better order, and what the choice is
    worth is the difference the simulation finds between the two orders (R8)."""
    a, b = outfield.value(ROTATION, CLASSIC), outfield.value(REGULAR, CLASSIC)
    verdict = rank.verdict(a, b)
    ahead, behind = (ROTATION, REGULAR) if verdict.first == a.name else (REGULAR, ROTATION)
    ahead_first = _first_with_a_rating(ahead, behind)
    behind_first = _first_with_a_rating(behind, ahead)
    assert ahead_first > behind_first
    assert ahead_first - behind_first == pytest.approx(verdict.margin, abs=0.06)


def test_at16_expected_points_without_cover_dont_change() -> None:
    """A rearrangement, not new value: p_start x E_start + chance of coming on x the old price."""
    value = outfield.value(ROTATION, CLASSIC)
    scored = value.p_scores_cameo
    old_price = scored * 9.8 + (1 - scored) * 0.6 * 5.75
    assert value.no_cover == pytest.approx(0.4 * value.e_start + 0.3 * old_price)


def test_at16_a_flat_cameo_doesnt_change() -> None:
    """Every other role's cameo always gets a rating, at the flat value."""
    defender = outfield_inputs("D", "Dc", team_xg=1.4, p_start=0.4, p_cameo=0.3)
    value = outfield.value(defender, CLASSIC)
    assert (value.p_cameo, value.e_cameo) == (0.3, 5.5)
    assert value.key == pytest.approx((0.4 * value.e_start + 0.3 * 5.5) / 0.7)
