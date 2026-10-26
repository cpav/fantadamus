"""P5: name resolution doesn't depend on the order players were learned (design C4; R1.2)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.players.resolve import KnownPlayer, resolve

WORDS = ["Rossi", "rossi", "Rossì", "Marco", "M.", "L.", "Luca", "Verdi", "De", "Ketelaere"]
names = st.lists(st.sampled_from(WORDS), min_size=1, max_size=3).map(" ".join)


@st.composite
def squads(draw: st.DrawFn) -> list[KnownPlayer]:
    named = draw(st.lists(names, max_size=8))
    return [KnownPlayer(player_id=index + 1, name=name, club="alfa") for index, name in enumerate(named)]


@given(squads().flatmap(lambda players: st.tuples(st.just(players), st.permutations(players))), names)
def test_p5_resolution_ignores_learning_order(
    orders: tuple[list[KnownPlayer], list[KnownPlayer]], name: str
) -> None:
    learned, shuffled = orders
    assert resolve(name, learned) == resolve(name, shuffled)
