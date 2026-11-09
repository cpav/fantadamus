"""P2 and P5 of mvp-rules: formula rules in the simulation add only their own points and repeat (R2.2,
R3.4)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import Band, FormulaRule, Unit
from fantadamus.engine import keepers, outfield
from fantadamus.engine.lineup import arrange
from fantadamus.engine.rank import Scoring
from fantadamus.engine.simulate import SimPlayer, keeper_player, outfield_player, simulate
from tests.lineup_data import FORMATIONS, full_squad, lineup_rules
from tests.roles_data import keeper as keeper_inputs
from tests.roles_data import outfield as outfield_inputs

SQUAD = full_squad()
SCORING = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
_ROLES = st.sampled_from(("P", "D", "C", "A"))


def _players() -> list[SimPlayer]:
    found: list[SimPlayer] = []
    for candidate in SQUAD:
        if candidate.role == "P":
            keeper = keeper_inputs(name=candidate.name, club=candidate.club, p_start=candidate.p_start)
            found.append(
                keeper_player(candidate.player_id, keeper, keepers.value(keeper, SCORING), SCORING, (0, 0))
            )
        else:
            inputs = outfield_inputs(
                candidate.role, None, p_start=candidate.p_start, p_cameo=candidate.p_cameo
            )
            found.append(
                outfield_player(candidate.player_id, inputs, outfield.value(inputs, SCORING), SCORING, (0, 0))
            )
    return found


PLAYERS = _players()
RULES = lineup_rules()
ARRANGEMENTS = [arrange(SQUAD, formation, RULES) for formation in FORMATIONS[:3]]


def _rule(role: Role, combine: str, points: float) -> FormulaRule:
    return FormulaRule.model_validate(
        {
            "name": "a rule",
            "who": [Unit(role=role).model_dump()],
            "combine": combine,
            "bands": [Band(from_value=5.0, points=points).model_dump()],
        }
    )


@given(role=_ROLES, combine=st.sampled_from(("average", "sum", "each")))
def test_p2_zero_bands_change_nothing(role: Role, combine: str) -> None:
    plain = simulate(PLAYERS, [(1.4, 1.2)], ARRANGEMENTS, RULES, rounds=120)
    zero = simulate(
        PLAYERS, [(1.4, 1.2)], ARRANGEMENTS, RULES, formula_rules=[_rule(role, combine, 0.0)], rounds=120
    )
    for before, after in zip(plain, zero, strict=True):
        assert after.model_copy(update={"rules": {}}) == before
        assert after.rules == {"a rule": 0.0}


@given(role=_ROLES, combine=st.sampled_from(("average", "sum", "each")))
def test_p5_the_same_inputs_the_same_results(role: Role, combine: str) -> None:
    rules = [_rule(role, combine, 2.0)]
    first = simulate(PLAYERS, [(1.4, 1.2)], ARRANGEMENTS, RULES, formula_rules=rules, rounds=120)
    assert first == simulate(PLAYERS, [(1.4, 1.2)], ARRANGEMENTS, RULES, formula_rules=rules, rounds=120)
    assert all(result.rules["a rule"] > 0 for result in first)
