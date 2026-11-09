"""mvp-review task 1.1: the three new columns reach silver unchanged, each in its own column, and a read
stored before them reads them as unknown (design C1; R2.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from fantadamus.contracts.xy.season import SeasonStatsPayload
from fantadamus.core.clock import fixed_clock
from fantadamus.domains import facts
from fantadamus.domains.season.silver import SEASON_STATS
from fantadamus.lake.duckdb_store import LakeStore
from tests.roles_data import stats_read
from tests.xy_harness import CLUBS

STATS = "https://example.org/statistiche-serie-a"
READ = dt.datetime(2026, 11, 2, 9, 0, tzinfo=dt.UTC)
LATER = dt.datetime(2026, 11, 3, 9, 0, tzinfo=dt.UTC)


def _store(store: LakeStore, players: list[dict[str, Any]], at: dt.datetime) -> None:
    facts.submit_many(
        store,
        SEASON_STATS,
        [facts.Submission(SeasonStatsPayload.model_validate({"players": players}))],
        source_url=STATS,
        captured_at=at,
        allowed_hosts=["example.org"],
        clock=fixed_clock(at),
        submitted_by="collector",
        clubs=CLUBS,
    )


def test_the_three_columns_are_kept(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    players = stats_read()["players"]
    keeper = next(index for index, player in enumerate(players) if player["role"] == "P")
    players[keeper] |= {"fantasy_average": 4.25, "penalties_saved": 2, "red_cards": 1}
    old = [
        {
            key: value
            for key, value in player.items()
            if key not in ("fantasy_average", "penalties_saved", "red_cards")
        }
        for player in stats_read()["players"]
    ]
    _store(store, old, READ)
    _store(store, players, LATER)
    rows = facts.read_silver(store, SEASON_STATS)
    stored = next(
        row for row in rows if row.player_id == players[keeper]["player_id"] and row.captured_at == LATER
    )
    assert (stored.fantasy_average, stored.penalties_saved, stored.red_cards) == (4.25, 2, 1)
    before = [row for row in rows if row.captured_at == READ]
    assert before
    assert all(
        (row.fantasy_average, row.penalties_saved, row.red_cards) == (None, None, None) for row in before
    )
