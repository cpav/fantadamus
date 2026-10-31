"""Fantacalcio-Online's round page read into facts (mvp-collect design C3.1; R3.1, R3.4, R4.2).

The page has one `div.tab-pane` per match, under one tab each. A pane holds the header (the clubs and the
kickoff in Italian time), the 1X2 odds, the chance of 3 or more goals with the time the odds were updated, and
each team's two tables ("Probabili titolari", "Probabile panchina") with one column per outlet, the page's own
average and the official-lineup column. The average is skipped; a dash means the outlet doesn't list him.
Names stay as the page writes them ("SKORUPSKI L"); clubs and players are mapped when the facts are stored.
"""

from __future__ import annotations

import datetime as dt
import functools
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.fixtures import Fixture, FixturesPayload
from fantadamus.contracts.xy.lineups import (
    OfficialLineupPayload,
    OfficialTeam,
    OutletLineupPayload,
    OutletPlayer,
    OutletTeam,
)
from fantadamus.contracts.xy.odds import MatchOddsPayload
from fantadamus.core.names import name_key
from fantadamus.web.html import Element, parse
from fantadamus.web.readers import UnreadablePageError

BOOKMAKER = "Fantacalcio-Online"
OUTLETS = ("Fantacalcio.it", "Gazzetta", "SOS Fanta", "Sky")
AVERAGE = "Tutte le fonti"
ROME = ZoneInfo("Europe/Rome")
_ROLES: dict[str, Role] = {"P": "P", "D": "D", "C": "C", "A": "A"}
_NOT_LISTED = {"\u2013", "-", ""}  # an en dash, a hyphen, nothing
_MONTHS = [
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
]
_SIGNS = (("1", "home_win"), ("X", "draw"), ("2", "away_win"))  # the 1X2 boxes, in order
_ROUND = re.compile(r"(\d+)\s*ª\s*Giornata", re.IGNORECASE)
_UPDATED = re.compile(r"(\d{1,2}) (\w+) alle (\d{1,2}):(\d{2})")
_NUMBER = re.compile(r"\d+(?:,\d+)?")
_PERCENT = re.compile(r"(\d+(?:,\d+)?)\s*%")


@dataclass(frozen=True)
class MatchOdds:
    payload: MatchOddsPayload
    published_at: dt.datetime | None  # when the page says the odds were updated


@dataclass(frozen=True)
class RoundFacts:
    fixtures: FixturesPayload
    odds: list[MatchOdds]
    outlets: list[OutletLineupPayload]
    officials: list[OfficialLineupPayload]
    problems: list[str]  # payloads that failed their contract, left out (design, error handling)


@dataclass
class _Found:
    odds: list[MatchOdds] = field(default_factory=list)
    outlets: list[OutletLineupPayload] = field(default_factory=list)
    officials: list[OfficialLineupPayload] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Row:
    name: str
    role: Role | None
    percents: dict[str, float]  # by outlet; an outlet that doesn't list him is absent
    confirmed: bool


@dataclass(frozen=True)
class _Team:
    starters: list[_Row]
    bench: list[_Row]
    unavailable: list[str]


def read_round(html: str, round: int | None = None) -> RoundFacts:
    """The round's facts, or `UnreadablePageError` if the page lacks anything the reader relies on. Without
    `round`, the page's title names it ("… - 11ª Giornata"): the current-round address has no number."""
    tree = parse(html)
    if round is None:
        title = tree.find("title")
        named = _ROUND.search(title.text()) if title else None
        if named is None:
            raise UnreadablePageError("the page's title names no round")
        round = int(named.group(1))
    panes = [
        (pane, header)
        for pane in tree.find_all("div", "tab-pane")
        if (header := pane.find("header", "prb-incontro")) is not None
    ]
    if not panes or len(panes) != len(tree.find_all(class_="prb-partita")):
        raise UnreadablePageError("the match tabs and their panes don't match")
    fixtures: list[Fixture] = []
    found = _Found()
    for pane, header in panes:
        home, away, kickoff = _match(header)
        fixtures.append(Fixture(home=home, away=away, kickoff_at=kickoff))
        _read_match(pane, home, away, kickoff, found)
    try:
        round_fixtures = FixturesPayload(round=round, matches=fixtures)
    except ValidationError as error:
        raise UnreadablePageError(f"the fixtures don't hold together: {error.errors()[0]['msg']}") from error
    return RoundFacts(round_fixtures, found.odds, found.outlets, found.officials, found.problems)


