"""P12: a taker's share stays in 0 to 1, the first has all of it, and it never rises down the list (R10.1)."""

from __future__ import annotations

import datetime as dt
from itertools import pairwise

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.facts import Source
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.season.gold import PenaltyOrder, penalty_share

NOW = dt.datetime(2026, 11, 6, 12, tzinfo=dt.UTC)
SOURCE = Source(source_url="https://example.org/takers", captured_at=NOW, content_sha256="a" * 64)
SURNAMES = ("Rossi", "Bianchi", "Verdi", "Neri", "Gialli")


@given(st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=5))
def test_p12_a_share_never_rises_down_the_list(chances: list[float]) -> None:
    mates = [
        KnownPlayer(player_id=number, name=SURNAMES[number], club="alfa") for number in range(len(chances))
    ]
    order = PenaltyOrder(takers=[mate.name for mate in mates], source=SOURCE)
    shares = [penalty_share(mate, order, mates, lambda other: chances[other.player_id]) for mate in mates]
    assert shares[0] == 1.0
    assert all(0.0 <= share <= 1.0 for share in shares)
    assert all(later <= earlier for earlier, later in pairwise(shares))
