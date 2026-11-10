"""Fantacalcio.it's table read into each club's record, goals and last results (mvp-cards design C1; R2.4).

The page (`/serie-a/classifica`, titled "Calendario, classifica e marcatori") holds several
`table.serie-a-table`; the table is the one whose header has each column below, as its class and its heading.
A club's row has a `td` per column, its name in `a.team-name`, and its form as dots: a `span.value` per result
with the letter in `data-value` and its place, oldest first, in `data-count`. The text Claude reads through
`read_page` shows the record but not the dots, which is why Fantadamus reads this page itself. A page with
another title, or without those columns headed as they are, is unreadable rather than misread; a single club
that doesn't hold together is named, and the others still count.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from fantadamus.contracts.xy.season import TeamRow, TeamSeasonPayload
from fantadamus.web.html import Element, parse
from fantadamus.web.readers import UnreadablePageError

TITLE = "classifica"
COLUMNS = {
    "played": ("G", "played"),
    "won": ("V", "wins"),
    "drawn": ("P", "draws"),
    "lost": ("S", "losses"),
    "goalsscored": ("Gf", "goals_for"),
    "goalsconceded": ("Gs", "goals_against"),
}
"""Each column's class, then its heading and the field it fills."""
FORM = ("form", "Forma")


@dataclass(frozen=True)
class TableFacts:
    payload: TeamSeasonPayload
    problems: list[str]


def _headed(table: Element) -> bool:
    """Whether the table's header has every column, each under its own heading."""
    head = table.find("thead")
    if head is None:
        return False
    for name, heading in [*((key, short) for key, (short, _) in COLUMNS.items()), FORM]:
        cell = head.find("th", name)
        if cell is None or cell.text().strip() != heading:
            return False
    return True


def _form(cell: Element) -> list[str]:
    dots = [
        (int(dot.attr("data-count") or 0), dot.attr("data-value") or "")
        for dot in cell.find_all("span", "value")
    ]
    return [result for _, result in sorted(dots)]


def _club(row: Element) -> TeamRow:
    figures: dict[str, object] = {}
    for name, (_, field) in COLUMNS.items():
        cell = row.find("td", name)
        text = cell.text().strip() if cell is not None else ""
        if not text.isdigit():
            raise ValueError(f"its {name} cell isn't a count")
        figures[field] = int(text)
    form = row.find("td", FORM[0])
    link = row.find("a", "team-name")
    return TeamRow.model_validate(
        {
            "club": link.text().strip() if link is not None else "",
            **figures,
            "form": _form(form) if form is not None else None,
        }
    )


def read_table(html: str) -> TableFacts:
    """Each club's row, or `UnreadablePageError` if the page isn't the one the reader knows."""
    tree = parse(html)
    title = tree.find("title")
    if title is None or TITLE not in title.text().lower():
        raise UnreadablePageError("the page's title isn't the table's")
    table = next((table for table in tree.find_all("table", "serie-a-table") if _headed(table)), None)
    if table is None:
        raise UnreadablePageError("the page has no table with the record, the goals and the form")
    body = table.find("tbody")
    rows = [row for row in body.find_all("tr") if row.find("td", "played") is not None] if body else []
    clubs: list[TeamRow] = []
    problems: list[str] = []
    for row in rows:
        link = row.find("a", "team-name")
        name = link.text().strip() if link is not None else "A club"
        try:
            clubs.append(_club(row))
        except ValidationError as error:
            problems.append(f"{name}: {error.errors()[0]['msg']}")
        except ValueError as error:
            problems.append(f"{name}: {error}")
    try:
        return TableFacts(TeamSeasonPayload(teams=clubs), problems)
    except ValidationError as error:
        raise UnreadablePageError(f"the clubs don't hold together: {error.errors()[0]['msg']}") from error
