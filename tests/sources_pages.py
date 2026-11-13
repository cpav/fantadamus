"""Invented pages in the real layouts, for the `mvp-sources` tests: Wikipedia's raw wikitext of a competition,
with each match in a `Football box` template. Clubs and players are invented; real pages can't be committed
to a public repository (design, testing strategy)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
UEFA_PROSE = (
    "Times are {{abbr|CET|Central European Time}}/{{abbr|CEST|Central European Summer Time}},"
    "{{efn|[[Central European Summer Time|CEST]] ([[UTC+02:00|UTC+2]]) for dates up to 24 October 2026, "
    "and [[Central European Time|CET]] ([[UTC+01:00|UTC+1]]) for dates thereafter.}} as listed by UEFA "
    "(local times, if different, are in parentheses).\n"
)
CUP_PROSE = (
    "Times up to 24 October 2026 and from 28 March 2027 are [[Central European Summer Time|CEST]] "
    "([[UTC+02:00|UTC+2]]). Times from 25 October 2026 to 27 March 2027 are [[Central European Time|CET]] "
    "([[UTC+01:00|UTC+1]]).\n"
)


@dataclass(frozen=True)
class Box:
    """One match as the page writes it: a side is a club's link, or any text (a placeholder, two clubs)."""

    team1: str
    team2: str
    date: str
    time: str
    score: str = ""


def link(name: str, target: str | None = None) -> str:
    """A club's link, `[[Target|Name]]` or `[[Name]]`."""
    return f"[[{target}|{name}]]" if target else f"[[{name}]]"


def start_date(day: dt.date) -> str:
    return f"{{{{Start date|{day.year}|{day.month}|{day.day}|df=y}}}}"


def plain_date(day: dt.date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def uefa_box(box: Box) -> str:
    """A league-phase match: the home side's flag after its name, the away side's before."""
    return (
        "{{#invoke:Football box|main\n"
        f"|date       = {box.date}\n"
        f"|time       = {box.time}\n"
        f"|team1      = {box.team1} {{{{fbaicon|ITA}}}}\n"
        f"|score      = {box.score}\n"
        f"|team2      = {{{{fbaicon|AUT}}}} {box.team2}\n"
        "|goals1     =\n"
        "*[[Anna Bianchi|Bianchi]] {{goal|21}}\n"
        "|goals2     =\n"
        "|stadium    = [[Stadio Invented]], [[Nowhere]]\n"
        "|attendance = 30,221<ref>{{cite web |url=https://example.org/report.pdf "
        "|title=Full Time Summary \u2013 A v B |publisher=Example |date=8 September 2026 "
        "|access-date=8 September 2026}}</ref>\n"
        "|referee    = [[Carlo Rossi]] ([[Invented Football Federation|Nowhere]])\n"
        "|report     = Report<ref>{{cite web |url=https://example.org/match/1/ |title=A vs. B}}</ref>\n"
        "}}\n----\n"
    )


def cup_box(box: Box, *, collapsible: bool = True) -> str:
    """A Coppa Italia match: a plain date, the zone after the time, the winner in bold, each side's tier."""
    head = "{{Football box collapsible\n|id = A v B\n" if collapsible else "{{Football box\n"
    return (
        f"{head}"
        f"|date = {box.date}\n"
        f"|time = {box.time}\n"
        f"|team1 = {box.team1}\n"
        f"|score = {box.score}\n"
        "|report = https://example.org/coppa-italia/match/abc/a-vs-b\n"
        f"|team2 = {box.team2}\n"
        "|goals1 =\n*[[Gabriele Verdi|Verdi]] {{goal|25}}\n"
        "|goals2 =\n*[[Marco Neri|Neri]] {{goal|39|pen.}}\n"
        "|stadium = [[Stadio Inventato]], [[Nessuno]]\n"
        "|attendance = 9,000\n"
        "|referee = [[Luca Gialli]]\n"
        "}}\n"
    )


def wiki_page(boxes: Sequence[str], prose: str = UEFA_PROSE) -> str:
    """A competition's raw wikitext: its lead, its prose on times, then its matchdays."""
    return (
        "{{Short description|An invented competition}}\n"
        "{{Infobox football tournament season\n| year = 2026\u201327\n| teams = 36\n}}\n"
        "The '''2026\u201327 league phase''' is invented for tests."
        "<ref>{{cite web |url=https://example.org/ |title=X}}</ref>\n\n"
        f"==Matches==\n{prose}\n===Matchday 1===\n" + "".join(boxes) + "\n==References==\n{{Reflist}}\n"
    )
