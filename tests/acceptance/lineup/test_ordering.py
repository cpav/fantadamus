"""AT-1: method §A9 test 1. Sorting by the key is optimal in 100% of cases: an exact enumeration of who gets a
rating, across every ordering of random players, independent of the simulation (R3.2)."""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine.lineup import Candidate, arrange
from tests.lineup_data import candidate, lineup_rules

_UNIT = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
_FORWARD = st.tuples(_UNIT, _UNIT, st.floats(min_value=3.0, max_value=13.0, allow_nan=False))
_OTHERS = [
    candidate(1, "P"),
    *(candidate(10 + number, "D") for number in range(5)),
    *(candidate(20 + number, "C") for number in range(5)),
]
_FORMATIONS = {1: "5-4-1", 2: "4-4-2", 3: "3-4-3"}


def _expected(order: tuple[Candidate, ...], places: int) -> float:
    """Exactly: whoever gets a rating counts, in order, until the places are filled. With the bench covering
    every place, those are the starters who got one and then the first bench players who did."""
    total = 0.0
    for rated in itertools.product((True, False), repeat=len(order)):
        chance = 1.0
        for player, has in zip(order, rated, strict=True):
            rating = player.p_start + player.p_cameo
            chance *= rating if has else 1 - rating
        counted = [player for player, has in zip(order, rated, strict=True) if has][:places]
        total += chance * sum(player.key for player in counted)
    return total


@given(raw=st.lists(_FORWARD, min_size=4, max_size=4), places=st.sampled_from((1, 2, 3)))
def test_at1_sorting_by_key_is_optimal(raw: list[tuple[float, float, float]], places: int) -> None:
    forwards = [
        candidate(100 + number, "A", p_start=p_start, p_cameo=(1 - p_start) * share, key=key)
        for number, (p_start, share, key) in enumerate(raw)
    ]
    arranged = arrange([*_OTHERS, *forwards], _FORMATIONS[places], lineup_rules(bench_size=14))
    ours = tuple(player for player in (*arranged.starters, *arranged.bench) if player.role == "A")
    best = max(_expected(order, places) for order in itertools.permutations(forwards))
    assert _expected(ours, places) == pytest.approx(best)
