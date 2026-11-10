"""P2 of mvp-cards: a likely eleven has eleven players and one keeper, all of his club, and once the official
lineup is stored it's the official eleven (design C3; R3.1, R3.4)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.contracts.types import Role
from fantadamus.domains.cards import lineups
from tests.cards_data import KICKOFF, listed

PERCENT = st.integers(min_value=0, max_value=100)
ROLES: list[Role] = ["P", "P", "D", "D", "D", "D", "D", "C", "C", "C", "C", "A", "A", "A", "A"]


@given(st.lists(st.tuples(PERCENT, PERCENT, PERCENT, PERCENT), min_size=len(ROLES), max_size=len(ROLES)))
def test_p2_eleven_and_one_keeper(percents: list[tuple[int, int, int, int]]) -> None:
    squad = [
        listed(f"Alfa {index}", role, views)
        for index, (role, views) in enumerate(zip(ROLES, percents, strict=True))
    ]
    rival = listed("Beta 1", "A", (100, 100, 100, 100), club="beta")
    found = lineups("alfa", [*squad, rival], KICKOFF)
    assert len(found.eleven) == 11
    assert [player.role for player in found.eleven].count("P") == 1
    assert {player.player_id for player in found.eleven} <= {part.player.player_id for part in squad}


@given(st.permutations(range(len(ROLES))))
def test_p2_the_official_eleven(order: list[int]) -> None:
    """Any eleven on the sheet, one of them a keeper, is the card's eleven, whatever the outlets said."""
    keeper, *outfield = [index for index in order if ROLES[index] == "P"][:1] + [
        index for index in order if ROLES[index] != "P"
    ][:10]
    picked = {keeper, *outfield}
    squad = [
        listed(f"Alfa {index}", role, (50, 50, 50, 50), official="starter" if index in picked else "bench")
        for index, role in enumerate(ROLES)
    ]
    found = lineups("alfa", squad, KICKOFF)
    assert {player.name for player in found.eleven} == {f"Alfa {index}" for index in picked}
