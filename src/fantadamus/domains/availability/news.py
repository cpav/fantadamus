"""What the injured and suspended pages say about one player, as an answer says it (mvp-sources design C5;
R3.2, R3.3).

A player's rows are found among his club's by his name, or by his surname as the outlets' are. He's out when
the injured page lists him, or the suspended page bans him for the round asked or names no round; he's one
booking from a ban when it lists him among the diffidati. None of it moves a number: the outlets already price
who's out (R3.3). Where an outlet, or the official lineup, has him starting while a page has him out, that's
said as a disagreement.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel

from fantadamus.domains.availability.consensus import Availability
from fantadamus.domains.availability.silver import InjuryRow, SuspensionRow
from fantadamus.domains.facts import Source
from fantadamus.domains.players.resolve import KnownPlayer, resolve, same_surname

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
STARTING = 0.5
"""An outlet's own chance at or above this has him starting, for a disagreement."""
_KINDS = {
    "muscle": "muscle injury",
    "knock": "knock",
    "fracture": "fracture",
    "ligament": "ligament injury",
    "surgery": "surgery",
    "national team": "injury with his national team",
}


class OutDetail(BaseModel):
    reason: str
    """"thigh muscle injury", "banned for round 12", or "out, detail on the page"."""
    back: str | None = None
    """"back from late November", "return to be assessed"; None when the page doesn't say."""


@dataclass(frozen=True)
class News:
    out: OutDetail | None
    one_booking: bool
    banned: bool
    """The suspended page is why he's out, rather than only the injured page."""
    sources: tuple[Source, ...]


def reason_said(row: InjuryRow) -> str:
    part = row.body_part if row.body_part not in (None, "other") else None
    if row.kind == "illness":
        return "illness"
    if row.kind in _KINDS:
        return f"{part} {_KINDS[row.kind]}" if part else _KINDS[row.kind]
    return f"{part} injury" if part else "out, detail on the page"


def back_said(row: InjuryRow) -> str | None:
    start, end = row.back_from, row.back_until
    if start is None or end is None:
        return "return to be assessed" if row.to_be_assessed else None
    month = MONTHS[start.month - 1]
    if start == end:
        return f"back around {start.day} {month}"
    whole = end.month == start.month and end.day == calendar.monthrange(end.year, end.month)[1]
    if start.day == 1 and whole:
        return f"back from {month}"
    parts = {(1, 10): "early", (11, 20): "mid"}
    if (start.day, end.day) in parts:
        return f"back from {parts[start.day, end.day]} {month}"
    if start.day == 16 and whole:
        return f"back from the second half of {month}"
    if start.day == 21 and whole:
        return f"back from late {month}"
    return f"back from {start.day} {month}"


def current[R: InjuryRow | SuspensionRow](rows: Sequence[R]) -> list[R]:
    """The rows of the page's newest read: a player it no longer lists is back, and a club it lists with
    nobody out gives no row, so an older read must not stand in for it. Claude submits the whole page at
    once."""
    newest = max(((row.captured_at, row.content_sha256) for row in rows), default=None)
    return [row for row in rows if (row.captured_at, row.content_sha256) == newest]


def _his[R: InjuryRow | SuspensionRow](
    player: KnownPlayer, rows: Sequence[R], mates: Sequence[KnownPlayer]
) -> list[R]:
    club = [row for row in rows if row.club == player.club]
    named = [row for row in club if resolve(row.name, mates).player == player]
    return named or [row for row in club if same_surname(row.name, mates) == player]


def news_of(
    player: KnownPlayer,
    round: int,
    injuries: Sequence[InjuryRow],
    suspensions: Sequence[SuspensionRow],
    mates: Sequence[KnownPlayer],
) -> News | None:
    """What the pages' current reads say about `player` for `round`; None when they don't name him."""
    injured = _his(player, injuries, mates)
    bans = _his(player, suspensions, mates)
    banned = [row for row in bans if row.status == "banned"]
    rounds = sorted({row.round for row in banned if row.round is not None})
    out_now = any(row.round is None or row.round == round for row in banned)
    reasons = []
    if out_now:
        reasons.append(
            "banned"
            if not rounds
            else f"banned for round {rounds[0]}"
            if len(rounds) == 1
            else f"banned for rounds {', '.join(map(str, rounds[:-1]))} and {rounds[-1]}"
        )
    if injured:
        reasons.append(reason_said(injured[0]))
    warned = any(row.status == "one booking" for row in bans)
    if not reasons and not warned:
        return None
    out = (
        OutDetail(reason="; ".join(reasons), back=back_said(injured[0]) if injured else None)
        if reasons
        else None
    )
    used = [
        *(injured[:1]),
        *(banned if out_now else []),
        *(row for row in bans if row.status == "one booking"),
    ]
    return News(
        out=out, one_booking=warned, banned=out_now, sources=tuple(dict.fromkeys(row.source for row in used))
    )


def page_disagreement(news: News, present: Availability | None) -> str | None:
    """Where an outlet, or the official lineup, has him starting while a page has him out."""
    if news.out is None or present is None:
        return None
    page = (
        "Fantacalcio.it's bans page has him banned"
        if news.banned
        else "Fantacalcio.it's injury page has him out"
    )
    if present.official is not None and present.official.status == "starter":
        return f"The official lineup has him starting; {page}."
    starting = [
        view.outlet
        for view in present.outlets
        if view.status == "starter"
        or (view.status in ("ballottaggio", "percentage") and view.p_start >= STARTING)
    ]
    if not starting:
        return None
    named = starting[0] if len(starting) == 1 else f"{', '.join(starting[:-1])} and {starting[-1]}"
    return f"{named} {'has' if len(starting) == 1 else 'have'} him starting; {page}."
