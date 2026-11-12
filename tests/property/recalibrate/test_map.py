"""P1 and P2: a fitted starting map is monotone and anchored, and without enough evidence it stays near no
change (mvp-recalibrate design C2; R2.1, R5.2)."""

from __future__ import annotations

import itertools

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine.constants import START_MAP_WEIGHT
from fantadamus.engine.recalibrate import IDENTITY, fit_start_map, mapped

_CHANCE = st.floats(min_value=0.0, max_value=1.0)
_PAIRS = st.lists(st.tuples(_CHANCE, st.booleans()), max_size=200)
_XS = st.lists(_CHANCE, min_size=2, max_size=20)
THIN = 5
"""At most this many players a bucket."""


@given(pairs=_PAIRS, xs=_XS)
def test_p1_monotone_and_anchored(pairs: list[tuple[float, bool]], xs: list[float]) -> None:
    knots = fit_start_map(pairs)
    assert knots[0] == (0.0, 0.0)
    assert knots[-1] == (1.0, 1.0)
    raws = [raw for raw, _ in knots]
    assert raws == sorted(set(raws))  # one knot per raw chance, in order
    values = [mapped(x, knots) for x in sorted(xs)]
    assert all(0.0 <= value <= 1.0 for value in values)
    assert all(low <= high for low, high in itertools.pairwise(values))
    assert mapped(0.0, knots) == 0.0
    assert mapped(1.0, knots) == 1.0


@st.composite
def _thin(draw: st.DrawFn) -> list[tuple[float, bool]]:
    """Up to `THIN` players in each of the ten buckets, each raw chance well inside its bucket."""
    found = []
    for bucket in range(10):
        for _ in range(draw(st.integers(min_value=0, max_value=THIN))):
            raw = (bucket + draw(st.floats(min_value=0.0, max_value=0.99))) / 10
            found.append((raw, draw(st.booleans())))
    return found


@given(pairs=_thin(), xs=_XS)
def test_p2_no_evidence_no_change(pairs: list[tuple[float, bool]], xs: list[float]) -> None:
    assert fit_start_map([]) == IDENTITY
    assert all(mapped(x, IDENTITY) == x for x in xs)
    reach = THIN / (THIN + START_MAP_WEIGHT)  # the most a bucket of THIN players moves
    knots = fit_start_map(pairs)
    assert all(abs(mapped(x, knots) - x) <= reach + 1e-9 for x in xs)