def _read_match(pane: Element, home: str, away: str, kickoff: dt.datetime, found: _Found) -> None:
    """One match's odds, outlet views and official lineup, added to `found`. A payload that fails its contract
    is left out and named in `found.problems`; the match's other payloads still count."""
    teams = _team(pane, "home", home), _team(pane, "away", away)

    def attempt[T](what: str, build: Callable[[], T]) -> T | None:
        try:
            return build()
        except ValidationError as error:
            found.problems.append(f"{home} v {away}, {what}: {error.errors()[0]['msg']}")
            return None

    price = _odds(pane, home, away)
    if price is not None:
        prices, over3, updated = price
        payload = attempt(
            "odds",
            lambda: MatchOddsPayload(
                home=home, away=away, bookmaker=BOOKMAKER, **prices, over_2_5_percent=over3
            ),
        )
        if payload is not None:
            found.odds.append(MatchOdds(payload, _updated_at(updated, kickoff) if updated else None))
    for outlet in OUTLETS:
        view = attempt(outlet, functools.partial(_outlet_view, outlet, home, away, teams))
        if view is not None:
            found.outlets.append(view)
    if all(row.confirmed for team in teams for row in team.starters):
        official = attempt(
            "official lineup",
            lambda: OfficialLineupPayload(
                home=home, away=away, home_team=_official_team(teams[0]), away_team=_official_team(teams[1])
            ),
        )
        if official is not None:
            found.officials.append(official)


def _match(header: Element) -> tuple[str, str, dt.datetime]:
    names = [name.text() for name in header.find_all(class_="prb-incontro__nome")]
    if len(names) != 2 or not all(names):
        raise UnreadablePageError(f"a match header names {len(names)} clubs")
    when = header.find(class_="prb-incontro__data")
    try:
        local = dt.datetime.strptime(when.text() if when else "", "%d/%m/%Y %H:%M")
    except ValueError as error:
        raise UnreadablePageError(f"{names[0]} v {names[1]} has no kickoff") from error
    return names[0], names[1], local.replace(tzinfo=ROME).astimezone(dt.UTC)


def _decimal(text: str) -> float:
    return float(text.replace(",", "."))


def _odds(pane: Element, home: str, away: str) -> tuple[dict[str, float], float | None, str | None] | None:
    """The 1X2 odds, the chance of 3+ goals and the update text; None when the page shows no odds yet."""
    boxes = pane.find_all("div", "stp-qbox")
    if not boxes:
        return None
    if len(boxes) != len(_SIGNS):
        raise UnreadablePageError(f"{home} v {away} shows {len(boxes)} odds, not 3")
    prices: dict[str, float] = {}
    for box, (sign, market) in zip(boxes, _SIGNS, strict=True):
        label, value = box.find(class_="stp-qlab"), box.find(class_="stp-qval")
        number = _NUMBER.search(value.text()) if value else None
        if label is None or not label.text().startswith(sign) or number is None:
            raise UnreadablePageError(f"{home} v {away}: the {sign} odds don't read")
        prices[market] = _decimal(number.group())
    over3 = updated = None
    markets = pane.find("ul", "prb-sintesi__mercati")
    for item in markets.find_all("li") if markets else []:
        text = item.text()
        if item.has_class("prb-sintesi__ora"):
            updated = text
        elif "3 o più" in text and (percent := _PERCENT.search(text)):
            over3 = _decimal(percent.group(1))
    return prices, over3, updated


