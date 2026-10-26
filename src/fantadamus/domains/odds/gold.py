"""As-of team xG for a match (design C6, C7; R5.2, R5.3, R7.4): fitted from the mean of the pages' latest
odds, or, without odds, from regressed team form, flagged."""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Sequence

from pydantic import BaseModel

from fantadamus.core.names import name_key
from fantadamus.domains.facts import Source, latest_by
from fantadamus.domains.odds.silver import OddsRow
from fantadamus.domains.season.silver import TeamSeasonRow
from fantadamus.engine import odds


class TeamXg(BaseModel):
    home_xg: float
    away_xg: float
    p_home_win: float
    p_draw: float
    p_away_win: float
    from_odds: bool
    """False when no odds were known and team form stood in (R5.3)."""
    sources: list[Source]


def _mean(values: Sequence[float]) -> float:
    return math.fsum(values) / len(values)


def _market(rows: Sequence[OddsRow]) -> odds.Market:
    btts = [row.p_btts for row in rows if row.p_btts is not None]
    return odds.Market(
        p_home=_mean([row.p_home for row in rows]),
        p_draw=_mean([row.p_draw for row in rows]),
        p_away=_mean([row.p_away for row in rows]),
        p_over=_mean([row.p_over for row in rows]),
        p_btts=_mean(btts) if btts else None,
    )


def team_xg(
    odds_rows: Sequence[OddsRow],
    team_rows: Sequence[TeamSeasonRow],
    *,
    home: str,
    away: str,
    as_of: dt.datetime,
) -> TeamXg | None:
    """The match's team xG as known at `as_of`, or None without odds or a league table covering both clubs."""
    match = [row for row in odds_rows if (row.home, row.away) == (home, away)]
    pages = sorted(
        latest_by(match, as_of, key=lambda row: (row.source_url, name_key(row.bookmaker))).values(),
        key=lambda row: (row.source_url, row.bookmaker),
    )
    if pages:
        home_xg, away_xg = odds.fit(_market(pages))
        return _result(home_xg, away_xg, from_odds=True, sources=[row.source for row in pages])
    table = latest_by(team_rows, as_of, key=lambda row: row.club)
    played = sum(row.played for row in table.values())
    if (
        home not in table
        or away not in table
        or not played
        or not table[home].played
        or not table[away].played
    ):
        return None
    league = sum(row.goals_for for row in table.values()) / played
    sides = [
        (
            table[club].goals_for / table[club].played,
            table[club].goals_against / table[club].played,
            table[club].played,
        )
        for club in (home, away)
    ]
    home_xg, away_xg = odds.form_xg(sides[0], sides[1], league)
    sources = sorted({table[home].source, table[away].source}, key=lambda source: source.captured_at)
    return _result(home_xg, away_xg, from_odds=False, sources=sources)


def _result(home_xg: float, away_xg: float, *, from_odds: bool, sources: list[Source]) -> TeamXg:
    market = odds.model(home_xg, away_xg)
    return TeamXg(
        home_xg=home_xg,
        away_xg=away_xg,
        p_home_win=market.p_home,
        p_draw=market.p_draw,
        p_away_win=market.p_away,
        from_odds=from_odds,
        sources=sources,
    )
