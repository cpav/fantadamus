"""P8: a squad resolves to the same players whatever order the names arrive in, and to none if any name fails
(design C3; R1.2)."""

from __future__ import annotations

import random

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.league.squads import match_squad
from tests.collect_pages import squad
from tests.xy_harness import CLUBS

KNOWN = [
    KnownPlayer(player_id=100 * club_index + number, name=name, club=club.lower())
    for club_index, club in enumerate(("Alfa", "Beta"), start=1)
    for number, name in enumerate(squad(club))
]
_NAMES = [player.name for player in KNOWN]
_GOOD = st.lists(st.sampled_from(_NAMES), min_size=1, max_size=len(_NAMES), unique=True)
_BAD = st.sampled_from(("Nessuno Mai", "Beta Uno (Alfa)", "Alfa Uno (Lontano)"))


@given(names=_GOOD, order=st.randoms(use_true_random=False))
def test_p8_any_order_gives_the_same_players(names: list[str], order: random.Random) -> None:
    shuffled = order.sample(names, len(names))
    first, second = match_squad(names, KNOWN, CLUBS), match_squad(shuffled, KNOWN, CLUBS)
    assert first.unresolved == {}
    assert first.players == second.players
    assert sorted(player.name for player in first.players) == sorted(names)


@given(names=_GOOD, bad=_BAD, at=st.integers(min_value=0, max_value=30))
def test_p8_any_name_that_fails_stores_nobody(names: list[str], bad: str, at: int) -> None:
    mixed = [*names[: at % (len(names) + 1)], bad, *names[at % (len(names) + 1) :]]
    match = match_squad(mixed, KNOWN, CLUBS)
    assert match.players == []
    assert set(match.unresolved) == {bad}
