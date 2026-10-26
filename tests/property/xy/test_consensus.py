"""P1 to P3: consensus is a probability, an official lineup always wins, and outlet order doesn't matter
(design C5; R3, R4.2)."""

from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.availability.consensus import (
    OfficialStatus,
    OfficialView,
    OutletView,
    Status,
    combine,
    outlet_view,
)
from fantadamus.domains.facts import Source

SOURCE = Source(
    source_url="https://example.org/a",
    captured_at=dt.datetime(2026, 10, 31, tzinfo=dt.UTC),
    content_sha256="0" * 64,
)
statuses: st.SearchStrategy[Status] = st.sampled_from(
    ["starter", "ballottaggio", "bench", "unavailable", "not listed"]
)
official_statuses: st.SearchStrategy[OfficialStatus] = st.sampled_from(["starter", "bench", "not listed"])
shares = st.floats(min_value=0, max_value=100, allow_nan=False)


@st.composite
def views(draw: st.DrawFn) -> list[OutletView]:
    count = draw(st.integers(min_value=1, max_value=6))
    return [outlet_view(f"Outlet {index}", draw(statuses), draw(shares), SOURCE) for index in range(count)]


@given(views())
def test_p1_probabilities_bounded(outlets: list[OutletView]) -> None:
    result = combine(outlets)
    assert 0 <= result.p_start <= 1
    assert 0 <= result.p_cameo <= 1
    assert result.p_start + result.p_cameo <= 1 + 1e-12


@given(views(), official_statuses)
def test_p2_official_lineup_wins(outlets: list[OutletView], status: OfficialStatus) -> None:
    result = combine(outlets, OfficialView(status=status, source=SOURCE))
    expected = {"starter": (1.0, 0.0), "bench": (0.0, 0.5), "not listed": (0.0, 0.0)}[status]
    assert (result.p_start, result.p_cameo) == expected
    assert not result.disputed


@given(views().flatmap(lambda outlets: st.tuples(st.just(outlets), st.permutations(outlets))))
def test_p3_outlet_order_ignored(orders: tuple[list[OutletView], list[OutletView]]) -> None:
    submitted, reordered = orders
    assert combine(submitted) == combine(reordered)
