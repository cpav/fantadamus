"""P3 (mvp-fixes design; R3): for any player's facts, with any of them present or missing,
`PlayerFacts.sources()` holds the source of every fact present, and nothing else."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from tests.fixes_facts import facts, page_names, rested


@given(
    st.booleans(),
    st.integers(min_value=0, max_value=4),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
)
def test_p3_every_fact_present_has_its_source(
    match: bool, outlets: int, official: bool, odds: bool, news: bool, rest: bool
) -> None:
    side = facts(match=match, outlets=outlets, official=official, odds=odds, news=news)
    expected = {"statistics", "table", "takers"}
    if match:
        expected |= {"round", *(f"outlet-{index}" for index in range(outlets))} | (
            {"official"} if official else set()
        )
    expected |= (
        ({"odds"} if odds else set()) | ({"injuries"} if news else set()) | ({"cup"} if rest else set())
    )
    assert page_names(side.sources(rested() if rest else None)) == expected
