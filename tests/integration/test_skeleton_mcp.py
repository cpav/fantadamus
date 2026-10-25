"""Task 8.4: the skeleton's MCP tools through an in-process client, without network (R16.10 to R16.13)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from mcp import Client

from fantadamus.core.clock import fixed_clock
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.mcp.server import build_server

pytestmark = pytest.mark.anyio

T0 = dt.datetime(2026, 10, 25, 10, 0, tzinfo=dt.UTC)
ROWS = [
    {"player_id": 1, "name": "Giocatore Uno", "club": "Squadra Alfa", "role": "A"},
    {"player_id": 2, "name": "Giocatore Due", "club": "Squadra Beta", "role": "D"},
]


def _client(root: Path) -> Client:
    server = build_server(
        LakeStore(root), allowed_hosts=["example.org"], clock=fixed_clock(T0), submitted_by="user-1"
    )
    return Client(server, raise_exceptions=True)


async def test_submit_then_read(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        submitted = await client.call_tool(
            "submit_skeleton_rows",
            {
                "rows": ROWS,
                "source_url": "https://example.org/skeleton",
                "captured_at": "2026-10-25T09:00:00Z",
            },
        )
        assert not submitted.is_error
        assert submitted.structured_content is not None
        assert submitted.structured_content["accepted"] == 2
        assert submitted.structured_content["rejected"] == []
        assert submitted.structured_content["bronze_id"]

        summary = await client.call_tool("get_skeleton_summary", {})
        assert not summary.is_error
        assert summary.structured_content == {
            "rows": [
                {
                    "club": "Squadra Alfa",
                    "role": "A",
                    "n_players": 1,
                    "source_urls": ["https://example.org/skeleton"],
                },
                {
                    "club": "Squadra Beta",
                    "role": "D",
                    "n_players": 1,
                    "source_urls": ["https://example.org/skeleton"],
                },
            ]
        }


async def test_off_allowlist_rejected_nothing_written(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        result = await client.call_tool(
            "submit_skeleton_rows",
            {
                "rows": ROWS,
                "source_url": "https://example.org.evil.example/x",
                "captured_at": "2026-10-25T09:00:00Z",
            },
        )
        summary = await client.call_tool("get_skeleton_summary", {})
    assert result.structured_content == {
        "accepted": 0,
        "rejected": [
            {"index": None, "reason": "source_url host example.org.evil.example is not on the allowlist"}
        ],
        "bronze_id": None,
    }
    assert summary.structured_content == {"rows": []}
    assert not any(tmp_path.rglob("*"))


async def test_naive_timestamp_is_a_tool_error(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        result = await client.call_tool(
            "submit_skeleton_rows",
            {"rows": ROWS, "source_url": "https://example.org/x", "captured_at": "2026-10-25T09:00:00"},
        )
    assert result.is_error
    assert not any(tmp_path.rglob("*"))


async def test_tools_describe_their_inputs(tmp_path: Path) -> None:
    async with _client(tmp_path) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    assert set(tools) == {"submit_skeleton_rows", "get_skeleton_summary"}
    submit = tools["submit_skeleton_rows"]
    assert submit.description
    assert "allowlist" in submit.description
    assert submit.input_schema["required"] == ["rows", "source_url", "captured_at"]
    assert submit.input_schema["properties"]["captured_at"]["format"] == "date-time"
