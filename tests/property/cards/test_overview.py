"""P5 of mvp-cards, for the overview: its lines are in kickoff order whatever order the fixtures were stored
in (design C6; R5.1)."""

from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.cards import round_lines
from fantadamus.domains.fixtures.silver import FixtureRow
from tests.cards_data import KICKOFF, source

CLUBS = ["alfa", "beta", "gamma", "delta", "epsilon", "zeta"]


def _fixture(home: str, away: str, hours: int) -> FixtureRow:
    return FixtureRow(
        **source().model_dump(),
        round=12,
        home=home,
        away=away,
        kickoff_at=KICKOFF + dt.timedelta(hours=hours),
    )


@given(st.lists(st.integers(min_value=0, max_value=72), min_size=3, max_size=3), st.permutations(range(3)))
def test_p5_in_kickoff_order(hours: list[int], order: list[int]) -> None:
    fixtures = [_fixture(CLUBS[2 * index], CLUBS[2 * index + 1], hour) for index, hour in enumerate(hours)]
    names = {club: club.title() for club in CLUBS}
    lines = round_lines([(fixtures[index], None) for index in order], names)
    assert [line.kickoff for line in lines] == sorted(line.kickoff for line in lines)
    assert lines == round_lines([(row, None) for row in fixtures], names)
