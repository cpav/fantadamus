"""P7: a choice's worth never exceeds the difference in keys, doesn't depend on the order asked, and never
changes who comes first (design C1; R8.1)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine import rank
from fantadamus.engine.rank import Option

_POINTS = st.floats(min_value=3.0, max_value=15.0, allow_nan=False)


def _option(name: str) -> st.SearchStrategy[Option]:
    def build(p_start: float, share: float, e_start: float, e_cameo: float) -> Option:
        return Option(
            name=name, p_start=p_start, p_cameo=(1 - p_start) * share, e_start=e_start, e_cameo=e_cameo
        )

    unit = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
    return st.builds(build, unit, unit, _POINTS, _POINTS)


@given(a=_option("A"), b=_option("B"))
def test_p7_worth_is_bounded_and_keeps_the_order(a: Option, b: Option) -> None:
    verdict = rank.verdict(a, b)
    keys = {option.name: rank.key(**option.figures()) for option in (a, b)}
    assert keys[verdict.first] >= keys[verdict.second]  # the order follows the key, whatever the margin
    assert verdict.key_margin == pytest.approx(keys[verdict.first] - keys[verdict.second])
    assert 0.0 <= verdict.margin <= verdict.key_margin + 1e-12
    assert verdict.label == rank.label(verdict.margin)
    other = rank.verdict(b, a)
    assert (other.first, other.second) == (verdict.first, verdict.second)
    assert other.margin == pytest.approx(verdict.margin)
