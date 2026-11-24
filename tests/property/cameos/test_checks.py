"""P3 (mvp-cameos design; R2.3): rerating with today's shares gives back each player's chance of a rating,
and a player of one kind doesn't move when only the other kind's share changes."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.recalibration import rerated
from fantadamus.engine.constants import CAMEO_SHARE, CAMEO_SHARE_PRICED
from tests.cameos_rows import row

CHANCE = st.floats(min_value=0.0, max_value=1.0)


@given(
    p_start=CHANCE,
    cameo=CHANCE,
    kind=st.sampled_from([True, False, None]),
    flat=CHANCE,
    priced=CHANCE,
)
def test_p3_rerated_by_kind(
    p_start: float, cameo: float, kind: bool | None, flat: float, priced: float
) -> None:
    rating = p_start + (1 - p_start) * cameo
    player = row(11, 0, 1, role="A" if kind else "D", priced=kind, p_start=p_start, p_rating=rating)
    assert rerated(player, rating, CAMEO_SHARE, CAMEO_SHARE_PRICED) == pytest.approx(rating)
    if kind is True:
        assert rerated(player, rating, flat, CAMEO_SHARE_PRICED) == pytest.approx(rating)
    elif kind is False:
        assert rerated(player, rating, CAMEO_SHARE, priced) == pytest.approx(rating)
    else:  # a row from before the kinds were kept moves with neither
        assert rerated(player, rating, flat, priced) == rating
    assert 0.0 <= rerated(player, rating, flat, priced) <= 1.0
