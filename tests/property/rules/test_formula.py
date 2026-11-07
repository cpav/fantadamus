"""P1 of mvp-rules: a value gets its band's points, for any rising bands (R2.1)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.contracts.xy.league import Band, FormulaRule, Unit
from fantadamus.engine.formula import Mark, formula_points

_FROM = st.lists(st.integers(min_value=30, max_value=95), min_size=1, max_size=8, unique=True).map(
    lambda values: [value / 10 for value in sorted(values)]
)


@given(
    starts=_FROM, data=st.data(), vote=st.integers(min_value=0, max_value=100).map(lambda value: value / 10)
)
def test_p1_a_value_gets_its_bands_points(starts: list[float], data: st.DataObject, vote: float) -> None:
    points = data.draw(
        st.lists(
            st.integers(-20, 20).map(lambda value: value / 2), min_size=len(starts), max_size=len(starts)
        )
    )
    bands = [Band(from_value=start, points=point) for start, point in zip(starts, points, strict=True)]
    rule = FormulaRule(name="one", who=[Unit(role="A")], combine="each", bands=bands)
    reached = [band.points for band in bands if band.from_value <= vote]
    expected = reached[-1] if reached else 0.0
    assert formula_points(rule, [Mark(role="A", vote=vote, bonus_or_goal=False)]) == expected
