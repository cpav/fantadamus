"""mvp-sources task 7.1: the raters' claims at their edges, a player's claims found by name, and each round's
newest read only (design C7; R5.1, R5.2)."""

from __future__ import annotations

import datetime as dt

from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.raters import Bias, claim, claims_for, desk_bias
from fantadamus.domains.ratings.silver import MatchRatingRow

AT = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)


def _bias(value: float, matches: int = 5, desk: str = "Roma") -> Bias:
    return Bias(
        club="alfa", name="NOVE A.", desk=desk, bias=value, matches=matches, low=value - 0.1, high=value + 0.1
    )


def test_a_claim_at_its_edges() -> None:
    """From 0.25 of a rating point, either way, over 5 matches or more (both start values)."""
    assert claim(_bias(0.25)) == "Roma rates him 0.25 above the other desks, over 5 matches."
    assert claim(_bias(-0.3, 9, "Torino")) == "Torino rates him 0.30 below the other desks, over 9 matches."
    assert claim(_bias(0.249)) is None
    assert claim(_bias(0.5, 4)) is None


def test_a_player_s_claims() -> None:
    """His claims, found by his name as the outlets' are; another club's player of that name isn't him."""
    mates = [KnownPlayer(player_id=1, name="Alfa Nove", club="alfa")]
    biases = [_bias(0.4, desk="Fantacalcio.it"), _bias(0.1), _bias(0.4).model_copy(update={"club": "beta"})]
    assert claims_for(mates[0], biases, mates) == [
        "Fantacalcio.it rates him 0.40 above the other desks, over 5 matches."
    ]
    assert claims_for(KnownPlayer(player_id=2, name="Alfa Dieci", club="alfa"), biases, mates) == []


def _row(round: int, desk: str, rating: float, at: dt.datetime) -> MatchRatingRow:
    return MatchRatingRow(
        source_url="https://example.org/voti",
        captured_at=at,
        content_sha256=f"{at.hour:064d}",
        round=round,
        home="alfa",
        away="beta",
        club="alfa",
        name="NOVE A.",
        role="A",
        came_on=False,
        minutes=None,
        desk=desk,
        rating=rating,
    )


def test_each_round_s_newest_read() -> None:
    """A round read twice counts once, from its newest read: a desk that published later is in it."""
    early, late = AT, AT + dt.timedelta(hours=10)
    rows = [
        _row(1, "Fantacalcio.it", 7.0, early),
        _row(1, "Fantacalcio.it", 7.0, late),
        _row(1, "Roma", 6.0, late),
        _row(1, "Torino", 6.0, late),
    ]
    [league] = [bias for bias in desk_bias(rows) if bias.desk == "Fantacalcio.it"]
    assert (league.matches, league.bias) == (1, 1.0)
