"""Task 7.4: what `fantadamus serve` gives Claude Desktop (design C13; R13.1, R13.2)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from mcp.server.mcpserver import MCPServer

from fantadamus.core.clock import fixed_clock
from fantadamus.core.clubs import Clubs
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.server import build_advisor, load_instructions
from fantadamus.mcp.tools.compare import load_reading_list
from tests.xy_harness import NOW, ROOT

pytestmark = pytest.mark.anyio


def _server(tmp_path: Path) -> MCPServer:
    return build_advisor(
        LakeStore(tmp_path / "lake"),
        allowed_hosts=["example.org"],
        clubs=Clubs.from_toml((ROOT / "config" / "clubs.toml").read_text(encoding="utf-8")),
        rules=RulesStore(tmp_path / "league"),
        log=DecisionLog(tmp_path / "decisions"),
        reading=load_reading_list(ROOT / "config" / "reading_list.toml"),
        user="owner",
        clock=fixed_clock(NOW),
        instructions=load_instructions(ROOT / "docs" / "agent-prompt.md"),
    )


async def test_served_tools(tmp_path: Path) -> None:
    tools = {tool.name: tool for tool in await _server(tmp_path).list_tools()}
    assert sorted(tools) == [
        "compare_players",
        "set_league_rules",
        "submit_fixtures",
        "submit_match_odds",
        "submit_official_lineup",
        "submit_penalty_takers",
        "submit_player_season",
        "submit_probable_lineups",
        "submit_team_season",
    ]  # the skeleton's tools aren't served
    for fact, entry in load_reading_list(ROOT / "config" / "reading_list.toml").items():
        sites = re.findall(r"https://(?:www\.|it\.)?([a-z-]+)\.", " ".join(entry.pages))
        sites += re.findall(r"site:(?:www\.)?([a-z-]+)\.", " ".join(entry.search))
        description = (tools[entry.submit_tool].description or "").lower().replace("-", "")
        assert any(site.replace("-", "") in description for site in sites), fact


def test_instructions_are_agent_prompt(tmp_path: Path) -> None:
    instructions = _server(tmp_path).instructions
    assert instructions is not None
    assert instructions.startswith("You are a Fantacalcio advisor.")
    assert "**MVP only: collecting data**" in instructions
    assert "Status:" not in instructions


async def test_prompt_names_only_served_tools(tmp_path: Path) -> None:
    server = _server(tmp_path)
    served = {tool.name for tool in await server.list_tools()}
    named = set(re.findall(r"`([a-z]+(?:_[a-z]+)+)`", server.instructions or ""))
    assert "compare_players" in named
    assert named <= served, named - served


def test_prompt_explains_fallbacks(tmp_path: Path) -> None:
    """mvp-x-or-y task 10.1 (R11.4): Claude works down a plan item's pages and search hints."""
    instructions = _server(tmp_path).instructions or ""
    assert "next listed page" in instructions
    assert "search hint" in instructions
    assert "never ask the user to paste" in instructions


async def test_schemas_spell_out_every_field(tmp_path: Path) -> None:
    """mvp-x-or-y task 11.1: Claude Desktop guessed payload shapes it had to reach through `$ref`s, so every
    schema is served whole, and each nested submit tool shows its shape."""
    tools = {tool.name: tool for tool in await _server(tmp_path).list_tools()}
    for name, tool in tools.items():
        assert "$ref" not in json.dumps(tool.input_schema), name
    lineup = tools["submit_probable_lineups"].input_schema["properties"]["payload"]["properties"]
    assert "starters" in lineup["home_team"]["properties"]
    assert (
        "percent"
        in lineup["home_team"]["properties"]["ballottaggi"]["items"]["properties"]["players"]["items"][
            "properties"
        ]
    )
    shapes = {
        "submit_fixtures": '"kickoff_at"',
        "submit_probable_lineups": '"home_team"',
        "submit_official_lineup": '"home_team"',
        "submit_team_season": '"goals_for"',
        "submit_penalty_takers": '"takers"',
    }
    for name, field in shapes.items():
        assert field in (tools[name].description or ""), name
