"""P7 of mvp-rules: a captain's points stay within the bands, and the recommended captain and vice bring at
least as much over the rounds as any other pair (R3.3)."""

from __future__ import annotations

import itertools

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.contracts.xy.league import Band
from fantadamus.engine.formula import band_points, choose_captain

_VOTES = st.one_of(st.none(), st.floats(min_value=2.0, max_value=10.0))
_BANDS = st.lists(
    st.tuples(st.floats(min_value=0.0, max_value=10.0), st.floats(min_value=-10.0, max_value=10.0)),
    min_size=1,
    max_size=6,
    unique_by=lambda band: band[0],
)


@given(
    votes=st.lists(st.lists(_VOTES, min_size=6, max_size=6), min_size=1, max_size=5),
    bands=_BANDS,
    stand_in=st.one_of(st.none(), st.floats(min_value=0.0, max_value=10.0)),
)
def test_p7_a_captains_points_stay_in_the_bands(
    votes: list[list[float | None]], bands: list[tuple[float, float]], stand_in: float | None
) -> None:
    rising = [Band(from_value=start, points=points) for start, points in sorted(bands)]
    points = {
        player: [None if vote is None else band_points(rising, vote) for vote in rounds]
        for player, rounds in enumerate(votes)
    }
    fallback = 0.0 if stand_in is None else band_points(rising, stand_in)
    pool = list(points)
    chosen = choose_captain(pool, points, fallback=fallback)
    lowest, highest = min(0.0, *(band.points for band in rising)), max(0.0, *(band.points for band in rising))
    assert all(lowest <= value <= highest for value in chosen.points)
    for captain, vice in itertools.permutations(pool, 2):
        other = choose_captain([captain, vice], points, fallback=fallback, named=captain)
        assert sum(chosen.points) >= sum(other.points) - 1e-9
