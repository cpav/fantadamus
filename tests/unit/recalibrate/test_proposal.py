"""The reliability gap, by hand, and the statistics read that goes with the table (mvp-recalibrate design C5,
C8)."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.domains.calibration import Bucket, Scored
from fantadamus.domains.recalibration import reliability_gap, season_read
from fantadamus.domains.season.silver import PlayerSeasonRow, TeamSeasonRow
from tests.cards_data import source


def test_the_reliability_gap_by_hand() -> None:
    """30 players said 15% and 5% started; 10 said 95% and 90% did: (30 x 0.10 + 10 x 0.05) / 40."""
    scored = Scored(
        chance="Starting",
        count=40,
        brier=0.1,
        baseline=0.2,
        buckets=[
            Bucket(low=0.1, high=0.2, count=30, said=0.15, happened=0.05),
            Bucket(low=0.9, high=1.0, count=10, said=0.95, happened=0.90),
        ],
    )
    assert reliability_gap(scored) == pytest.approx((30 * 0.10 + 10 * 0.05) / 40)


T = dt.datetime(2026, 11, 4, 12, 32, tzinfo=dt.UTC)
"""When the table was last read."""


def _stats(at: dt.datetime) -> list[PlayerSeasonRow]:
    return [
        PlayerSeasonRow(
            **source("https://example.org/statistiche", at).model_dump(),
            player_id=player_id,
            name=f"Player {player_id}",
            club="alfa",
            role="D",
            mantra_role=None,
            appearances=9,
            rated_appearances=9,
            average_rating=6.0,
            goals=0,
            assists=0,
            yellow_cards=1,
            penalties_scored=0,
            penalties_taken=0,
        )
        for player_id in (1, 2)
    ]


def _table(club: str, at: dt.datetime) -> TeamSeasonRow:
    return TeamSeasonRow(
        **source("https://example.org/classifica", at).model_dump(),
        club=club,
        played=10,
        goals_for=10,
        goals_against=10,
    )


def test_the_read_that_goes_with_the_table() -> None:
    """The penalties per match need the statistics and the table to count the same matches: the read stored
    last before the table's, or in the same run just after it, not a later one."""
    stats = [
        *_stats(T - dt.timedelta(days=3)),
        *_stats(T + dt.timedelta(minutes=10)),
        *_stats(T + dt.timedelta(days=2)),
    ]
    tables = [_table("alfa", T - dt.timedelta(days=7)), _table("alfa", T), _table("beta", T)]
    later = T + dt.timedelta(days=3)
    players, teams = season_read(stats, tables, as_of=later)
    assert {row.captured_at for row in players} == {T + dt.timedelta(minutes=10)}
    assert len(players) == 2
    assert sorted((row.club, row.captured_at) for row in teams) == [("alfa", T), ("beta", T)]
    unchanged, _ = season_read(stats[:2], tables, as_of=later)  # the page unchanged since: that read holds
    assert {row.captured_at for row in unchanged} == {T - dt.timedelta(days=3)}
    alone, none = season_read(stats, [], as_of=later)  # without a table, the latest read
    assert {row.captured_at for row in alone} == {T + dt.timedelta(days=2)}
    assert none == []
    assert season_read([], tables, as_of=later)[0] == []
    hour = [*_stats(T - dt.timedelta(days=3)), *_stats(T + dt.timedelta(hours=1))]  # the run's last minute
    assert {row.captured_at for row in season_read(hour, tables, as_of=later)[0]} == {
        T + dt.timedelta(hours=1)
    }
