"""Task 8.5: the `fantadamus` command line (R16.1, R16.6)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver import MCPServer

from fantadamus.cli import __main__ as cli

ROOT = Path(__file__).resolve().parents[2]


def test_golden_difference_fails_with_a_readable_diff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    golden = tmp_path / "golden.json"
    golden.write_text('[\n  {"club": "Squadra Zeta"}\n]\n', encoding="utf-8")
    code = cli.main(["skeleton", "run", "--lake", str(tmp_path / "lake"), "--golden", str(golden)])
    err = capsys.readouterr().err
    assert code == 1
    assert "differs from the golden file" in err
    assert '-  {"club": "Squadra Zeta"}' in err
    assert '+    "club": "Squadra Alfa",' in err


def test_run_without_golden_prints_the_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["skeleton", "run", "--lake", str(tmp_path / "lake")]) == 0
    assert json.loads(capsys.readouterr().out)["rows"]


def test_rejected_fixture_rows_fail_the_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fixture = tmp_path / "rows.json"
    rows = json.loads((ROOT / "tests" / "fixtures" / "skeleton" / "rows.json").read_text(encoding="utf-8"))
    rows["rows"].append({"player_id": 0})
    fixture.write_text(json.dumps(rows), encoding="utf-8")
    code = cli.main(["skeleton", "run", "--lake", str(tmp_path / "lake"), "--fixture", str(fixture)])
    assert code == 1
    assert "rejected" in capsys.readouterr().err


def test_serve_runs_the_server_on_stdio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, Any] = {}

    def fake_run(self: MCPServer, transport: str = "stdio", **_: Any) -> None:
        seen["transport"] = transport
        seen["tools"] = sorted(tool.name for tool in asyncio.run(self.list_tools()))

    monkeypatch.setattr(MCPServer, "run", fake_run)
    assert cli.main(["serve", "--lake", str(tmp_path / "lake"), "--user", "user-1"]) == 0
    assert seen == {"transport": "stdio", "tools": ["get_skeleton_summary", "submit_skeleton_rows"]}


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        cli.main([])
    assert exited.value.code == 2
    assert "usage: fantadamus" in capsys.readouterr().err
