"""P5: every estimated rate lies in its interval and within [0, 1] (mvp-recalibrate design C4, C5; R3.1,
R4.1)."""

from __future__ import annotations

import math

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine.recalibrate import Rate, cameo_rated, cameo_share, counted


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
        st.tuples(st.floats(min_value=0.0, max_value=0.99), st.booleans()), min_size=1, max_size=300
    ),
    share=st.floats(min_value=0.01, max_value=1.0),
)
def test_p5_the_cameo_rating_within_bounds(forwards: list[tuple[float, bool]], share: float) -> None:
    rated = cameo_rated(forwards, share)
    scoring = math.fsum(chance for chance, _ in forwards) / len(forwards)
    solved = (sum(happened for _, happened in forwards) / len(forwards) / share - scoring) / (1 - scoring)
    assert (rated is None) == (not 0 <= solved <= 1)  # a value it can't fit is no value, not a bound
    if rated is not None:
        assert _bounded(rated)
        assert rated.count == len(forwards)
