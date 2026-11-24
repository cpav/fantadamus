"""P5: every estimated rate lies in its interval and within [0, 1] (mvp-recalibrate design C4, C5; R3.1,
R4.1)."""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine.constants import CAMEO_RATED
from fantadamus.engine.recalibrate import Rate, cameo_share, cameo_share_priced, counted


def _bounded(rate: Rate) -> bool:
    return 0.0 <= rate.low <= rate.value <= rate.high <= 1.0


@given(count=st.integers(min_value=1, max_value=5000), data=st.data())
def test_p5_rates_within_bounds(count: int, data: st.DataObject) -> None:
    events = data.draw(st.integers(min_value=0, max_value=2 * count))  # more penalties than matches, even
    rate = counted("A", events, count)
    assert _bounded(rate)
    assert rate.count == count


@given(rated=st.lists(st.booleans(), min_size=1, max_size=300))
def test_p5_the_cameo_share_within_bounds(rated: list[bool]) -> None:
    share = cameo_share(rated)
    assert share is not None
    assert _bounded(share)


@given(
    forwards=st.lists(
        st.tuples(st.floats(min_value=0.0, max_value=1.0), st.booleans()), min_size=1, max_size=300
    ),
)
def test_p5_the_cameo_rating_within_bounds(forwards: list[tuple[float, bool]]) -> None:
    """The priced share, which took `CAMEO_RATED`'s place (mvp-cameos R1.4): within its interval and [0, 1],
    and no share where more of them got a rating than one who comes on is ever rated."""
    priced = cameo_share_priced(forwards)
    scoring = math.fsum(chance for chance, _ in forwards) / len(forwards)
    seen = sum(happened for _, happened in forwards) / len(forwards)
    assert (priced is None) == (seen > scoring + (1 - scoring) * CAMEO_RATED)  # no value pinned at a bound
    if priced is not None:
        assert _bounded(priced)
        assert priced.count == len(forwards)
