"""Fantacalcio.it's injured page and its suspended-and-diffidati page read into facts (mvp-sources design C4;
R3.1; ADR-0007).

Both pages hold a `div.team-card` per club, its name in `span.team-name`. On the injured page (titled
"Infortunati Serie A") each player is an `li` with his name in `strong.item-name` and a sentence in
`div.item-description`, which the rules in `injury_rules` turn into a kind, a body part and a return window.
On the suspended page (titled "Squalificati e diffidati Serie A") a club's card has a column headed
"Squalificati", each banned player with a sentence naming the round he misses, and one headed "Diffidati",
those one booking from a ban; an empty column says "Nessuno". The sentences aren't kept (ADR-0005, guardrail
4). A page with another title, or without a club card, is unreadable rather than misread; a club that doesn't
hold together is named, and the others still count.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from pydantic import ValidationError

from fantadamus.contracts.xy.unavailable import (
    Banned,
    ClubBans,
    ClubInjuries,
    InjuriesPayload,
    Injury,
    SuspensionsPayload,
)
from fantadamus.web.html import Element, parse
from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.injury_rules import back_of, banned_rounds, body_part_of, kind_of

INJURED_TITLE = "infortunati"
SUSPENDED_TITLE = "squalificati"


@dataclass(frozen=True)
class InjuriesFacts:
    payload: InjuriesPayload
    problems: list[str]


@dataclass(frozen=True)
class SuspensionsFacts:
    payload: SuspensionsPayload
    problems: list[str]


def _cards(html: str, title: str, page: str) -> list[tuple[str, Element]]:
    """Each club's name and card, or `UnreadablePageError` when the page isn't the one the reader knows."""
    tree = parse(html)
    heading = tree.find("title")
    if heading is None or title not in heading.text().lower():
        raise UnreadablePageError(f"the page's title isn't the {page} page's")
    cards = tree.find_all("div", "team-card")
    if not cards:
        raise UnreadablePageError(f"the {page} page has no club card")
    found = []
    for card in cards:
        name = card.find(class_="team-name")
        found.append((name.text().strip() if name is not None else "", card))
    return found


def _entries(column: Element) -> list[tuple[str, str]]:
    """Each player in a list: his name, and the sentence beside it."""
    found = []
    for item in column.find_all("li"):
        name = item.find(class_="item-name")
        sentence = item.find(class_="item-description")
        if name is not None and name.text().strip():
            found.append((name.text().strip(), " ".join(sentence.text().split()) if sentence else ""))
    return found


def read_injuries(html: str, today: dt.date) -> InjuriesFacts:
    """Each club's injured players, their sentences read as of `today`, the read's date in Italy."""
    clubs: list[ClubInjuries] = []
    problems: list[str] = []
    for club, card in _cards(html, INJURED_TITLE, "injured"):
        try:
            players = [
                Injury(
                    name=name,
                    kind=kind_of(sentence),
                    body_part=body_part_of(sentence),
                    **vars(back_of(sentence, today)),
                )
                for name, sentence in _entries(card)
            ]
            clubs.append(ClubInjuries(club=club, players=players))
        except ValidationError as error:
            problems.append(f"{club or 'A club'}: {error.errors()[0]['msg']}")
    try:
        return InjuriesFacts(InjuriesPayload(clubs=clubs), problems)
    except ValidationError as error:
        raise UnreadablePageError(f"the clubs don't hold together: {error.errors()[0]['msg']}") from None


def read_suspensions(html: str) -> SuspensionsFacts:
    """Each club's banned players, with the rounds they miss, and those one booking from a ban."""
    clubs: list[ClubBans] = []
    problems: list[str] = []
    for club, card in _cards(html, SUSPENDED_TITLE, "suspended"):
        listed: dict[str, list[tuple[str, str]]] = {"squalificat": [], "diffidat": []}
        for column in card.find_all("div", "col"):
            label = column.find(class_="label")
            heading = label.text().strip().lower() if label is not None else ""
            for start in listed:
                if heading.startswith(start):
                    listed[start] += _entries(column)
        try:
            banned = [Banned(name=name, rounds=banned_rounds(why)) for name, why in listed["squalificat"]]
            warned = [name for name, _ in listed["diffidat"]]
            clubs.append(ClubBans(club=club, banned=banned, one_booking=warned))
        except ValidationError as error:
            problems.append(f"{club or 'A club'}: {error.errors()[0]['msg']}")
    try:
        return SuspensionsFacts(SuspensionsPayload(clubs=clubs), problems)
    except ValidationError as error:
        raise UnreadablePageError(f"the clubs don't hold together: {error.errors()[0]['msg']}") from None
