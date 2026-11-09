"""Fantacalcio.it's statistics page read into every player's season so far (mvp-roles design C3; R1.2, R1.3,
R1.6).

The page is one table, `table#stats`, with one `tr.player-row` per player. Its header names each column by a
key (`data-col-key`) and a title, and the reader checks the title of every column it reads, so a column that
changes meaning makes the page unreadable instead of misread. A player's ID and club come from his profile
link (`/serie-a/squadre/{club}/{player}/{id}`), whose club slug is the club's key in `config/clubs.toml`. The
fantamedia, penalties saved and red cards are read for the lineup review, which works out a round from two
reads (mvp-review C1). The page gives no appearances without a rating, so his appearances are his rated ones.
Players come out by ID, so the same figures read the same whatever order the page sorts them in, and an
unchanged page stores nothing new (R1.5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import ValidationError

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.season import MantraRole, PlayerSeason, SeasonStatsPayload
from fantadamus.web.html import Element, parse
from fantadamus.web.readers import UnreadablePageError

TITLE = "Statistiche"
COLUMNS = {
    "pg": "Partite a voto",
    "mv": "Media voto",
    "gol": "Gol segnati",
    "gs": "Gol subiti",
    "rig": "Rigori segnati / tirati",
    "ass": "Assist",
    "amm": "Ammonizioni",
    "mfv": "Fantamedia",
    "rp": "Rigori parati",
    "esp": "Espulsioni",
}
"""The columns read, by key, with the title the page gives each."""
_ROLES: dict[str, Role] = {"p": "P", "d": "D", "c": "C", "a": "A"}
_MANTRA: dict[str, MantraRole] = {
    "por": "Por",
    "dc": "Dc",
    "dd": "Dd",
    "ds": "Ds",
    "b": "B",
    "e": "E",
    "m": "M",
    "c": "C",
    "t": "T",
    "w": "W",
    "a": "A",
    "pc": "Pc",
}
_PROFILE = re.compile(r"/serie-a/squadre/([^/]+)/[^/]+/(\d+)/?$")
_COUNT = re.compile(r"\d+")
_DECIMAL = re.compile(r"\d+(?:,\d+)?")
_SIGNED = re.compile(r"-?\d+(?:,\d+)?")
"""A fantasy average can fall below zero, for a keeper who concedes a lot."""
_PENALTIES = re.compile(r"(\d+)\s*/\s*(\d+)")


@dataclass(frozen=True)
class StatsFacts:
    payload: SeasonStatsPayload
    problems: list[str]
    """Rows left out, and why."""


class _BadRowError(ValueError):
    pass


def read_stats(html: str) -> StatsFacts:
    """Every readable player on the page, or `UnreadablePageError` if the page isn't the statistics page as
    the reader knows it."""
    tree = parse(html)
    title = tree.find("title")
    if title is None or TITLE not in title.text():
        raise UnreadablePageError("the page's title isn't the statistics page's")
    table = next((table for table in tree.find_all("table") if table.attr("id") == "stats"), None)
    if table is None:
        raise UnreadablePageError("the page has no statistics table")
    head = {th.attr("data-col-key"): _title(th) for th in table.find_all("th")}
    for key, name in COLUMNS.items():
        if head.get(key) != name:
            raise UnreadablePageError(f"the column {key!r} isn't {name!r}")
    rows = table.find_all("tr", "player-row")
    if not rows:
        raise UnreadablePageError("the statistics table has no player rows")
    players: dict[int, PlayerSeason] = {}
    problems: list[str] = []
    for row in rows:
        try:
            player = _player(row)
        except (_BadRowError, ValidationError) as error:
            problems.append(f"{_label(row)}: {_reason(error)}")
            continue
        if player.player_id in players:
            problems.append(f"{_label(row)}: listed twice")
            continue
        players[player.player_id] = player
    if not players:
        raise UnreadablePageError("no player row could be read")
    payload = SeasonStatsPayload(players=[players[key] for key in sorted(players)])
    return StatsFacts(payload=payload, problems=problems)


def _title(th: Element) -> str | None:
    link = th.find("a")
    return link.attr("title") if link is not None else None


def _player(row: Element) -> PlayerSeason:
    link = row.find("a", "player-link")
    found = _PROFILE.search(link.attr("href") or "") if link is not None else None
    if link is None or found is None:
        raise _BadRowError("no profile link")
    classic = row.find("th", "player-role-classic")
    role = classic.find("span", "role") if classic is not None else None
    if role is None or (classic_role := _ROLES.get(role.attr("data-value") or "")) is None:
        raise _BadRowError("no Classic role")
    cells = {key: td.text().strip() for td in row.find_all("td") if (key := td.attr("data-col-key"))}
    for key, name in COLUMNS.items():
        if key not in cells:
            raise _BadRowError(f"no {name} cell")
    rated = _count(cells["pg"])
    average = _decimal(cells["mv"])
    fantasy = _decimal(cells["mfv"], _SIGNED)
    penalties = _PENALTIES.fullmatch(cells["rig"])
    if penalties is None:
        raise _BadRowError(f"{cells['rig']!r} isn't scored / taken")
    return PlayerSeason(
        player_id=int(found.group(2)),
        name=link.text(),
        club=found.group(1),
        role=classic_role,
        mantra_role=_mantra(row),
        appearances=rated,
        rated_appearances=rated,
        average_rating=average if rated else None,
        goals=_count(cells["gol"]),
        assists=_count(cells["ass"]),
        yellow_cards=_count(cells["amm"]),
        penalties_scored=int(penalties.group(1)),
        penalties_taken=int(penalties.group(2)),
        goals_conceded=_count(cells["gs"]),
        fantasy_average=fantasy if rated else None,
        penalties_saved=_count(cells["rp"]),
        red_cards=_count(cells["esp"]),
    )


def _mantra(row: Element) -> MantraRole | None:
    """His first Mantra role, None if the page gives none."""
    cell = row.find("th", "player-role-mantra")
    first = cell.find("span", "role-mantra") if cell is not None else None
    if first is None:
        return None
    code = first.attr("data-value") or ""
    if code not in _MANTRA:
        raise _BadRowError(f"unknown Mantra role {code!r}")
    return _MANTRA[code]


def _count(text: str) -> int:
    if not _COUNT.fullmatch(text):
        raise _BadRowError(f"{text!r} isn't a number")
    return int(text)


def _decimal(text: str, form: re.Pattern[str] = _DECIMAL) -> float:
    if not form.fullmatch(text):
        raise _BadRowError(f"{text!r} isn't a number")
    return float(text.replace(",", "."))


def _label(row: Element) -> str:
    link = row.find("a", "player-link")
    found = _PROFILE.search(link.attr("href") or "") if link is not None else None
    name = link.text() if link is not None else "a row"
    return f"{name} ({found.group(2)})" if found else name


def _reason(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return "; ".join(str(detail["msg"]).removeprefix("Value error, ") for detail in error.errors())
    return str(error)
