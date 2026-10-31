"""Silver `odds`: each page's prices for a match, de-margined (R5.1, R5.2)."""

from __future__ import annotations

from fantadamus.contracts.xy.odds import MatchOddsPayload
from fantadamus.core.clubs import Clubs
from fantadamus.domains.facts import PROVENANCE_COLUMNS, Domain, RefusedError, SilverRow, Source
from fantadamus.engine.odds import de_margin
from fantadamus.lake.duckdb_store import Table


class OddsRow(SilverRow):
    home: str
    away: str
    bookmaker: str
    p_home: float
    p_draw: float
    p_away: float
    p_over: float | None
    """Over 2.5 goals."""
    p_btts: float | None
    """Both teams to score, when the page shows it."""


def _rows(payload: MatchOddsPayload, clubs: Clubs, source: Source) -> list[OddsRow]:
    home, away = clubs.key(payload.home), clubs.key(payload.away)
    if home == away:
        raise RefusedError(f"{payload.home} plays itself")
    p_home, p_draw, p_away = de_margin([payload.home_win, payload.draw, payload.away_win])
    totals = [payload.over_2_5, payload.under_2_5]
    p_over = de_margin([price for price in totals if price is not None])[0] if None not in totals else None
    if (
        p_over is None and payload.over_2_5_percent is not None
    ):  # the page's own chance, when it gives no odds
        p_over = payload.over_2_5_percent / 100
    p_btts = de_margin([payload.goal, payload.no_goal])[0] if payload.goal and payload.no_goal else None
    return [
        OddsRow(
            **source.model_dump(),
            home=home,
            away=away,
            bookmaker=payload.bookmaker,
            p_home=p_home,
            p_draw=p_draw,
            p_away=p_away,
            p_over=p_over,
            p_btts=p_btts,
        )
    ]


ODDS = Domain(
    "match_odds",
    MatchOddsPayload,
    OddsRow,
    _rows,
    Table(
        "odds",
        f"CREATE TEMP TABLE odds ({PROVENANCE_COLUMNS}, home VARCHAR, away VARCHAR, bookmaker VARCHAR, "
        "p_home DOUBLE, p_draw DOUBLE, p_away DOUBLE, p_over DOUBLE, p_btts DOUBLE)",
        "INSERT INTO odds VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    ),
)
