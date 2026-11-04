"""AT-7: `set_squad` resolves names, returns candidates and unknown names and stores nothing then, and
replaces the squad on a second call; a league-mate's squad is kept apart under its team name (R1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import CLASSIC, DEFAULT_ROOT
from fantadamus.league.squads import SquadStore
from tests.collect_harness import HTML, STATS_ROUTE, local_site, round_collector
from tests.collect_pages import stats_page
from tests.roles_data import squad_stats, stats_row
from tests.xy_harness import NOW, SetClock, send, set_classic, tools

pytestmark = pytest.mark.anyio

READ = NOW - dt.timedelta(hours=1)
PLAYERS = (
    ("Marco Rossi", "Alfa", "P", "Por", 8001),
    ("Luca Rossi", "Beta", "D", "Dc", 8002),
    ("Anna Bianchi", "Alfa", "C", "C", 8003),
    ("Carlo Verdi", "Beta", "A", "Pc", 8004),
    ("Dino Neri", "Gamma", "D", "Dc", 8005),
)


async def _known(client: Any) -> None:
    for name, club, role, mantra, player_id in PLAYERS:
        row = stats_row(club, role, mantra, player_id, name=name)
        assert not (await send(client, "submit_player_season", row, READ)).is_error


async def _squad(client: Any, *players: str, **options: Any) -> dict[str, Any]:
    result = await client.call_tool("set_squad", {"players": list(players), **options})
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


async def test_at7_set_squad(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    squads = SquadStore(store.root / "league")
    async with tools(store) as client:
        await set_classic(client)
        await _known(client)

        refused = await _squad(client, "Rossi", "Nessuno Mai", "Anna Bianchi")
        assert refused["status"] == "choose"
        assert {player["name"] for player in refused["unresolved"]["Rossi"]} == {"Marco Rossi", "Luca Rossi"}
        assert refused["unresolved"]["Nessuno Mai"] == []
        assert "Anna Bianchi" not in refused["unresolved"]
        assert refused["by_role"] == {}
        assert squads.get("user-1") is None  # nothing stored

        stored = await _squad(client, "Rossi (Alfa)", "Verdi", "Dino Neri", "Anna Bianchi")
        assert stored["status"] == "stored"
        assert stored["team"] == "mine"
        assert {
            role: [player["name"] for player in players] for role, players in stored["by_role"].items()
        } == {
            "P": ["Marco Rossi"],
            "D": ["Dino Neri"],
            "C": ["Anna Bianchi"],
            "A": ["Carlo Verdi"],
        }
        mine = squads.get("user-1")
        assert mine is not None
        assert {player.player_id for player in mine.players} == {8001, 8003, 8004, 8005}
        assert mine.saved_at == NOW

        await _squad(client, "Marco Rossi", "Verdi")  # a second call replaces the squad
        mine = squads.get("user-1")
        assert mine is not None
        assert {player.player_id for player in mine.players} == {8001, 8004}

        mate = await _squad(
            client, "Luca Rossi", "Dino Neri", team="Rivali FC"
        )  # a league-mate's is kept apart
        assert mate["team"] == "Rivali FC"
        theirs = squads.get("user-1", "rivali fc")  # however the name is written
        assert theirs is not None
        assert {player.player_id for player in theirs.players} == {8002, 8005}
        mine = squads.get("user-1")
        assert mine is not None
        assert {player.player_id for player in mine.players} == {8001, 8004}

        again = await _squad(client, "Anna Bianchi", "Bianchi")  # one player, listed twice
        assert again["status"] == "choose"
        assert set(again["unresolved"]) == {"Anna Bianchi", "Bianchi"}


async def test_at7_says_what_it_cannot_field(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        await _known(client)
        no_keeper = await _squad(client, "Verdi", "Dino Neri")
        assert no_keeper["status"] == "stored"
        assert no_keeper["warnings"] == ["No keeper: a lineup can't be fielded without one."]
        rules = {
            "format": "head_to_head",
            "thresholds": [66, 72],
            "bench_size": 7,
            "substitutions": 3,
            "substitution_mode": "same_role",
            "formations": ["3-4-3"],
        }
        await client.call_tool("set_league_rules", {"rules": {**CLASSIC.model_dump(), "lineup": rules}})
        short = await _squad(client, "Marco Rossi", "Luca Rossi", "Dino Neri", "Anna Bianchi", "Carlo Verdi")
        assert short["warnings"] == [
            "Can't field 3-4-3: it needs 3 defenders, 4 midfielders and 3 forwards, and the squad has "
            "2, 1 and 1."
        ]


async def test_at7_reads_the_statistics_page_if_nobody_is_known(tmp_path: Path) -> None:
    routes = {"/robots.txt": (404, {}, b""), STATS_ROUTE: (200, HTML, stats_page(squad_stats()).encode())}
    store, clock = LakeStore(tmp_path / "lake"), SetClock(NOW)
    with local_site(routes) as site:
        collector = round_collector(store, site.base_url, tmp_path / "robots", clock=clock, statistics=True)
        log = CollectLog(tmp_path / "collect")
        async with tools(store, clock=clock, collector=collector, collect_log=log) as client:
            await set_classic(client)
            stored = await _squad(client, "Alfa Uno", "Beta Nove")
    assert stored["status"] == "stored", stored
    assert [path for path, _ in site.requests].count(STATS_ROUTE) == 1
    assert log.last_attempt(NOW, "statistics") == NOW


async def test_at7_without_any_player_it_says_what_to_read(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        result = await _squad(client, "Marco Rossi")
    assert result["status"] == "refresh"
    assert [item["fact"] for item in result["refresh"]] == ["player_season"]
    assert "statistiche-serie-a" in result["refresh"][0]["pages"][0]


def test_at7_squads_sit_in_the_private_folder() -> None:
    assert Path("data/local/league") == DEFAULT_ROOT
