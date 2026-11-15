"""mvp-sources task 6.1: Fantacalcio-Online's round ratings page read into each player's base rating from the
three desks, with when he came on or off; "s.v." and an unpublished desk kept apart (design C6; R4.2)."""

from __future__ import annotations

import pytest

from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fco_ratings import read_ratings
from tests.sources_pages import NOT_PUBLISHED, Rated, ratings_page

ALFA = [
    Rated("UNO", "A", "P", ("6,00", "6,50", "6,00")),
    Rated("DUE", "A", "D", ("5,50", NOT_PUBLISHED, "5,00"), off_after=65),
    Rated("SETTE", "A", "C", ("s.v.", "s.v.", "6,00"), came_on=12),
    Rated("DODICI", "A", "C", unused=True),
]
BETA = [Rated("NOVE", "B", "A", ("7,50", "7,00", "7,50"))]


def test_a_round_s_ratings() -> None:
    """Each player who played, with his club, role and each desk's base rating: s.v. is a desk's rating of
    None, an unpublished desk is left out, and a player who never came on isn't listed."""
    facts = read_ratings(ratings_page(11, [("Alfa", "Beta", ALFA, BETA)]), 11)
    assert facts.payload.round == 11
    [match] = facts.payload.matches
    assert (match.home, match.away) == ("Alfa", "Beta")
    assert [
        (
            player.club,
            player.name,
            player.role,
            player.came_on,
            player.minutes,
            [(rated.desk, rated.rating) for rated in player.ratings],
        )
        for player in match.players
    ] == [
        ("Alfa", "UNO A.", "P", False, None, [("Fantacalcio.it", 6.0), ("Roma", 6.5), ("Torino", 6.0)]),
        ("Alfa", "DUE A.", "D", False, 65, [("Fantacalcio.it", 5.5), ("Torino", 5.0)]),
        ("Alfa", "SETTE A.", "C", True, 12, [("Fantacalcio.it", None), ("Roma", None), ("Torino", 6.0)]),
        ("Beta", "NOVE B.", "A", False, None, [("Fantacalcio.it", 7.5), ("Roma", 7.0), ("Torino", 7.5)]),
    ]
    assert facts.problems == []


def test_a_match_not_rated_yet_is_left_out() -> None:
    """A match whose ratings no desk has published yet gives nothing; the others still count."""
    waiting = [Rated("TRE", "C", "D", (NOT_PUBLISHED,) * 3)]
    facts = read_ratings(
        ratings_page(11, [("Alfa", "Beta", ALFA, BETA), ("Gamma", "Delta", waiting, waiting)]), 11
    )
    assert [(match.home, match.away) for match in facts.payload.matches] == [("Alfa", "Beta")]


def test_the_round_from_the_title() -> None:
    """Without a round asked for, the title's; with one, the title must agree."""
    page = ratings_page(11, [("Alfa", "Beta", ALFA, BETA)])
    assert read_ratings(page, None).payload.round == 11
    with pytest.raises(UnreadablePageError, match="round 12"):
        read_ratings(page, 12)


@pytest.mark.parametrize(
    "page",
    [
        "<html><head><title>Probabili formazioni</title></head><body></body></html>",
        ratings_page(11, []),
        ratings_page(11, [("Alfa", "Beta", [Rated("TRE", "C", "D", (NOT_PUBLISHED,) * 3)], [])]),
    ],
)
def test_a_page_without_ratings_is_unreadable(page: str) -> None:
    with pytest.raises(UnreadablePageError):
        read_ratings(page, 11)
