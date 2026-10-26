"""P7: raising a player's E_start, all else equal, never lowers his rank (design C8; R9.8)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine import forwards
from fantadamus.engine.forwards import Option

probability = st.floats(min_value=0, max_value=1, allow_nan=False)
score = st.floats(min_value=0, max_value=20, allow_nan=False)


@st.composite
def options(draw: st.DrawFn, name: str) -> Option:
    p_start = draw(probability)
    p_cameo = draw(st.floats(min_value=0, max_value=1 - p_start, allow_nan=False))
    return Option(name=name, p_start=p_start, p_cameo=p_cameo, e_start=draw(score), e_cameo=draw(score))


@given(options("A"), options("B"), st.floats(min_value=0, max_value=5, allow_nan=False))
def test_p7_higher_e_start_never_ranks_lower(a: Option, b: Option, raise_by: float) -> None:
    raised = a.model_copy(update={"e_start": a.e_start + raise_by})
    if forwards.verdict(a, b).first == "A":
        assert forwards.verdict(raised, b).first == "A"
