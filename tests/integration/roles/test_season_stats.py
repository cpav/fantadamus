"""mvp-roles tasks 1.2 and 1.3: one bronze record per read of the statistics page, the whole-read check, and
gold reading both season tables as one (design C2; R1.1, R1.6, R6.1)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from fantadamus.contracts.xy.season import PlayerSeasonPayload, SeasonStatsPayload
from fantadamus.core.clock import fixed_clock
from fantadamus.domains import facts
from fantadamus.domains.season import gold
from fantadamus.domains.season.silver import PLAYER_SEASONS, SEASON_STATS, read_player_seasons
from fantadamus.lake.duckdb_store import LakeStore
from tests.roles_data import stats_read, stats_row
from tests.xy_harness import CLUBS, page

STATS = "https://example.org/statistiche-serie-a"
PROFILE = "https://example.org/serie-a/squadre/alfa/alfa-nove/9001"
READ = dt.datetime(2026, 11, 2, 9, 0, tzinfo=dt.UTC)
LATER = dt.datetime(2026, 11, 3, 9, 0, tzinfo=dt.UTC)
RECEIVED = dt.datetime(2026, 11, 3, 10, 0, tzinfo=dt.UTC)


def _store(store: LakeStore, read: dict[str, Any], at: dt.datetime = READ) -> facts.Stored:
    payload = SeasonStatsPayload.model_validate_json(json.dumps(read))
    return facts.submit_many(
        store,
        SEASON_STATS,
        [facts.Submission(payload)],
        source_url=STATS,
        captured_at=at,
        allowed_hosts=["example.org"],
        clock=fixed_clock(RECEIVED),
        submitted_by="collector",
        clubs=CLUBS,
    )


def _profile(store: LakeStore, profile: dict[str, Any], at: dt.datetime) -> None:
    payload = PlayerSeasonPayload.model_validate_json(json.dumps(profile))
    facts.submit_many(
        store,
        PLAYER_SEASONS,
        [facts.Submission(payload)],
        source_url=PROFILE,
        captured_at=at,
        allowed_hosts=["example.org"],
        clock=fixed_clock(RECEIVED),
        submitted_by="user-1",
        clubs=CLUBS,
    )


def test_one_record_per_read(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    read = stats_read()
    stored = _store(store, read)
    assert [receipt.rows for receipt in stored.receipts] == [len(read["players"])]
    assert len(store.read_bronze("season_stats")) == 1
    rows = facts.read_silver(store, SEASON_STATS)
    keepers = {row.club: row.goals_conceded for row in rows if row.role == "P"}
    assert keepers == dict.fromkeys(CLUBS.names, 9)
    assert {row.source_url for row in rows} == {STATS}


def test_incomplete_read_refused(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    unknown = stats_read()
    unknown["players"].append(stats_row("Omega", "A", "Pc", 7999))
    for read, reason in (
        (stats_read(without=("Gamma",)), "the read has no players of Gamma"),
        (stats_read(without=(("Beta", "P"),)), "the read has no keeper of Beta"),
        (unknown, "unknown club 'Omega'"),
    ):
        stored = _store(store, read)
        assert not stored.receipts
        assert len(stored.rejections) == 1
        assert reason in stored.rejections[0].reason
    assert store.read_bronze("season_stats") == []


def test_every_player_known(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    read = stats_read()
    _store(store, read)
    known = gold.known_players(read_player_seasons(store), READ)
    assert sorted(player.player_id for player in known) == sorted(row["player_id"] for row in read["players"])


def test_newest_figures_win(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    _profile(store, page("player_season"), READ - dt.timedelta(days=1))
    read = stats_read()
    read["players"].append(stats_row("Alfa", "A", "Pc", 9001, name="Alfa Nove", goals=6))
    _store(store, read)
    _profile(store, page("player_season") | {"goals": 7}, LATER)
    rows = read_player_seasons(store)
    on = {at: gold.player_form(rows, 9001, at) for at in (READ - dt.timedelta(hours=1), READ, LATER)}
    assert {at: (form.goals, form.source_url) for at, form in on.items() if form} == {
        READ - dt.timedelta(hours=1): (5, PROFILE),
        READ: (6, STATS),
        LATER: (7, PROFILE),
    }
