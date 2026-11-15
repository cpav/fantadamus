"""Fantacalcio-Online's round ratings page read into each player's base rating from three desks (mvp-sources
design C6; R4.2; ADR-0007).

The page (`/voti/{n}-giornata`, titled "Voti Fantacalcio Serie A ... - nª Giornata") holds a `div.tab-pane`
per match: its header names both clubs in `a.prb-incontro__nome`, home first; then a `section.prb-squadra` per
club, named in `h2.prb-squadra__nome`, with a `table.prb-tabella` of those who started and one of the bench.
Each table heads a column per desk (`th.prb-tabella__fonte`, its desk in `title`). A player's row gives his
role (`span.role`), his name in `span.prb-nome` with his initial in `<small>`, how he played (`span.prb-
segno`: "Entrato dalla panchina, 25 minuti giocati", "Sostituito dopo 65 minuti"), and a cell per desk: a
rating such as "6,50", "s.v." (seen, no rating), or a dash when the desk hasn't published. A player who never
came on isn't listed, nor is a match no desk has rated yet."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import ValidationError

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.ratings import Desk, DeskRating, MatchRatings, PlayerRatings, RatingsPayload
from fantadamus.web.html import Element, parse
from fantadamus.web.readers import UnreadablePageError

_DESKS: dict[str, Desk] = {"Fantacalcio.it": "Fantacalcio.it", "Roma": "Roma", "Torino": "Torino"}
_ROLES: dict[str, Role] = {"P": "P", "D": "D", "C": "C", "A": "A"}
_TITLE = re.compile(r"Voti .*?(\d+)\s*ª\s*Giornata", re.IGNORECASE)
_RATING = re.compile(r"(\d{1,2}),(\d{1,2})")
_CAME_ON = re.compile(r"Entrato dalla panchina\D*(\d+) minuti")
_TAKEN_OFF = re.compile(r"Sostituito dopo (\d+) minuti")
UNRATED = "s.v."


@dataclass(frozen=True)
class RatingsFacts:
    payload: RatingsPayload
    problems: list[str]


def _name(row: Element) -> str | None:
    """His name as the page writes it, his initial after his surname: "DE GEA D."."""
    shown = row.find("span", "prb-nome")
    if shown is None:
        return None
    small = shown.find("small")
    initial = small.text().strip() if small is not None else ""
    whole = shown.text().strip()
    surname = whole[: len(whole) - len(initial)].strip() if initial and whole.endswith(initial) else whole
    return f"{surname} {initial}." if initial and surname else surname or None


def _player(row: Element, club: str, desks: list[Desk | None]) -> PlayerRatings | None:
    """His ratings, or None for a row that isn't a player's, or a player no desk has rated."""
    role = row.find("span", "role")
    name = _name(row)
    known = _ROLES.get(role.text().strip().upper()) if role is not None else None
    if known is None or name is None or row.has_class("prb-riga--non-entrato"):
        return None
    mark = row.find("span", "prb-segno")
    said = (mark.attr("title") or "") if mark is not None else ""
    came_on, taken_off = _CAME_ON.search(said), _TAKEN_OFF.search(said)
    ratings = []
    for desk, cell in zip(desks, row.find_all("td"), strict=False):
        shown = cell.text().strip()
        found = _RATING.fullmatch(shown)
        if desk is not None and (found is not None or shown == UNRATED):
            ratings.append(DeskRating(desk=desk, rating=float(f"{found[1]}.{found[2]}") if found else None))
    if not ratings:
        return None
    played = came_on or taken_off
    return PlayerRatings(
        club=club,
        name=name,
        role=known,
        came_on=came_on is not None,
        minutes=int(played[1]) if played else None,
        ratings=ratings,
    )


def _match(pane: Element) -> MatchRatings | None:
    """The match's players with their ratings; None when no desk has rated it yet."""
    named = [link.text().strip() for link in pane.find_all("a", "prb-incontro__nome")]
    if len(named) != 2:
        return None
    players = []
    for section in pane.find_all("section", "prb-squadra"):
        heading = section.find("h2", "prb-squadra__nome")
        club = heading.text().strip() if heading is not None else ""
        for table in section.find_all("table", "prb-tabella"):
            desks = [
                _DESKS.get(cell.attr("title") or "") for cell in table.find_all("th", "prb-tabella__fonte")
            ]
            for row in table.find_all("tr"):
                if (player := _player(row, club, desks)) is not None:
                    players.append(player)
    return MatchRatings(home=named[0], away=named[1], players=players) if players else None


def read_ratings(html: str, round: int | None) -> RatingsFacts:
    """Round `round`'s ratings, or the round the title names; `UnreadablePageError` if the page isn't the one
    the reader knows, names another round, or holds no rating yet."""
    tree = parse(html)
    title = tree.find("title")
    named = _TITLE.search(title.text()) if title is not None else None
    if named is None:
        raise UnreadablePageError("the page's title isn't a round's ratings")
    if round is not None and int(named[1]) != round:
        raise UnreadablePageError(f"the page is round {named[1]}'s, not round {round}'s")
    matches: list[MatchRatings] = []
    problems: list[str] = []
    for pane in tree.find_all("div", "tab-pane"):
        try:
            if (match := _match(pane)) is not None:
                matches.append(match)
        except ValidationError as error:
            problems.append(f"A match: {error.errors()[0]['msg']}")
    if not matches:
        raise UnreadablePageError("no match on the page has a rating yet")
    try:
        return RatingsFacts(RatingsPayload(round=int(named[1]), matches=matches), problems)
    except ValidationError as error:
        raise UnreadablePageError(f"the matches don't hold together: {error.errors()[0]['msg']}") from None
