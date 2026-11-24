"""P4 (mvp-cameos design; R2.2): the priced share fitted on players made with a known share gives that share
back, to within one player's rounding, and its interval holds it."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine.constants import CAMEO_RATED
from fantadamus.engine.recalibrate import cameo_share_priced


@given(
    count=st.integers(min_value=20, max_value=400),
    scoring=st.floats(min_value=0.0, max_value=0.5),
    share=st.floats(min_value=0.05, max_value=0.95),
)
def test_p4_the_share_comes_back(count: int, scoring: float, share: float) -> None:
    once_on = scoring + (1 - scoring) * CAMEO_RATED
    rated = round(share * once_on * count)
    fitted = cameo_share_priced([(scoring, index < rated) for index in range(count)])
    assert fitted is not None
    assert fitted.value == pytest.approx(share, abs=0.5 / (once_on * count) + 1e-12)
    assert fitted.low <= share <= fitted.high
    assert 0.0 <= fitted.low <= fitted.value <= fitted.high <= 1.0
