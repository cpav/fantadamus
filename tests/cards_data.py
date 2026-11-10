"""Invented odds and tables for the match card's pure tests (mvp-cards): no lake, no tools."""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from fantadamus.contracts.types import Role
from fantadamus.domains.availability.consensus import OfficialStatus, OfficialView, combine, outlet_view
from fantadamus.domains.cards import Listed
from fantadamus.domains.facts import Source
from fantadamus.domains.odds.silver import OddsRow
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.season.silver import TeamSeasonRow

AT = dt.datetime(2026, 11, 20, 9, 0, tzinfo=dt.UTC)
"""When the card is asked for."""
READ = AT - dt.timedelta(hours=2)


def source(url: str = "https://example.org/page", at: dt.datetime = READ) -> Source:
    return Source(source_url=url, captured_at=at, content_sha256="0" * 64)


def odds_row(
    p_home: float,
    p_draw: float,
    p_away: float,
    *,
    p_over: float | None = None,
    p_btts: float | None = None,
    url: str = "https://example.org/round",
    bookmaker: str = "Bookmaker",
) -> OddsRow:
    """One page's de-margined prices for Alfa v Beta."""
    return OddsRow(
        **source(url).model_dump(),
        home="alfa",
        away="beta",
        bookmaker=bookmaker,
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        p_over=p_over,
        p_btts=p_btts,
    )


def table_row(club: str, played: int, goals_for: int, goals_against: int, **record: Any) -> TeamSeasonRow:
    return TeamSeasonRow(
        **source("https://example.org/classifica").model_dump(),
        club=club,
        played=played,
        goals_for=goals_for,
        goals_against=goals_against,
        **record,
    )


ALFA = table_row("alfa", 9, 17, 8, wins=6, draws=2, losses=1, form="WWDLW")
BETA = table_row("beta", 9, 11, 13, wins=3, draws=2, losses=4, form="LWDLW")


KICKOFF = dt.datetime(2026, 11, 21, 14, 0, tzinfo=dt.UTC)
OUTLETS = ("Fantacalcio.it", "Gazzetta", "SOS Fanta", "Sky")


def player_id(name: str) -> int:
    """A steady invented ID for a name."""
    return 1 + int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "big")


def listed(
    name: str,
    role: Role,
    percents: Sequence[float | None] = (90, 90, 95, 90),
    *,
    club: str = "alfa",
    rivals: Mapping[str, Sequence[str]] | None = None,
    official: OfficialStatus | None = None,
) -> Listed:
    """One player and how the four outlets see him: a percentage each, or None for unavailable. `rivals` makes
    an outlet's view a ballottaggio with those names, his percentage his share; `official` is his status on
    the official sheet."""
    views = []
    for outlet, percent in zip(OUTLETS, percents, strict=True):
        if percent is None:
            views.append(outlet_view(outlet, "unavailable", None, source()))
        elif rivals and outlet in rivals:
            views.append(outlet_view(outlet, "ballottaggio", percent, source(), rivals[outlet]))
        else:
            views.append(outlet_view(outlet, "percentage", percent, source()))
    sheet = OfficialView(status=official, source=source()) if official is not None else None
    player = KnownPlayer(player_id=player_id(name), name=name, club=club)
    return Listed(player=player, role=role, present=combine(views, sheet))
