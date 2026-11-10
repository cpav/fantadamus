"""Invented odds and tables for the match card's pure tests (mvp-cards): no lake, no tools."""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import LeagueRules
from fantadamus.domains.availability.consensus import OfficialStatus, OfficialView, combine, outlet_view
from fantadamus.domains.cards import Listed, Valued
from fantadamus.domains.facts import Source
from fantadamus.domains.odds.silver import OddsRow
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.season.silver import PlayerSeasonRow, TeamSeasonRow
from fantadamus.engine import keepers, outfield
from fantadamus.engine.keepers import KeeperInputs, KeeperValue
from fantadamus.engine.outfield import OutfieldInputs, OutfieldValue
from fantadamus.league.rules import CLASSIC, scoring_for

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


def valued(
    part: Listed,
    *,
    rated: int = 8,
    goals: int = 2,
    penalties: tuple[int, int] = (0, 0),
    team_xg: float = 1.5,
    opponent_xg: float = 1.1,
    penalty_share: float = 0.0,
    rules: LeagueRules = CLASSIC,
) -> Valued:
    """`part` priced by the engine itself, as the card's tool will price him, from invented season figures."""
    form = PlayerSeasonRow(
        **source("https://example.org/statistiche").model_dump(),
        player_id=part.player.player_id,
        name=part.player.name,
        club=part.player.club,
        role=part.role,
        mantra_role=None,
        appearances=rated,
        rated_appearances=rated,
        average_rating=6.2 if part.role == "P" else 6.3,
        goals=0 if part.role == "P" else goals,
        assists=1,
        yellow_cards=1,
        penalties_scored=penalties[0],
        penalties_taken=penalties[1],
        goals_conceded=9 if part.role == "P" else None,
    )
    scoring = scoring_for(rules, part.role)
    value: OutfieldValue | KeeperValue
    if part.role == "P":
        value = keepers.value(
            KeeperInputs(
                name=form.name,
                club=form.club,
                rated_appearances=form.rated_appearances,
                average_rating=form.average_rating,
                goals_conceded=form.goals_conceded,
                league_goals_per_match=1.3,
                opponent_xg=opponent_xg,
                p_start=part.present.p_start,
            ),
            scoring,
        )
    else:
        value = outfield.value(
            OutfieldInputs(
                name=form.name,
                role=part.role,
                mantra_role=None,
                appearances=form.appearances,
                rated_appearances=form.rated_appearances,
                average_rating=form.average_rating,
                goals=form.goals,
                assists=form.assists,
                yellow_cards=form.yellow_cards,
                club_goals_per_match=1.4,
                penalty_share=penalty_share,
                penalties_scored=penalties[0],
                team_xg=team_xg,
                p_win=0.45,
                p_loss=0.30,
                p_start=part.present.p_start,
                p_cameo=part.present.p_cameo,
                opponent_xg=opponent_xg,
            ),
            scoring,
        )
    return Valued(listed=part, value=value, form=form)
