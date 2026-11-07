"""mvp-rules task 2: a formula rule worked out on one round's fielded players (design C5; R2.1, R2.2)."""

from __future__ import annotations

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import Band, FormulaRule, Unit
from fantadamus.engine.formula import Mark, formula_points

GAZZETTA = [
    Band(from_value=6.0, points=1.0),
    Band(from_value=6.5, points=3.0),
    Band(from_value=7.0, points=6.0),
]


def _marks(role: Role, *votes: float, scored: tuple[float, ...] = ()) -> list[Mark]:
    return [Mark(role=role, vote=vote, bonus_or_goal=vote in scored) for vote in votes]


def test_a_sum() -> None:
    rule = FormulaRule(
        name="midfield sum",
        who=[Unit(role="C")],
        combine="sum",
        bands=[Band(from_value=24.0, points=1.0), Band(from_value=26.0, points=2.0)],
    )
    assert formula_points(rule, _marks("C", 6.0, 6.5, 6.5, 6.0)) == 1.0
    assert formula_points(rule, _marks("C", 6.5, 6.5, 6.5, 6.5)) == 2.0


def test_more_than_the_base_counts_the_best() -> None:
    rule = FormulaRule(name="four best", who=[Unit(role="D")], combine="average", base=2, bands=GAZZETTA)
    assert formula_points(rule, _marks("D", 7.0, 7.0, 5.0)) == 6.0


def test_no_stand_in_averages_those_present() -> None:
    rule = FormulaRule(name="defence", who=[Unit(role="D")], combine="average", base=4, bands=GAZZETTA)
    assert formula_points(rule, _marks("D", 6.5, 6.5)) == 3.0


def test_nobody_and_no_stand_in_gives_nothing() -> None:
    rule = FormulaRule(name="defence", who=[Unit(role="D")], combine="average", base=4, bands=GAZZETTA)
    assert formula_points(rule, _marks("A", 8.0)) == 0.0


def test_a_captain_rule() -> None:
    rule = FormulaRule(
        name="captain",
        who="captain",
        combine="each",
        stand_in=[5.0],
        bands=[
            Band(from_value=0.0, points=-1.0),
            Band(from_value=6.0, points=0.0),
            Band(from_value=7.0, points=1.0),
        ],
    )
    assert formula_points(rule, [], captain=Mark(role="A", vote=7.5, bonus_or_goal=True)) == 1.0
    assert formula_points(rule, [], captain=None) == -1.0  # no rating: his stand-in vote
    no_stand_in = rule.model_copy(update={"stand_in": []})
    assert formula_points(no_stand_in, [], captain=None) == 0.0
