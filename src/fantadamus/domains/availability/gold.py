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
    OutletView,
    Status,
    combine,
    outlet_view,
)
from fantadamus.domains.availability.silver import LineupViewRow, OfficialLineupRow, OutletViewRow
from fantadamus.domains.facts import latest_submissions
from fantadamus.domains.players.resolve import KnownPlayer, resolve

_STRONGEST: tuple[Status, ...] = ("unavailable", "ballottaggio", "starter", "bench")


def _view_of(rows: Sequence[LineupViewRow]) -> LineupViewRow | None:
    """His row in one outlet's lineup: unavailable outranks a ballottaggio, a starting place, the bench."""
    for status in _STRONGEST:
        row = next((row for row in rows if row.status == status), None)
        if row is not None:
            return row
    return None


def _rivals(row: LineupViewRow, lineup: Sequence[LineupViewRow]) -> list[str]:
    """The others in his ballottaggio in the same outlet's lineup."""
    if row.status != "ballottaggio" or row.contest is None:
        return []
    return [
        other.name
        for other in lineup
        if other.status == "ballottaggio"
        and (other.club, other.contest) == (row.club, row.contest)
        and other is not row
    ]


def _stamp(row: LineupViewRow) -> tuple[dt.datetime, str]:
    return row.captured_at, row.content_sha256


def _percentage_view(sheet: Sequence[OutletViewRow], his: Sequence[OutletViewRow]) -> OutletView:
    """One outlet's percentage for him, its word that he's unavailable, or that it didn't list him."""
    outlet, source = sheet[0].outlet, sheet[0].source
    if any(row.unavailable for row in his):
        return outlet_view(outlet, "unavailable", None, source)
    percent = next((row.percent for row in his if row.percent is not None), None)
    return (
        outlet_view(outlet, "percentage", percent, source)
        if percent is not None
        else outlet_view(outlet, "not listed", None, source)
    )


def availability(
    player: KnownPlayer,
    *,
    home: str,
    away: str,
    views: Sequence[LineupViewRow],
    officials: Sequence[OfficialLineupRow],
    players: Sequence[KnownPlayer],
    as_of: dt.datetime,
    outlet_views: Sequence[OutletViewRow] = (),
) -> Availability | None:
    """His p_start and p_cameo for the match, or None if no lineup for it is known yet. Each outlet counts
    once, from its newest read, whether it gave a lineup or its own percentages (mvp-collect R4.2)."""
    mates = [known for known in players if known.club == player.club]

    def mentions(row: LineupViewRow | OfficialLineupRow | OutletViewRow) -> bool:
        return row.club == player.club and resolve(row.name, mates).player == player

    def in_match[R: LineupViewRow | OutletViewRow](rows: Sequence[R]) -> list[R]:
        return [row for row in rows if (row.home, row.away) == (home, away)]

    lineups = latest_submissions(in_match(views), as_of, key=lambda row: name_key(row.outlet))
    percentages = latest_submissions(in_match(outlet_views), as_of, key=lambda row: name_key(row.outlet))
    outlets = []
    for outlet in sorted(lineups.keys() | percentages.keys()):
        lineup, sheet = lineups.get(outlet), percentages.get(outlet)
        if sheet and (not lineup or (sheet[0].captured_at, sheet[0].content_sha256) > _stamp(lineup[0])):
            outlets.append(_percentage_view(sheet, [row for row in sheet if mentions(row)]))
        elif lineup:
            row = _view_of([row for row in lineup if mentions(row)])
            if row is None:
                outlets.append(outlet_view(lineup[0].outlet, "not listed", None, lineup[0].source))
            else:
                outlets.append(
                    outlet_view(row.outlet, row.status, row.share, row.source, _rivals(row, lineup))
                )

    official = None
    match_officials = [row for row in officials if (row.home, row.away) == (home, away)]
    for team_sheet in latest_submissions(
        match_officials, as_of, key=lambda row: (row.home, row.away)
    ).values():
        named = [row for row in team_sheet if mentions(row)]
        official = OfficialView(
            status=named[0].status if named else "not listed", source=team_sheet[0].source
        )

    if not outlets and official is None:
        return None
    return combine(outlets, official)
