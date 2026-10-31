"""The `fantadamus` command line: `serve` runs the advisor on stdio (mvp-x-or-y R13.1)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver import MCPServer

from fantadamus.cli import __main__ as cli


def test_serve_runs_the_server_on_stdio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, Any] = {}

    def fake_run(self: MCPServer, transport: str = "stdio", **_: Any) -> None:
        seen["transport"] = transport
        seen["tools"] = sorted(tool.name for tool in asyncio.run(self.list_tools()))

    monkeypatch.setattr(MCPServer, "run", fake_run)
    assert cli.main(["serve", "--lake", str(tmp_path / "lake"), "--user", "user-1"]) == 0
    assert seen == {
        "transport": "stdio",
        "tools": [
            "collect",
            "compare_players",
            "read_page",
            "set_league_rules",
            "submit_fixtures",
            "submit_match_odds",
            "submit_official_lineup",
            "submit_outlet_lineup",
            "submit_penalty_takers",
            "submit_player_season",
            "submit_probable_lineups",
            "submit_team_season",
        ],
    }


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        cli.main([])
    assert exited.value.code == 2
    assert "usage: fantadamus" in capsys.readouterr().err
