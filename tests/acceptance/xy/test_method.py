"""AT-1 to AT-3: method §A9 tests 2, 4 and 6 for forwards (R9.3, R9.4, R9.7, R9.8, R10.1, R10.6)."""

from __future__ import annotations

import pytest

from fantadamus.engine import forwards
from fantadamus.engine.forwards import ForwardInputs, Option, Scoring

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5)


def test_at1_tie_and_rejected_ranking() -> None:
    """§A9.2: with a flat 5.5 cameo, the two attackers tie on the key; the ranking that ignores the bench
    (5.88 vs 6.21) is not the verdict."""
    doubtful = Option(name="X", p_start=0.55, p_cameo=0.35, e_start=7.2, e_cameo=5.5)
    certain = Option(name="Y", p_start=0.90, p_cameo=0.05, e_start=6.6, e_cameo=5.5)
    assert forwards.key(**doubtful.figures()) == pytest.approx(6.54, abs=0.005)
    assert forwards.key(**certain.figures()) == pytest.approx(6.54, abs=0.005)
    verdict = forwards.verdict(doubtful, certain)
    assert verdict.label == "coin flip"
    assert verdict.margin < 0.01
    assert forwards.no_cover(**doubtful.figures()) == pytest.approx(5.885)
    assert forwards.no_cover(**certain.figures()) == pytest.approx(6.215)
    assert verdict.no_cover_first == "Y"


def test_at2_goal_chances() -> None:
    """§A9.4: a centre-forward with 4 goals in 5, team xG 1.35 and 88 % to start is about 32 % to score; a
    rotation striker at 25 % with team xG 1.1 is about 12 %; the first ranks ahead."""
    centre = ForwardInputs(
        name="Centravanti",
        mantra_role="Pc",
        appearances=5,
        rated_appearances=5,
        average_rating=6.5,
        goals=4,
        assists=0,
        yellow_cards=0,
        club_goals_per_match=2.0,
        penalty_taker=False,
        team_xg=1.35,
        p_win=0.45,
        p_loss=0.30,
        p_start=0.88,
        p_cameo=0.06,
    )
    rotation = centre.model_copy(
        update={
            "name": "Ala",
            "mantra_role": "W",
            "appearances": 8,
            "rated_appearances": 8,
            "goals": 1,
            "club_goals_per_match": 1.2,
            "team_xg": 1.1,
            "p_start": 0.25,
            "p_cameo": 0.375,
        }
    )
    first, second = forwards.value(centre, CLASSIC), forwards.value(rotation, CLASSIC)
    assert first.goal_share == pytest.approx(0.34)
    assert first.p_scores == pytest.approx(0.32, abs=0.005)
    assert second.p_scores == pytest.approx(0.12, abs=0.005)
    assert forwards.compare(centre, rotation, CLASSIC).verdict.first == "Centravanti"


def test_at3_bench_cover_changes_verdict() -> None:
    """§A9.6: X is ahead if he plays but only 55 % to get a rating: start X, Y first on the bench; without
    bench cover, Y."""
    x = Option(name="X", p_start=0.45, p_cameo=0.10, e_start=7.6, e_cameo=6.0)
    y = Option(name="Y", p_start=0.95, p_cameo=0.02, e_start=6.6, e_cameo=6.0)
    verdict = forwards.verdict(y, x)
    assert (verdict.first, verdict.second) == ("X", "Y")
    assert verdict.margin == pytest.approx(7.309 - 6.588, abs=0.002)
    assert verdict.label == "clear"
    assert forwards.no_cover(**x.figures()) == pytest.approx(4.02)
    assert forwards.no_cover(**y.figures()) == pytest.approx(6.39)
    assert verdict.no_cover_first == "Y"
    assert verdict.no_cover_differs
