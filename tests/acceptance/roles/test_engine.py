"""mvp-roles AT-1 to AT-5: the engine for keepers, defenders and midfielders (design C6, C7; method §A4, §A5,
§A6, §A9 tests 3 and 6)."""

from __future__ import annotations

import math

import pytest

from fantadamus.engine import keepers, outfield
from fantadamus.engine.constants import DIXON_COLES_RHO
from fantadamus.engine.odds import fit, form_xg, model
from fantadamus.engine.rank import Scoring
from tests.roles_data import keeper
from tests.roles_data import outfield as player

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
LEAGUE = 1.3


def test_at1_keepers_on_regressed_form() -> None:
    """§A9 test 3 at the method's weights: equal skill, clubs that conceded 6 and 9 in five matches, both
    against an average attack: about +0.9 on raw form, about 0.3 regressed, under 0.1 on odds alike."""
    tight, leaky = keeper(name="Tight", club="alfa"), keeper(name="Leaky", club="beta")
    tight = tight.model_copy(
        update={"average_rating": 6.5 - 0.35 * 1.2, "goals_conceded": 6, "rated_appearances": 5}
    )
    leaky = leaky.model_copy(
        update={"average_rating": 6.5 - 0.35 * 1.8, "goals_conceded": 9, "rated_appearances": 5}
    )

    def gap(tight_xg: float, leaky_xg: float) -> float:
        a = keepers.value(tight.model_copy(update={"opponent_xg": tight_xg}), CLASSIC)
        b = keepers.value(leaky.model_copy(update={"opponent_xg": leaky_xg}), CLASSIC)
        assert a.skill == pytest.approx(b.skill)
        return a.e_start - b.e_start

    average = (LEAGUE, LEAGUE, 5)  # the opponents: scored and conceded at the league's rate
    regressed = form_xg((LEAGUE, 1.2, 5), average, LEAGUE)[1], form_xg((LEAGUE, 1.8, 5), average, LEAGUE)[1]
    assert gap(1.2, 1.8) == pytest.approx(0.95, abs=0.05)  # raw five-match form
    assert gap(*regressed) == pytest.approx(0.28, abs=0.05)
    alike = fit(model(1.5, 1.2))[1]
    assert abs(gap(alike, alike)) < 0.1


def test_at2_same_skill_same_vote() -> None:
    """Average 6.0 conceding 2 a game and 6.35 conceding 1 a game, in the same games: the same keeper."""
    behind_leaky = keeper(average_rating=6.0, goals_conceded=16, rated_appearances=8)
    behind_tight = keeper(average_rating=6.35, goals_conceded=8, rated_appearances=8)
    first, second = keepers.value(behind_leaky, CLASSIC), keepers.value(behind_tight, CLASSIC)
    assert first.expected_vote == pytest.approx(second.expected_vote)


def test_at3_clean_sheet_from_the_fit() -> None:
    """An opponent expected to score about 1.0 leaves about a 37% clean sheet, from the same fit as the 1X2:
    the Dixon-Coles correction leaves each side's chance of scoring none as Poisson's."""
    home_xg, away_xg = fit(model(1.6, 1.0))
    value = keepers.value(keeper(opponent_xg=away_xg), CLASSIC)
    assert value.p_clean_sheet == pytest.approx(0.37, abs=0.01)

    def poisson(rate: float, goals: int) -> float:
        return math.exp(-rate) * rate**goals / math.factorial(goals)

    tau = {(0, 0): 1 - home_xg * away_xg * DIXON_COLES_RHO, (1, 0): 1 + away_xg * DIXON_COLES_RHO}
    corrected = sum(poisson(home_xg, x) * poisson(away_xg, 0) * tau.get((x, 0), 1) for x in range(30))
    assert value.p_clean_sheet == pytest.approx(corrected)


def test_at4_role_priors() -> None:
    """Without goals or games, a T's goal share is 0.15 and a C's 0.06; a full-back's is 0.03, shrunk with a
    weight of 25; and a forward's values are what they were (method §A9 test 4: about 32% to score)."""
    assert outfield.value(player("C", "T"), CLASSIC).goal_share == pytest.approx(0.15)
    assert outfield.value(player("C", "C"), CLASSIC).goal_share == pytest.approx(0.06)
    assert outfield.value(player("D", "Dd"), CLASSIC).goal_share == pytest.approx(0.03)
    played = player(
        "D", "Dd", appearances=5, rated_appearances=5, average_rating=6.0, club_goals_per_match=2.0
    )
    assert outfield.value(played, CLASSIC).goal_share == pytest.approx(0.03 * 25 / 35)
    centre = player(
        "A",
        "Pc",
        appearances=5,
        rated_appearances=5,
        average_rating=6.5,
        goals=4,
        club_goals_per_match=2.0,
        team_xg=1.35,
        p_start=0.88,
        p_cameo=0.06,
    )
    assert outfield.value(centre, CLASSIC).p_scores == pytest.approx(0.32, abs=0.005)


def test_at5_defenders_bench_advice() -> None:
    """§A9 test 6 for defenders: X ahead if he plays but only 55% to get a rating, each cameo 5.5: start X,
    Y first on the bench; without bench cover, Y."""
    x = player(
        "D",
        "Dc",
        name="X",
        appearances=8,
        rated_appearances=8,
        average_rating=6.4,
        goals=3,
        yellow_cards=1,
        team_xg=1.6,
        p_win=0.5,
        p_loss=0.25,
        p_start=0.45,
        p_cameo=0.10,
    )
    y = x.model_copy(
        update={"name": "Y", "average_rating": 6.0, "goals": 0, "p_start": 0.95, "p_cameo": 0.02}
    )
    result = outfield.compare(y, x, CLASSIC)
    assert [value.e_cameo for value in result.values] == [5.5, 5.5]
    assert (result.verdict.first, result.verdict.second) == ("X", "Y")
    assert result.verdict.no_cover_first == "Y"
    assert result.verdict.no_cover_differs
