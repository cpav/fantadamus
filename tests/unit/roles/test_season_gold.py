"""mvp-roles task 5.2: the league's goals per team per match, which sets an average keeper's skill (design C7;
R3.3)."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.domains.season.gold import league_goals_per_match
from fantadamus.domains.season.silver import TeamSeasonRow
from fantadamus.engine.constants import LEAGUE_GOALS_PER_MATCH

READ = dt.datetime(2026, 11, 3, 8, 0, tzinfo=dt.UTC)
TABLE = "https://www.fantacalcio.it/serie-a/classifica"
WIKI = "https://it.wikipedia.org/wiki/Serie_A_2026-2027"


def _row(club: str, played: int, goals: int, url: str = TABLE) -> TeamSeasonRow:
    return TeamSeasonRow(
        source_url=url,
        captured_at=READ,
        content_sha256="0" * 64,
        club=club,
        played=played,
        goals_for=goals,
        goals_against=goals,
    )


def test_league_goals_per_match() -> None:
    rows = [_row("alfa", 8, 14), _row("beta", 8, 10), _row("alfa", 9, 99, WIKI)]  # the better source counts
    assert league_goals_per_match(rows, READ) == pytest.approx(24 / 16)
    assert league_goals_per_match([_row("alfa", 0, 0)], READ) == LEAGUE_GOALS_PER_MATCH  # no table yet
    assert league_goals_per_match(rows, READ - dt.timedelta(days=1)) == LEAGUE_GOALS_PER_MATCH  # as of then
