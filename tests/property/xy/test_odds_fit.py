"""P6: the fitted team xG reproduces a consistent market's de-margined 1X2 and over/under within 0.01
(design C7; R5.2)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine import odds

rates = st.floats(min_value=0.3, max_value=3.5, allow_nan=False)


@given(rates, rates, st.booleans())
def test_p6_fit_reproduces_market(home: float, away: float, with_btts: bool) -> None:
    market = odds.model(home, away)
    if not with_btts:
        market = market.model_copy(update={"p_btts": None})
    refitted = odds.model(*odds.fit(market))
    for field in ("p_home", "p_draw", "p_away", "p_over"):
        assert abs(getattr(refitted, field) - getattr(market, field)) <= 0.01, field
