"""Shared by the `mvp-x-or-y` tests: synthetic pages, invented clubs, the tools on an in-process client."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult

from fantadamus.core.clock import fixed_clock
from fantadamus.core.clubs import Clubs
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.tools import league, submit

PAGES = Path(__file__).resolve().parent / "fixtures" / "xy"
URL = "https://example.org/page"
NOW = dt.datetime(2026, 10, 26, 10, 0, tzinfo=dt.UTC)
CLUBS = Clubs.from_toml(
    "".join(f'[clubs.{key}]\nname = "{key.title()}"\n' for key in ("alfa", "beta", "gamma", "delta"))
)


def page(name: str) -> dict[str, Any]:
    """A synthetic page from `tests/fixtures/xy/`, as Claude would submit it."""
    loaded: dict[str, Any] = json.loads((PAGES / f"{name}.json").read_text(encoding="utf-8"))
    return loaded


@contextlib.asynccontextmanager
async def tools(store: LakeStore, now: dt.datetime = NOW) -> AsyncIterator[Client]:
    """The tools over `store`, accepting pages from example.org, as user `user-1`; league rules are kept
    under `<lake>/league`."""
    server = MCPServer(name="fantadamus-test")
    clock = fixed_clock(now)
    submit.register(
        server, store, allowed_hosts=["example.org"], clock=clock, submitted_by="user-1", clubs=CLUBS
    )
    league.register(server, RulesStore(store.root / "league"), user="user-1", clock=clock)
    async with Client(server) as client:
        yield client


async def send(
    client: Client, tool: str, payload: dict[str, Any], captured_at: dt.datetime, url: str = URL
) -> CallToolResult:
    """Call a submit tool the way Claude does: the payload and where and when the page was read."""
    return await client.call_tool(
        tool, {"payload": payload, "source_url": url, "captured_at": captured_at.isoformat()}
    )


def error_text(result: CallToolResult) -> str:
    assert result.is_error
    return " ".join(getattr(block, "text", "") for block in result.content)


def probable(outlet: str, **teams: dict[str, Any]) -> dict[str, Any]:
    """The synthetic probable lineup as `outlet` sees it, with `home_team` or `away_team` replaced."""
    payload = page("probable_lineup") | {"outlet": outlet}
    return payload | teams


def alfa_team(nove: str) -> dict[str, Any]:
    """Alfa's probable team with Alfa Nove as a `starter`, in a 50/50 `ballottaggio`, on the `bench` or
    `unavailable`. The eleven starters stay eleven."""
    team: dict[str, Any] = page("probable_lineup")["home_team"]
    if nove != "starter":
        team["starters"] = [name for name in team["starters"] if name != "Alfa Nove"] + ["Alfa Dodici"]
        team["ballottaggi"] = []
        team["bench"] = ["Alfa Tredici"]
    if nove == "ballottaggio":
        team["ballottaggi"] = [
            {"players": [{"name": "Alfa Nove", "percent": 50}, {"name": "Alfa Dodici", "percent": 50}]}
        ]
    elif nove in {"bench", "unavailable"}:
        team[nove].append("Alfa Nove")
    return team
