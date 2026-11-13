"""Wikipedia's page of a competition read into its matches (mvp-sources design C2; R2.1; ADR-0007).

The page is read as raw wikitext at `/wiki/{title}?action=raw`. Each match is a `Football box` template:
`{{#invoke:Football box|main …}}` on the UEFA league-phase pages, `{{Football box collapsible …}}` or
`{{Football box …}}` on the Coppa Italia's. Its `date` is a `{{Start date|Y|M|D}}` or plain text ("8 August
2026"); its `time` starts with the kickoff in Italian time, as both pages' prose says (CET or CEST), a local
time after it in brackets where different; `team1` and `team2` each hold a club's link, with a flag, its tier
or bold around it. A match without a fixed date (a range of days, "TBD"), a kickoff or both clubs ("Winner of
Match 37", two clubs before a draw) isn't a match yet: it's left out and counted. The page's text isn't kept:
only each match's date, kickoff and clubs (ADR-0005, guardrail 4).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from fantadamus.contracts.xy.fixtures import Competition, Fixture, OtherFixturesPayload
from fantadamus.web.readers import UnreadablePageError

ROME = ZoneInfo("Europe/Rome")
TITLES: dict[str, Competition] = {
    "UEFA_Champions_League": "Champions League",
    "UEFA_Europa_League": "Europa League",
    "UEFA_Conference_League": "Conference League",
    "Coppa_Italia": "Coppa Italia",
}
"""What a page's title names, for each competition: its league phase's page, or a knockout round's."""
MONTHS = {
    name: number
    for number, name in enumerate(
        (
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
        ),
        start=1,
    )
}
_HIDDEN = re.compile(r"<!--.*?-->|<ref[^>]*?/>|<ref(?:\s[^>]*)?>.*?</ref>", re.S | re.I)
"""Comments and references: never a match's fact, and their text may hold anything."""
_BOX = re.compile(
    r"\{\{\s*(?:#invoke:\s*[Ff]ootball box\s*\|\s*main|[Ff]ootball box(?: collapsible)?)\s*(?=[|}])"
)
_START_DATE = re.compile(r"\{\{\s*[Ss]tart date\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})\s*[|}]")
_PLAIN_DATE = re.compile(r"(\d{1,2}) ([A-Z][a-z]+) (\d{4})")
_TIME = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")
_BRACES = re.compile(r"\{\{|\}\}")
_MARKS = re.compile(r"\{\{|\}\}|\[\[|\]\]|\|")
_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_LINK = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]")


@dataclass(frozen=True)
class OtherFixturesFacts:
    payload: OtherFixturesPayload
    problems: list[str]


def competition_of(url: str) -> Competition:
    """The competition a page's address names."""
    title = unquote(urlsplit(url).path).replace(" ", "_")
    for name, competition in TITLES.items():
        if name in title:
            return competition
    raise ValueError(f"{url} names none of the competitions: {', '.join(TITLES)}")


def _end(text: str, start: int) -> int:
    """Where the template opening at `start` closes, just after its `}}`."""
    depth = 0
    for brace in _BRACES.finditer(text, start):
        depth += 1 if brace[0] == "{{" else -1
        if depth == 0:
            return brace.end()
    raise UnreadablePageError("a match's template is left open: the page's layout has changed")


def _parameters(template: str) -> dict[str, str]:
    """A template's named parameters, split on each `|` outside an inner template or link."""
    body, parts, depth, start = template[2:-2], [], 0, 0
    for mark in _MARKS.finditer(body):
        if mark[0] in ("{{", "[["):
            depth += 1
        elif mark[0] in ("}}", "]]"):
            depth -= 1
        elif depth == 0:
            parts.append(body[start : mark.start()])
            start = mark.end()
    parts.append(body[start:])
    named = (part.split("=", 1) for part in parts[1:] if "=" in part)
    return {name.strip().lower(): value.strip() for name, value in named}


def _date(value: str) -> dt.date | None:
    start = _START_DATE.match(value)
    plain = _PLAIN_DATE.fullmatch(value)
    try:
        if start:
            return dt.date(int(start[1]), int(start[2]), int(start[3]))
        if plain and plain[2] in MONTHS:
            return dt.date(int(plain[3]), MONTHS[plain[2]], int(plain[1]))
    except ValueError:  # no such day
        return None
    return None


def _club(value: str) -> str | None:
    """The club a side names: the text of its one link, its flag and its tier dropped."""
    while _TEMPLATE.search(value):
        value = _TEMPLATE.sub("", value)
    links = _LINK.findall(value)
    if len(links) != 1:
        return None
    target, shown = links[0]
    return (shown or target).strip() or None


def _kickoff(parameters: dict[str, str]) -> dt.datetime | None:
    day = _date(parameters.get("date", ""))
    time = _TIME.search(parameters.get("time", ""))
    if day is None or time is None:
        return None
    return dt.datetime.combine(day, dt.time(int(time[1]), int(time[2])), ROME)


def read_other_fixtures(text: str, competition: Competition) -> OtherFixturesFacts:
    """The competition's matches on its page. A page without a match template, or without a settled match, is
    unreadable rather than misread: its layout has changed, or there's nothing to keep."""
    text = _HIDDEN.sub("", text)
    matches: list[Fixture] = []
    problems: list[str] = []
    unsettled = boxes = 0
    for found in _BOX.finditer(text):
        boxes += 1
        parameters = _parameters(text[found.start() : _end(text, found.start())])
        kickoff = _kickoff(parameters)
        home, away = _club(parameters.get("team1", "")), _club(parameters.get("team2", ""))
        if kickoff is None or home is None or away is None:
            unsettled += 1
            continue
        try:
            matches.append(Fixture(home=home, away=away, kickoff_at=kickoff))
        except ValidationError as error:
            problems.append(f"{home} v {away}: {error.errors()[0]['msg']}")
    if not boxes:
        raise UnreadablePageError("no Football box template: the page's layout has changed")
    if not matches:
        raise UnreadablePageError("no match with a fixed date, a kickoff and both clubs")
    if unsettled:
        noun = "match" if unsettled == 1 else "matches"
        problems.append(f"{unsettled} {noun} without a fixed date, a kickoff or both clubs, left out")
    try:
        payload = OtherFixturesPayload(competition=competition, matches=matches)
    except ValidationError as error:
        raise UnreadablePageError(f"the matches don't fit the contract: {error.errors()[0]['msg']}") from None
    return OtherFixturesFacts(payload, problems)
