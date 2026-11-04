"""A whole synthetic round for `best_lineup`'s tests: four clubs' players on the statistics page, the round
page with two matches, the table and the takers, through the real tools. Clubs and players are invented."""

from __future__ import annotations

import contextlib
import datetime as dt
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import Client

from fantadamus.contracts.types import Role
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import CLASSIC
from fantadamus.league.squads import SquadStore
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE, FakeWeb, round_collector
from tests.collect_pages import FcoMatch, fco_round_page, stats_page
from tests.lineup_data import FORMATIONS
from tests.roles_data import stats_row
from tests.xy_harness import NOW, TAKERS, TEAM_TABLE, WORDS, SetClock, send, tools

CLUBS = ("Alfa", "Beta", "Gamma", "Delta")
LINES: dict[str, tuple[Role, str]] = {
    "Uno": ("P", "Por"),
    "Due": ("D", "Dc"),
    "Tre": ("D", "Dc"),
    "Quattro": ("D", "Dd"),
    "Cinque": ("D", "Ds"),
    "Sei": ("C", "C"),
    "Sette": ("C", "M"),
    "Otto": ("C", "C"),
    "Nove": ("A", "Pc"),
    "Dieci": ("A", "A"),
    "Undici": ("A", "W"),
    "Dodici": ("C", "C"),
    "Tredici": ("A", "A"),
    "Quattordici": ("D", "Dc"),
}
READ = NOW - dt.timedelta(hours=1)
MATCHES = (FcoMatch("Alfa", "Beta"), FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00"))
LEAGUE: dict[str, Any] = {
    "format": "head_to_head",
    "thresholds": [66, 72],
    "bench_size": 12,
    "substitutions": 5,
    "substitution_mode": "same_role",
    "formations": FORMATIONS,
}
SQUAD = [
    "Alfa Uno",
    "Gamma Uno",
    "Beta Uno",
    *(f"{club} {word}" for club in ("Alfa", "Gamma") for word in ("Due", "Tre", "Quattro", "Cinque")),
    *(f"{club} {word}" for club in ("Alfa", "Gamma") for word in ("Sei", "Sette", "Otto", "Dodici")),
    *(f"{club} {word}" for club in ("Beta", "Delta") for word in ("Nove", "Dieci", "Undici")),
]


def player_id(club: str, word: str) -> int:
    return 8000 + 100 * CLUBS.index(club) + WORDS.index(word)


def rows(**changes: dict[str, Any]) -> list[dict[str, Any]]:
    """Every player's row on the statistics page; `changes` rewrite one, as `Alfa_Nove={"goals": 5}`."""
    found = []
    for club in CLUBS:
        for word in WORDS:
            role, mantra = LINES[word]
            found.append(
                stats_row(club, role, mantra, player_id(club, word), name=f"{club} {word}")
                | changes.get(f"{club}_{word}", {})
            )
    return found


@dataclass
class Round:
    client: Client
    store: LakeStore
    clock: SetClock
    web: FakeWeb
    routes: dict[str, Response | Exception]
    squads: SquadStore
    log: DecisionLog
    base: str = "https://example.org"

    def round_page(self, *matches: FcoMatch) -> None:
        self.routes[f"{self.base}{ROUND_ROUTE}"] = Response(200, HTML, fco_round_page(*matches).encode())

    async def ask(self, **options: Any) -> dict[str, Any]:
        result = await self.client.call_tool("best_lineup", options)
        assert not result.is_error, result
        content: dict[str, Any] | None = result.structured_content
        assert content is not None
        return content

    async def set_squad(self, *names: str, **options: Any) -> dict[str, Any]:
        result = await self.client.call_tool("set_squad", {"players": list(names or SQUAD), **options})
        assert not result.is_error, result
        content: dict[str, Any] | None = result.structured_content
        assert content is not None
        assert content["status"] == "stored", content
        return content

    async def set_rules(self, **lineup: Any) -> None:
        rules = CLASSIC.model_dump() | {"lineup": LEAGUE | lineup}
        result = await self.client.call_tool("set_league_rules", {"rules": rules})
        assert not result.is_error, result


@contextlib.asynccontextmanager
async def a_round(
    tmp_path: Path,
    *,
    matches: Sequence[FcoMatch] = MATCHES,
    players: Sequence[dict[str, Any]] | None = None,
    league: bool = True,
    squad: bool = True,
    table: bool = True,
    rounds: int = 500,
) -> AsyncIterator[Round]:
    """The tools over a lake that holds the table and the takers; the collector reads the pages when asked."""
    store, clock = LakeStore(tmp_path / "lake"), SetClock(NOW)
    base = "https://example.org"
    routes: dict[str, Response | Exception] = {
        f"{base}/robots.txt": Response(404, {}, b""),
        f"{base}{ROUND_ROUTE}": Response(200, HTML, fco_round_page(*matches).encode()),
        f"{base}{STATS_ROUTE}": Response(200, HTML, stats_page(players or rows()).encode()),
    }
    web = FakeWeb(routes)
    collector = round_collector(
        store, base, tmp_path / "robots", transport=web, hosts=["example.org"], clock=clock, statistics=True
    )
    log = CollectLog(tmp_path / "collect")
    async with tools(
        store, clock=clock, collector=collector, collect_log=log, hosts=("example.org",), lineup_rounds=rounds
    ) as client:
        here = Round(
            client,
            store,
            clock,
            web,
            routes,
            SquadStore(store.root / "league"),
            DecisionLog(store.root / "decisions"),
        )
        if table:
            for tool, payload in (("submit_team_season", TEAM_TABLE), ("submit_penalty_takers", TAKERS)):
                assert not (await send(client, tool, payload, READ)).is_error
        if league:
            await here.set_rules()
        if squad:
            await here.set_squad()
        yield here
