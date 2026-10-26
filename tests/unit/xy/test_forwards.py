"""Task 5: the forward model's formulas, the margin labels and the flip points (C8; R9, R10.2, R10.4)."""

from __future__ import annotations

import math

import pytest

from fantadamus.engine import forwards
from fantadamus.engine.forwards import ForwardInputs, Scoring

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5)


def striker(**changes: object) -> ForwardInputs:
    base = ForwardInputs(
        name="Alfa Nove",
        mantra_role="Pc",
        appearances=5,
        rated_appearances=5,
        average_rating=6.6,
        goals=4,
        assists=1,
        yellow_cards=1,
        club_goals_per_match=2.0,
        penalty_taker=False,
        team_xg=1.35,
        p_win=0.5,
        p_loss=0.25,
        p_start=0.88,
        p_cameo=0.06,
    )
    return base.model_copy(update=changes)


def test_formulas_by_hand() -> None:
    assert forwards.expected_vote(8, 6.4, p_win=0.45, p_loss=0.30) == pytest.approx(
        6 + 8 / 18 * 0.4 + 0.3 * 0.15
    )
    assert forwards.expected_vote(0, None, p_win=0.5, p_loss=0.5) == 6.0
    assert forwards.share(0.30, events=4, team_goals=10) == pytest.approx(0.34)
    assert forwards.expected_goals(1.35, 0.34, minutes=0.85) == pytest.approx(0.39015)
    assert forwards.penalty_goals(minutes=0.85, taker=True) == pytest.approx(0.15 * 0.78 * 0.85)
    assert forwards.penalty_goals(minutes=0.85, taker=False) == 0
    assert forwards.p_yellow(2, appearances=8) == pytest.approx(3.5 / 18)
    assert forwards.e_cameo(0.2) == pytest.approx((1 - math.exp(-0.2)) * 9.8 + math.exp(-0.2) * 0.6 * 5.75)

    value = forwards.value(striker(penalty_taker=True), CLASSIC)
    vote = 6 + 5 / 15 * 0.6 + 0.3 * 0.25
    goal_share, assist_share = (0.30 * 15 + 4) / 25, (0.11 * 15 + 1) / 25
    goals = 1.35 * goal_share * 0.85 + 0.15 * 0.78 * 0.85
    assists = 1.35 * assist_share * 0.85
    yellow = (1.5 + 1) / 15
    assert value.expected_vote == pytest.approx(vote)
    assert value.goal_share == pytest.approx(0.34)
    assert value.e_goals == pytest.approx(goals)
    assert value.p_scores == pytest.approx(1 - math.exp(-goals))
    assert value.e_start == pytest.approx(vote + 3 * goals + assists - 0.5 * yellow)
    cameo_goals = 1.35 * goal_share * 0.28 + 0.15 * 0.78 * 0.28
    assert value.e_cameo == pytest.approx(forwards.e_cameo(cameo_goals))
    assert value.key == pytest.approx(forwards.key(0.88, value.e_start, 0.06, value.e_cameo))
    assert forwards.value(striker(mantra_role=None), CLASSIC).goal_share == pytest.approx(
        (0.20 * 15 + 4) / 25
    )


def test_signed_yellow_lowers_score() -> None:
    careful, booked = (
        forwards.value(striker(yellow_cards=0), CLASSIC),
        forwards.value(striker(yellow_cards=5), CLASSIC),
    )
    assert booked.e_start < careful.e_start
    lenient = Scoring(goal=3, penalty_scored=3, assist=1, yellow=0)
    assert forwards.value(striker(yellow_cards=5), lenient).e_start > booked.e_start


@pytest.mark.parametrize(
    ("margin", "label"),
    [(0.0, "coin flip"), (0.149, "coin flip"), (0.15, "lean"), (0.5, "lean"), (0.51, "clear")],
)
def test_margin_labels(margin: float, label: str) -> None:
    assert forwards.label(margin) == label


def test_flip_points() -> None:
    leader, trailer = striker(), striker(name="Beta Nove", goals=2, p_start=0.95, p_cameo=0.02, team_xg=1.2)
    comparison = forwards.compare(leader, trailer, CLASSIC)
    assert comparison.verdict.first == "Alfa Nove"
    assert comparison.flip_p_start is not None
    assert comparison.flip_team_xg is not None
    for field, flip in (("p_start", comparison.flip_p_start), ("team_xg", comparison.flip_team_xg)):
        below = forwards.compare(leader.model_copy(update={field: flip - 0.01}), trailer, CLASSIC)
        above = forwards.compare(leader.model_copy(update={field: flip + 0.01}), trailer, CLASSIC)
        assert (below.verdict.first, above.verdict.first) == ("Beta Nove", "Alfa Nove"), field
    certain = forwards.compare(leader.model_copy(update={"p_start": 1.0, "p_cameo": 0.0}), trailer, CLASSIC)
    assert certain.flip_p_start is None  # nothing short of not playing changes his key


def test_verdict_knows_who_can_play() -> None:
    fit = forwards.Option(name="X", p_start=0.4, p_cameo=0.3, e_start=7.0, e_cameo=5.0)
    injured = forwards.Option(name="Y", p_start=0.0, p_cameo=0.0, e_start=7.5, e_cameo=5.0)
    verdict = forwards.verdict(injured, fit)
    assert (verdict.first, verdict.second) == ("X", "Y")
    assert (verdict.first_plays, verdict.second_plays) == (True, False)
    neither = forwards.verdict(injured, injured.model_copy(update={"name": "Z"}))
    assert (neither.first_plays, neither.second_plays) == (False, False)
    both = forwards.verdict(fit, fit.model_copy(update={"name": "W"}))
    assert (both.first_plays, both.second_plays) == (True, True)
