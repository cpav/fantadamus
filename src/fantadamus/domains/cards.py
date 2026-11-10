"""The match card's pure parts (mvp-cards design C2 to C4; R2 to R4).

This module knows what a card says about a fixture, from facts and values already worked out: the odds' team
xG, the table's rows and, in later tasks, each player's availability and value. It reads nothing and prices
nothing itself, so a card can't disagree with the other answers. The table's record and form are shown and
never used in a number (R2.4).
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from fantadamus.domains.odds.gold import TeamXg
from fantadamus.domains.season.silver import TeamSeasonRow
from fantadamus.engine import odds
from fantadamus.engine.keepers import clean_sheet


class Season(BaseModel):
    """A club's season so far, from the table: context beside the numbers, never in them."""

    played: int
    goals_for_per_match: float
    goals_against_per_match: float
    wins: int | None
    draws: int | None
    losses: int | None
    form: str | None
    """The last results as letters, oldest first."""


class Side(BaseModel):
    club: str
    p_win: float
    expected_goals: float
    p_clean_sheet: float
    """e^-xG of the other side's expected goals, as a keeper's is."""
    season: Season | None


class MatchNumbers(BaseModel):
    home: Side
    away: Side
    p_draw: float
    from_odds: bool
    """False when team form stood in for the odds."""
    spread: float | None
    """How far apart the odds pages' chances are; None with one page or none."""
    p_three_or_more: float | None
    p_both_score: float | None
    """Both None unless the odds showed over/under 2.5: the 1X2 alone, or team form, doesn't price goals."""


def season(row: TeamSeasonRow | None) -> Season | None:
    """The table's row for a club, per match; None without a row or before a match is played."""
    if row is None or not row.played:
        return None
    return Season(
        played=row.played,
        goals_for_per_match=row.goals_for / row.played,
        goals_against_per_match=row.goals_against / row.played,
        wins=row.wins,
        draws=row.draws,
        losses=row.losses,
        form=row.form,
    )


def match_numbers(xg: TeamXg, home: str, away: str, table: Mapping[str, TeamSeasonRow]) -> MatchNumbers:
    """The match in numbers (C2): the chances `team_xg` gives, each side's clean sheet, and the goals'
    chances where the odds price them; `table`, each club's latest row, only as its season so far."""
    market = odds.model(xg.home_xg, xg.away_xg) if xg.from_odds and xg.totals else None
    return MatchNumbers(
        home=Side(
            club=home,
            p_win=xg.p_home_win,
            expected_goals=xg.home_xg,
            p_clean_sheet=clean_sheet(xg.away_xg),
            season=season(table.get(home)),
        ),
        away=Side(
            club=away,
            p_win=xg.p_away_win,
            expected_goals=xg.away_xg,
            p_clean_sheet=clean_sheet(xg.home_xg),
            season=season(table.get(away)),
        ),
        p_draw=xg.p_draw,
        from_odds=xg.from_odds,
        spread=xg.spread if xg.from_odds and len(xg.sources) > 1 else None,
        p_three_or_more=market.p_over if market is not None else None,
        p_both_score=market.p_btts if market is not None else None,
    )
