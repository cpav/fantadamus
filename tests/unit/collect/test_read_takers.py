"""mvp-lineup task 12.2: Fantacalcio.it's penalty-takers page read into each club's takers (R10.3)."""

from __future__ import annotations

import pytest

from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fcit_takers import read_takers
from tests.collect_pages import takers_page

PAGE = takers_page({"Alfa": ["Alfa Nove", "Alfa Dieci"], "Beta": ["Beta Nove"]})


def test_each_club_in_order() -> None:
    """The penalties' list, not the free kicks' beside it."""
    facts = read_takers(PAGE)
    assert [(club.club, club.takers) for club in facts.payload.clubs] == [
        ("Alfa", ["Alfa Nove", "Alfa Dieci"]),
        ("Beta", ["Beta Nove"]),
    ]
    assert facts.problems == []


def test_a_club_without_a_list_is_named() -> None:
    facts = read_takers(takers_page({"Alfa": ["Alfa Nove"], "Beta": []}))
    assert [club.club for club in facts.payload.clubs] == ["Alfa"]
    assert facts.problems == ["Beta: no penalty takers listed"]


@pytest.mark.parametrize(
    "page",
    [
        takers_page({"Alfa": ["Alfa Nove"]}, title="Probabili formazioni"),
        takers_page({"Alfa": ["Alfa Nove"]}, heading="Rigoristi"),
        "<html><head><title>Rigoristi e tiratori da fermo Serie A</title></head><body></body></html>",
    ],
)
def test_a_changed_layout_is_unreadable(page: str) -> None:
    with pytest.raises(UnreadablePageError):
        read_takers(page)
