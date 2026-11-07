"""P3, P4 and P6 of mvp-rules: one table, read the same way by every path (R1.1, R1.2, R1.6)."""

from __future__ import annotations

import math
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import EventName, EventRow, LeagueRules
from fantadamus.engine import keepers, outfield
from fantadamus.engine.simulate import draw_rounds, keeper_player, outfield_player
from fantadamus.league.rules import scoring_for
from tests.roles_data import keeper as keeper_inputs
from tests.roles_data import outfield as outfield_inputs

ROLES: tuple[Role, ...] = ("P", "D", "C", "A")
_ROUNDS = 4_000
_BONUS = st.sampled_from((0.0, 0.5, 1.0, 3.0))
_MALUS = st.sampled_from((0.0, -0.5, -1.0, -3.0))


@given(points=_BONUS, role=st.sampled_from(ROLES), other=st.sampled_from(ROLES))
def test_p3_a_row_changes_only_its_roles(points: float, role: Role, other: Role) -> None:
    base = LeagueRules(events=[EventRow(event="assist", points=1.0, roles=list(ROLES))])
    plus = LeagueRules(
        events=[*base.events, EventRow(event="own_goal", points=-points, roles=[role])],
    )
    if other != role:
        assert scoring_for(plus, other) == scoring_for(base, other)
    assert scoring_for(plus, role).own_goal == -points


@given(
    goal=_BONUS,
    assist=_BONUS,
    penalty_scored=_BONUS,
    penalty_missed=_MALUS,
    penalty_saved=_BONUS,
    own_goal=_MALUS,
    yellow_card=_MALUS,
    red_card=_MALUS,
    goal_conceded=_MALUS,
    clean_sheet=_BONUS,
)
def test_p6_earlier_rules_convert(**earlier: Any) -> None:
    """Whatever the values, each reaches the engine as it did, a keeper's only for keepers."""
    rules = LeagueRules.model_validate(earlier)
    for role in ROLES:
        scoring = scoring_for(rules, role)
        assert scoring.goal == earlier["goal"]
        assert scoring.assist == earlier["assist"]
        assert scoring.penalty_missed == earlier["penalty_missed"]
        assert scoring.red == earlier["red_card"]
        assert scoring.clean_sheet == (earlier["clean_sheet"] if role == "P" else 0)
        assert scoring.goal_conceded == (earlier["goal_conceded"] if role == "P" else 0)
        assert scoring.penalty_saved == (earlier["penalty_saved"] if role == "P" else 0)


def _table(role: Role, points: dict[EventName, float]) -> LeagueRules:
    return LeagueRules(
        events=[EventRow(event=event, points=value, roles=[role]) for event, value in points.items()]
    )


@given(
    team_xg=st.sampled_from((0.8, 1.6)),
    share=st.sampled_from((0.0, 1.0)),
    missed=st.sampled_from((0.0, -3.0)),
    red=st.sampled_from((0.0, -1.0)),
    own_goal=st.sampled_from((0.0, -2.0)),
    clean_sheet=st.sampled_from((0.0, 2.0)),
    conceded=st.sampled_from((0.0, -1.0)),
)
def test_p4_the_mean_matches_the_model(
    team_xg: float,
    share: float,
    missed: float,
    red: float,
    own_goal: float,
    clean_sheet: float,
    conceded: float,
) -> None:
    """Certain to start, a player's mean over many rounds is his model's value, for any table."""
    rules = _table(
        "D",
        {
            "goal": 3.0,
            "assist": 1.0,
            "penalty_scored": 3.0,
            "penalty_missed": missed,
            "yellow_card": -0.5,
            "red_card": red,
            "own_goal": own_goal,
            "clean_sheet": clean_sheet,
            "goal_conceded": conceded,
        },
    )
    scoring = scoring_for(rules, "D")
    inputs = outfield_inputs(
        "D",
        "Dc",
        appearances=8,
        rated_appearances=8,
        average_rating=6.3,
        penalty_share=share,
        team_xg=team_xg,
        opponent_xg=1.2,
        p_start=1.0,
        p_cameo=0.0,
    )
    value = outfield.value(inputs, scoring)
    player = outfield_player(1, inputs, value, scoring, (0, 0))
    scored = [
        score
        for scores, _ in draw_rounds([player], [(team_xg, 1.2)], rounds=_ROUNDS, seed=17)
        if (score := scores[1]) is not None
    ]
    assert math.fsum(scored) / _ROUNDS == pytest.approx(value.e_start, abs=0.2)


@given(saved=st.sampled_from((0.0, 3.0)), red=st.sampled_from((0.0, -1.0)))
def test_p4_a_keepers_mean_matches_too(saved: float, red: float) -> None:
    rules = _table("P", {"clean_sheet": 1.0, "goal_conceded": -1.0, "penalty_saved": saved, "red_card": red})
    scoring = scoring_for(rules, "P")
    inputs = keeper_inputs(opponent_xg=1.1, p_start=1.0)
    value = keepers.value(inputs, scoring)
    player = keeper_player(1, inputs, value, scoring, (0, 0))
    scored = [
        score
        for scores, _ in draw_rounds([player], [(1.0, 1.1)], rounds=_ROUNDS, seed=19)
        if (score := scores[1]) is not None
    ]
    assert math.fsum(scored) / _ROUNDS == pytest.approx(value.e_start, abs=0.2)
