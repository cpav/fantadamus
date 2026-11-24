"""P1 and P2 (mvp-cameos design; R1.1, R1.3): the chance of a cameo is the kind's share of the chance of not
starting, and the share alone on an official bench; equal shares change nothing."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.availability.consensus import (
    OfficialStatus,
    OfficialView,
    OutletView,
    combine,
    outlet_view,
)
from fantadamus.engine import constants
from tests.cards_data import OUTLETS, source

PERCENTAGES = st.lists(st.integers(0, 100), min_size=1, max_size=len(OUTLETS))
OFFICIAL: st.SearchStrategy[OfficialStatus | None] = st.sampled_from([None, "starter", "bench", "not listed"])


def _views(percentages: list[int]) -> list[OutletView]:
    return [
        outlet_view(outlet, "percentage", p, source())
        for outlet, p in zip(OUTLETS, percentages, strict=False)
    ]


def _official(status: OfficialStatus | None) -> OfficialView | None:
    return OfficialView(status=status, source=source()) if status else None


@given(percentages=PERCENTAGES, share=st.floats(0.0, 1.0), official=OFFICIAL)
def test_p1_the_chance_of_a_cameo(
    percentages: list[int], share: float, official: OfficialStatus | None
) -> None:
    found = combine(_views(percentages), _official(official), share=share)
    if official == "bench":
        assert found.p_cameo == share
    elif official is not None:
        assert found.p_cameo == 0.0
    else:
        assert found.p_cameo == pytest.approx(share * (1 - found.p_start))


@given(percentages=PERCENTAGES, official=OFFICIAL)
def test_p2_equal_shares_change_nothing(percentages: list[int], official: OfficialStatus | None) -> None:
    views, view = _views(percentages), _official(official)
    assert combine(views, view, share=constants.CAMEO_SHARE) == combine(views, view)
