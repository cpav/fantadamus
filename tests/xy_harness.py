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
from fantadamus.mcp.tools import submit

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
    """The submit tools over `store`, accepting pages from example.org, as user `user-1`."""
    server = MCPServer(name="fantadamus-test")
    submit.register(
        server,
        store,
        allowed_hosts=["example.org"],
        clock=fixed_clock(now),
        submitted_by="user-1",
        clubs=CLUBS,
    )
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
