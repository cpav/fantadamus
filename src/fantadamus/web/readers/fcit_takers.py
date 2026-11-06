"""Fantacalcio.it's penalty-takers page read into each club's takers in order (mvp-lineup C13; R10.3).

Each club is a `div.team-card` with a `span.team-name`, and one column per kind of set piece: a
`header.primary` naming it, then a ranked list whose links hold the players' names, written as on the
statistics page. Only the column headed "Rigori" is read. A page with another title, or with no such column at
all, is unreadable rather than misread; a single club without a list is named, and the others still count.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from fantadamus.contracts.xy.season import ClubTakers, PenaltyTakersPayload
from fantadamus.web.html import Element, parse
from fantadamus.web.readers import UnreadablePageError

TITLE = "Rigoristi"
PENALTIES = "Rigori"


@dataclass(frozen=True)
class TakersFacts:
    payload: PenaltyTakersPayload
    problems: list[str]


def _penalties_column(card: Element) -> Element | None:
    for column in card.find_all("div", "col"):
        heading = column.find("header", "primary")
        if heading is not None and heading.text().strip() == PENALTIES:
            return column
    return None


def read_takers(html: str) -> TakersFacts:
    """Each club's takers, or `UnreadablePageError` if the page isn't the one the reader knows."""
    tree = parse(html)
    title = tree.find("title")
    if title is None or TITLE not in title.text():
        raise UnreadablePageError("the page's title isn't the penalty takers'")
    cards = tree.find_all("div", "team-card")
    columns = [(card, _penalties_column(card)) for card in cards]
    if not any(column is not None for _, column in columns):
        raise UnreadablePageError("the page has no club with a penalties column")
    clubs: list[ClubTakers] = []
    problems: list[str] = []
    for card, column in columns:
        heading = card.find(class_="team-name")
        name = heading.text().strip() if heading is not None else "A club"
        takers = [link.text().strip() for link in column.find_all("a", "player-name")] if column else []
        if not takers:
            problems.append(f"{name}: no penalty takers listed")
            continue
        try:
            clubs.append(ClubTakers(club=name, takers=takers))
        except ValidationError as error:
            problems.append(f"{name}: {error.errors()[0]['msg']}")
    try:
        return TakersFacts(PenaltyTakersPayload(clubs=clubs), problems)
    except ValidationError as error:
        raise UnreadablePageError(f"the clubs don't hold together: {error.errors()[0]['msg']}") from error