def _updated_at(text: str, kickoff: dt.datetime) -> dt.datetime | None:
    """`quote aggiornate il 30 ottobre alle 18:13`, Italian time, in the year that puts it before kickoff."""
    found = _UPDATED.search(text)
    if found is None or found.group(2).lower() not in _MONTHS:
        return None
    day, month = int(found.group(1)), _MONTHS.index(found.group(2).lower()) + 1
    hour, minute = int(found.group(3)), int(found.group(4))
    for year in (kickoff.year, kickoff.year - 1):
        try:
            stamp = dt.datetime(year, month, day, hour, minute, tzinfo=ROME).astimezone(dt.UTC)
        except ValueError:  # 29 February in a year without it
            continue
        if stamp <= kickoff:
            return stamp
    return None


def _team(pane: Element, side: str, club: str) -> _Team:
    sections = pane.find_all("section", f"prb-squadra--{side}")
    heading = sections[0].find("h2", "prb-squadra__nome") if len(sections) == 1 else None
    if heading is None or name_key(heading.text()) != name_key(club):
        raise UnreadablePageError(f"{club}'s lineup is missing")
    tables: dict[str, list[_Row]] = {}
    for table in sections[0].find_all("table", "prb-tabella"):
        caption = table.find("caption")
        kind = caption.text().lower().split(":")[0] if caption else ""
        tables[kind] = _rows(table, club)
    if "probabili titolari" not in tables:
        raise UnreadablePageError(f"{club} has no probable starters table")
    unavailable = [
        name.text()
        for row in sections[0].find_all("li", "prb-fuori__riga")
        if (name := row.find(class_="prb-nome")) is not None
    ]
    return _Team(tables["probabili titolari"], tables.get("probabile panchina", []), unavailable)


def _rows(table: Element, club: str) -> list[_Row]:
    columns = table.find_all("th", "prb-tabella__fonte")
    kinds = [
        "confirmed" if column.has_class("prb-tabella__conferma") else column.attr("title") or "?"
        for column in columns
    ]
    if sorted(kinds) != sorted((*OUTLETS, AVERAGE, "confirmed")):
        raise UnreadablePageError(f"{club}'s outlet columns are {kinds}")
    body = table.find("tbody")
    rows: list[_Row] = []
    for row in body.find_all("tr") if body else []:
        name, cells = row.find(class_="prb-nome"), row.find_all("td")
        if name is None or len(cells) != len(kinds):
            raise UnreadablePageError(f"a row of {club}'s lineup doesn't read")
        percents: dict[str, float] = {}
        for kind, cell in zip(kinds, cells, strict=True):
            text = cell.text()
            if kind not in OUTLETS or text in _NOT_LISTED:
                continue
            if (percent := _PERCENT.fullmatch(text)) is None:
                raise UnreadablePageError(f"{name.text()}'s {kind} percentage reads {text!r}")
            percents[kind] = _decimal(percent.group(1))
        role = row.find("span", "role")
        rows.append(
            _Row(
                name=name.text(),
                role=_ROLES.get(role.text()) if role else None,
                percents=percents,
                confirmed=bool(cells[kinds.index("confirmed")].text()),
            )
        )
    return rows


def _outlet_view(outlet: str, home: str, away: str, teams: tuple[_Team, _Team]) -> OutletLineupPayload:
    return OutletLineupPayload(
        outlet=outlet,
        home=home,
        away=away,
        home_team=_outlet_team(teams[0], outlet),
        away_team=_outlet_team(teams[1], outlet),
    )


def _outlet_team(team: _Team, outlet: str) -> OutletTeam:
    players = [
        OutletPlayer(name=row.name, role=row.role, percent=row.percents[outlet])
        for row in team.starters + team.bench
        if outlet in row.percents
    ]
    return OutletTeam(players=players, unavailable=team.unavailable)


def _official_team(team: _Team) -> OfficialTeam:
    return OfficialTeam(starters=[row.name for row in team.starters], bench=[row.name for row in team.bench])
