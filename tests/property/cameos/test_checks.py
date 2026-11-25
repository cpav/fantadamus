"""P3 (mvp-cameos design; R2.3): rerating with the shares a player was scored with gives back his chance of a
rating, it moves with his own kind's share only, and it doesn't depend on the share he was scored with, which
may be older than today's."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.calibration import SetRow
from fantadamus.domains.recalibration import rerated
from fantadamus.engine.constants import CAMEO_RATED
from tests.cameos_rows import row

SHARE = st.floats(min_value=0.01, max_value=1.0)
STARTS = st.floats(min_value=0.0, max_value=0.95)


def _made_with(share: float, p_start: float, goal: float, priced: bool) -> tuple[SetRow, float]:
    """A benched player as the model would store him with this share, and his chance of a rating."""
    once_on = goal + (1 - goal) * CAMEO_RATED if priced else 1.0
    rating = p_start + share * (1 - p_start) * once_on
    player = row(
        11,
        0,
        1,
        role="A" if priced else "D",
        priced=priced,
        p_start=p_start,
        p_rating=rating,
        p_scores_cameo=goal if priced else None,
    )
    return player, rating


@given(
    p_start=STARTS,
    goal=st.floats(min_value=0.0, max_value=1.0),
    priced=st.booleans(),
    made=SHARE,
    other=SHARE,
    new=st.floats(min_value=0.01, max_value=1.5),  # past one, a share is still never past certain
)
def test_p3_rerated_by_kind(
    p_start: float, goal: float, priced: bool, made: float, other: float, new: float
) -> None:
    player, rating = _made_with(made, p_start, goal, priced)
    older, older_rating = _made_with(other, p_start, goal, priced)

    def again(chance: SetRow, was: float, share: float, unused: float) -> float:
        return rerated(chance, was, unused, share) if priced else rerated(chance, was, share, unused)

    assert again(player, rating, made, new) == pytest.approx(rating)  # the same share gives it back
    assert again(player, rating, new, other) == pytest.approx(
        again(player, rating, new, 0.3)
    )  # his kind's only
    assert again(player, rating, new, 0.3) == pytest.approx(again(older, older_rating, new, 0.3))
    assert p_start <= again(player, rating, new, 0.3) <= 1.0


@given(p_start=STARTS, rating=st.floats(min_value=0.0, max_value=1.0), flat=SHARE, priced=SHARE)
def test_p3_nothing_to_rescale(p_start: float, rating: float, flat: float, priced: float) -> None:
    """A player with no chance of coming on stays as he was, and so does a row from before the kinds were kept
    or a forward whose chance of scoring once on isn't known."""
    for kind, scores in ((None, None), (True, None)):
        player = row(11, 0, 1, role="A", priced=kind, p_start=p_start, p_rating=rating, p_scores_cameo=scores)
        assert rerated(player, rating, flat, priced) == rating
    out = row(11, 0, 1, p_start=p_start, p_rating=p_start)
    assert rerated(out, p_start, flat, priced) == p_start
