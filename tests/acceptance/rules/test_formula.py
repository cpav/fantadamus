"""AT-5, AT-6 and AT-11 of mvp-rules: formula rules as data, worked out by hand (R2.1, R2.2, R2.4)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from fantadamus.contracts.xy.league import Band, FormulaRule, LeagueRules, Unit
from fantadamus.engine.formula import Mark, formula_points
from fantadamus.league.rules import CLASSIC

GAZZETTA = FormulaRule(
    name="defence modifier",
    who=[Unit(role="P"), Unit(role="D", best=3, at_least=4)],
    combine="average",
    base=4,
    stand_in=[5.0, 4.5],
    bands=[
        Band(from_value=6.0, points=1.0),
        Band(from_value=6.5, points=3.0),
        Band(from_value=7.0, points=6.0),
    ],
)
ATTACK = FormulaRule(
    name="attack modifier",
    who=[Unit(role="A")],
    combine="each",
    leave_out="bonus_or_goal",
    bands=[
        Band(from_value=6.5, points=0.5),
        Band(from_value=7.0, points=1.0),
        Band(from_value=7.5, points=1.5),
        Band(from_value=8.0, points=2.0),
    ],
)


def _team(
    keeper: float, defenders: tuple[float, ...], forwards: tuple[float, ...] = (), scored: int = -1
) -> list[Mark]:
    team = [Mark(role="P", vote=keeper, bonus_or_goal=False)]
    team += [Mark(role="D", vote=vote, bonus_or_goal=False) for vote in defenders]
    team += [Mark(role="A", vote=vote, bonus_or_goal=index == scored) for index, vote in enumerate(forwards)]
    return team


def test_at5_the_defence_modifier_by_hand() -> None:
    """The keeper and the three best defenders, averaged."""
    assert formula_points(GAZZETTA, _team(6.0, (6.5, 7.0, 6.0, 5.5))) == 1.0  # 25.5 / 4 = 6.375
    assert formula_points(GAZZETTA, _team(7.0, (6.5, 7.0, 6.5, 6.0))) == 3.0  # 27.0 / 4 = 6.75
    assert formula_points(GAZZETTA, _team(7.5, (7.0, 7.0, 6.5, 6.0))) == 6.0  # 28.0 / 4 = 7.0, an edge
    assert formula_points(GAZZETTA, _team(5.5, (6.0, 6.0, 5.5, 5.5))) == 0.0  # 23.0 / 4 = 5.75: no band
    assert formula_points(GAZZETTA, _team(5.0, (7.0, 7.0, 7.0, 7.0))) == 3.0  # the keeper counts: 26.0 / 4


def test_at5_a_stand_in_and_the_condition() -> None:
    """With three defenders fielded the condition fails. Without it, the missing count at their stand-ins."""
    assert formula_points(GAZZETTA, _team(7.0, (7.0, 7.0, 7.0))) == 0.0
    open_to_any = GAZZETTA.model_copy(update={"who": [Unit(role="P"), Unit(role="D", best=3)]})
    assert formula_points(open_to_any, _team(7.0, (7.0, 7.0))) == 3.0  # (7 + 7 + 7 + 5.0) / 4 = 6.5
    assert formula_points(open_to_any, _team(7.0, (7.0,))) == 0.0  # (7 + 7 + 5.0 + 4.5) / 4 = 5.875
    one_stand_in = open_to_any.model_copy(update={"stand_in": [6.0]})
    assert formula_points(one_stand_in, _team(7.0, (7.0,))) == 3.0  # (7 + 7 + 6.0 + 6.0) / 4 = 6.5
    at_most_four = GAZZETTA.model_copy(update={"who": [Unit(role="P"), Unit(role="D", best=3, at_most=4)]})
    assert formula_points(at_most_four, _team(7.5, (7.0, 7.0, 6.5, 6.0))) == 6.0  # four defenders: allowed
    assert formula_points(at_most_four, _team(7.5, (7.0, 7.0, 6.5, 6.0, 6.0))) == 0.0  # five defenders


def test_at6_the_attack_modifier_by_hand() -> None:
    """Each forward on his own, and one who scored is left out."""
    assert formula_points(ATTACK, _team(6.0, (), (6.5, 7.0, 8.0))) == 3.5  # 0.5 + 1.0 + 2.0
    assert formula_points(ATTACK, _team(6.0, (), (6.5, 7.0, 8.0), scored=2)) == 1.5  # 0.5 + 1.0
    assert formula_points(ATTACK, _team(6.0, (6.0, 8.0))) == 0.0  # no forwards: nothing


def _refused(payload: dict[str, Any], says: str) -> None:
    with pytest.raises(ValidationError, match=says):
        FormulaRule.model_validate(payload)


BASE: dict[str, Any] = {
    "name": "a rule",
    "who": [{"role": "D"}],
    "combine": "average",
    "bands": [{"from_value": 6.0, "points": 1.0}],
}


@pytest.mark.parametrize(
    ("change", "says"),
    [
        (
            {"bands": [{"from_value": 6.5, "points": 1.0}, {"from_value": 6.0, "points": 3.0}]},
            "bands must rise",
        ),
        ({"bands": []}, "at least 1 item"),
        ({"bands": [{"from_value": 6.0, "points": 11.0}]}, "less than or equal to 10"),
        ({"combine": "each", "base": 4}, "on his own"),
        ({"combine": "each", "stand_in": [5.0]}, "on his own"),
        ({"who": "captain", "combine": "average"}, "the captain is one player"),
        ({"who": [{"role": "D"}, {"role": "D"}]}, "D is listed twice"),
        ({"who": []}, "at least 1 item"),
        ({"who": [{"role": "D", "best": 0}]}, "greater than or equal to 1"),
        ({"who": [{"role": "D", "at_least": 5, "at_most": 4}]}, "at_least is above at_most"),
        ({"stand_in": [5.0, 4.5, 4.0]}, "at most 2 items"),
        ({"combine": "median"}, "Input should be"),
    ],
)
def test_at11_an_impossible_rule_is_refused(change: dict[str, Any], says: str) -> None:
    _refused(BASE | change, says)


def test_at11_a_rule_cant_carry_code() -> None:
    """Every field is a number or a fixed word: text in their place is refused, never run."""
    _refused(BASE | {"who": "__import__('os').system('true')"}, "Input should be")
    _refused(BASE | {"combine": "lambda votes: 99"}, "Input should be")
    _refused(BASE | {"formula": "votes * 2"}, "Extra inputs are not permitted")


def test_at11_two_rules_with_one_name_are_refused() -> None:
    twice = [GAZZETTA.model_dump(), GAZZETTA.model_dump()]
    with pytest.raises(ValidationError, match="defence modifier is listed twice"):
        LeagueRules.model_validate(CLASSIC.model_dump() | {"formula_rules": twice})


def test_at11_a_league_has_one_captain() -> None:
    captain = {"who": "captain", "combine": "each", "bands": [{"from_value": 6.0, "points": 1.0}]}
    two = [captain | {"name": "captain"}, captain | {"name": "vice captain"}]
    with pytest.raises(ValidationError, match="one captain"):
        LeagueRules.model_validate(CLASSIC.model_dump() | {"formula_rules": two})


def test_at11_a_league_keeps_its_rules() -> None:
    rules = LeagueRules.model_validate(CLASSIC.model_dump() | {"formula_rules": [GAZZETTA.model_dump()]})
    assert rules.formula_rules == [GAZZETTA]
