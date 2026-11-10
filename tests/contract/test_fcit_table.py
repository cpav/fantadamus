"""mvp-cards task 1.1: Fantacalcio.it's table read into each club's record, goals and last five results, the
form from its dots, oldest first (design C1; R2.4)."""

from __future__ import annotations

import pytest

from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fcit_table import read_table
from tests.collect_pages import TABLE_COLUMNS, TableClub, table_page

CLUBS = [
    TableClub("Alfa", won=6, drawn=2, lost=1, goals_for=17, goals_against=8, form="WWDLW"),
    TableClub("Beta", won=1, drawn=0, lost=1, goals_for=2, goals_against=3, form="WL"),
]


@pytest.mark.parametrize("reversed_dots", [False, True])
def test_the_record_and_the_form(reversed_dots: bool) -> None:
    """Each club's record and goals from its cells, and its form from the dots in the order they're numbered,
    however the page writes them. Early in a season a club has fewer than five results."""
    facts = read_table(table_page(CLUBS, reversed_dots=reversed_dots))
    assert [row.model_dump() for row in facts.payload.teams] == [
        {
            "club": "Alfa",
            "played": 9,
            "goals_for": 17,
            "goals_against": 8,
            "wins": 6,
            "draws": 2,
            "losses": 1,
            "form": ["W", "W", "D", "L", "W"],
        },
        {
            "club": "Beta",
            "played": 2,
            "goals_for": 2,
            "goals_against": 3,
            "wins": 1,
            "draws": 0,
            "losses": 1,
            "form": ["W", "L"],
        },
    ]
    assert facts.problems == []


def test_a_club_that_doesnt_add_up_is_named() -> None:
    """A club whose form holds a win its record doesn't is left out and named; the others still count."""
    clubs = [*CLUBS, TableClub("Gamma", won=0, drawn=1, lost=1, goals_for=1, goals_against=2, form="WD")]
    facts = read_table(table_page(clubs))
    assert [row.club for row in facts.payload.teams] == ["Alfa", "Beta"]
    assert len(facts.problems) == 1
    assert facts.problems[0].startswith("Gamma: ")


def _renamed(key: str, short: str) -> tuple[tuple[str, str], ...]:
    return tuple((column, short if column == key else name) for column, name in TABLE_COLUMNS)


@pytest.mark.parametrize(
    "page",
    [
        table_page(CLUBS, title="Probabili formazioni Serie A"),
        table_page(CLUBS, columns=_renamed("won", "Pt")),  # the wins' column now headed as points
        table_page(CLUBS, columns=_renamed("drawn", "S")),  # draws and losses swapped
        table_page(CLUBS, columns=tuple(column for column in TABLE_COLUMNS if column[0] != "form")),
        "<html><head><title>Calendario, classifica e marcatori di Serie A</title></head><body></body></html>",
    ],
)
def test_a_page_whose_columns_changed_is_unreadable(page: str) -> None:
    with pytest.raises(UnreadablePageError):
        read_table(page)
