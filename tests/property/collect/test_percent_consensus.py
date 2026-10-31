"""P5: consensus over outlets' percentages is a probability, ignores their order, and counts nothing else
(design C5; R4)."""

from __future__ import annotations

import datetime as dt
import math

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.availability.consensus import combine, outlet_view
from fantadamus.domains.facts import Source

SOURCE = Source(
    source_url="https://example.org/p",
    captured_at=dt.datetime(2026, 10, 30, tzinfo=dt.UTC),
    content_sha256="0" * 64,
)
percents = st.lists(st.floats(min_value=0, max_value=100, allow_nan=False), min_size=1, max_size=6)


@given(percents.flatmap(lambda values: st.tuples(st.just(values), st.permutations(values))))
def test_p5_percent_consensus(orders: tuple[list[float], list[float]]) -> None:
    given_order, shuffled = orders

    def consensus(values: list[float]) -> object:
        return combine(
            [outlet_view(f"Outlet {i}", "percentage", value, SOURCE) for i, value in enumerate(values)]
        )

    result = combine(
        [outlet_view(f"Outlet {i}", "percentage", value, SOURCE) for i, value in enumerate(given_order)]
    )
    assert 0 <= result.p_start <= 1
    assert math.isclose(result.p_start, math.fsum(given_order) / len(given_order) / 100, abs_tol=1e-12)
    assert len(result.outlets) == len(given_order)
    assert consensus(sorted(given_order)) == consensus(sorted(shuffled))
