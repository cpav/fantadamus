"""P4 of mvp-sources: a desk's bias lies in its 90% interval, and the three desks' biases for a player sum to
zero, whatever the ratings (design C7; R5.1)."""

from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.raters import desk_bias
from fantadamus.domains.ratings.silver import MatchRatingRow

DESKS = ("Fantacalcio.it", "Roma", "Torino")
AT = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)
_RATING = st.one_of(st.none(), st.integers(8, 20).map(lambda halves: halves / 2))


@st.composite
def _rows(draw: st.DrawFn) -> list[MatchRatingRow]:
    rows = []
    for round in range(1, draw(st.integers(1, 12)) + 1):
        for name in draw(st.lists(st.sampled_from(["UNO A.", "DUE A.", "TRE B."]), min_size=1, unique=True)):
            club = "beta" if name.endswith("B.") else "alfa"
            for desk in DESKS:
                rows.append(
                    MatchRatingRow(
                        source_url="https://example.org/voti",
                        captured_at=AT + dt.timedelta(days=round),
                        content_sha256=f"{round:064d}",
                        round=round,
                        home="alfa",
                        away="beta",
                        club=club,
                        name=name,
                        role="C",
                        came_on=False,
                        minutes=None,
                        desk=desk,
                        rating=draw(_RATING),
                    )
                )
    return rows


@given(_rows())
def test_p4_bias_in_its_interval(rows: list[MatchRatingRow]) -> None:
    found = desk_bias(rows)
    for bias in found:
        assert bias.low - 1e-9 <= bias.bias <= bias.high + 1e-9
        assert bias.matches >= 1
    players = {(bias.club, bias.name) for bias in found}
    for player in players:
        mine = [bias for bias in found if (bias.club, bias.name) == player]
        assert sorted(bias.desk for bias in mine) == sorted(DESKS)
        assert abs(sum(bias.bias for bias in mine)) < 1e-9
