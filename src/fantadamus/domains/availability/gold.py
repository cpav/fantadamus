"""As-of availability of one player for one match (design C5, C6; R3, R4.2, R7.4).

Each outlet counts with its latest lineup for the match; the latest official lineup, once out, decides.
Names are matched against the player's club-mates with profiles (design C4).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from fantadamus.core.names import name_key
from fantadamus.domains.availability.consensus import (
    Availability,
    OfficialView,
    Status,
    combine,
    outlet_view,
)
from fantadamus.domains.availability.silver import LineupViewRow, OfficialLineupRow
from fantadamus.domains.facts import latest_submissions
from fantadamus.domains.players.resolve import KnownPlayer, resolve

_STRONGEST: tuple[Status, ...] = ("unavailable", "ballottaggio", "starter", "bench")


def _view_of(rows: Sequence[LineupViewRow]) -> tuple[Status, float | None]:
    """His status in one outlet's lineup: unavailable outranks a ballottaggio, a starting place, the bench."""
    for status in _STRONGEST:
        row = next((row for row in rows if row.status == status), None)
        if row is not None:
            return status, row.share
    return "not listed", None


def availability(
    player: KnownPlayer,
    *,
    home: str,
    away: str,
    views: Sequence[LineupViewRow],
    officials: Sequence[OfficialLineupRow],
    players: Sequence[KnownPlayer],
    as_of: dt.datetime,
) -> Availability | None:
    """His p_start and p_cameo for the match, or None if no lineup for it is known yet."""
    mates = [known for known in players if known.club == player.club]

    def mentions(row: LineupViewRow | OfficialLineupRow) -> bool:
        return row.club == player.club and resolve(row.name, mates).player == player

    outlets = []
    match_views = [row for row in views if (row.home, row.away) == (home, away)]
    for rows in latest_submissions(match_views, as_of, key=lambda row: name_key(row.outlet)).values():
        status, share = _view_of([row for row in rows if mentions(row)])
        outlets.append(outlet_view(rows[0].outlet, status, share, rows[0].source))

    official = None
    match_officials = [row for row in officials if (row.home, row.away) == (home, away)]
    for sheet in latest_submissions(match_officials, as_of, key=lambda row: (row.home, row.away)).values():
        named = [row for row in sheet if mentions(row)]
        official = OfficialView(status=named[0].status if named else "not listed", source=sheet[0].source)

    if not outlets and official is None:
        return None
    return combine(outlets, official)
