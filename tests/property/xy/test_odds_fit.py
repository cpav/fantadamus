"""P6: the fitted team xG reproduces a consistent market's de-margined 1X2, and its over/under when the page
shows it, within 0.01 (design C7; R5.1, R5.2)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine import odds

rates = st.floats(min_value=0.3, max_value=3.5, allow_nan=False)


@given(rates, rates, st.booleans(), st.booleans())
def test_p6_fit_reproduces_market(home: float, away: float, with_over: bool, with_btts: bool) -> None:
    market = odds.model(home, away)
    shown = {"p_over": market.p_over if with_over else None, "p_btts": market.p_btts if with_btts else None}
    market = market.model_copy(update=shown)
    refitted = odds.model(*odds.fit(market))
    for field in ("p_home", "p_draw", "p_away") + (("p_over",) if with_over else ()):
        assert abs(getattr(refitted, field) - getattr(market, field)) <= 0.01, field
