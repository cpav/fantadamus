"""mvp-collect task 4.3: the `collect` tool and `fantadamus collect`, each run appended to the collection log,
and `--report` showing the last run and when each page last worked (design C9, C10; R1.2, R8.2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from mcp import Client

from fantadamus.cli import __main__ as cli
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.mcp.server import AdvisorServer
from fantadamus.mcp.tools import collect
from fantadamus.web.collector import ROUND_FACTS, CollectReport, PageReport
from tests.collect_harness import HTML, ROUND_ROUTE, local_site, round_collector
from tests.collect_pages import FcoMatch, fco_round_page

pytestmark = pytest.mark.anyio

PAGE = fco_round_page(FcoMatch("Alfa", "Beta")).encode()  # the test clubs
REAL_CLUBS = fco_round_page(
    FcoMatch("Inter", "Milan")
).encode()  # clubs config/clubs.toml knows, for the command
URL = "https://www.example.org/probabili-formazioni/ultima-giornata"


async def test_tool_and_command_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    routes = {"/robots.txt": (404, {}, b""), ROUND_ROUTE: (200, HTML, PAGE)}
    with local_site(routes) as site:
        log = CollectLog(tmp_path / "collect")
        server = AdvisorServer(name="fantadamus-test")
        collect.register(
            server, round_collector(LakeStore(tmp_path / "lake"), site.base_url, tmp_path / "robots"), log
        )
        async with Client(server) as client:
            result = await client.call_tool("collect", {})
        assert not result.is_error, result
        assert result.structured_content is not None
        assert result.structured_content["pages"][0]["outcome"] == "stored"
        last = log.last()
        assert last is not None
        assert last.pages[0].outcome == "stored"

        routes[ROUND_ROUTE] = (200, HTML, REAL_CLUBS)
        sources = tmp_path / "sources.toml"
        sources.write_text('allowed_hosts = ["127.0.0.1"]\n', encoding="utf-8")
        reading = tmp_path / "reading_list.toml"
        reading.write_text(
            f'[collector]\ncurrent_round = "{site.base_url}{ROUND_ROUTE}"\n'
            f'round = "{site.base_url}/probabili-formazioni/{{round}}-giornata"\n',
            encoding="utf-8",
        )
        command = ["collect", "--lake", str(tmp_path / "cli" / "lake"), "--sources", str(sources)]
        assert cli.main([*command, "--reading-list", str(reading)]) == 0
    out = capsys.readouterr().out
    assert f"{site.base_url}{ROUND_ROUTE}: stored fixtures 1, odds 1, outlet_views 112" in out
    assert CollectLog(tmp_path / "cli" / "collect").last() is not None  # the command logs next to its lake


def test_report_shows_last_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = CollectLog(tmp_path / "collect")
    worked_at = dt.datetime(2026, 10, 30, 18, 0, tzinfo=dt.UTC)
    log.append(
        CollectReport(
            started_at=worked_at,
            finished_at=worked_at,
            round=None,
            pages=[PageReport(url=URL, outcome="stored", fetched_at=worked_at, stored={"fixtures": 10})],
        )
    )
    blocked_at = dt.datetime(2026, 10, 31, 9, 0, tzinfo=dt.UTC)
    reason = "www.example.org answered 429; stopped for this run"
    log.append(
        CollectReport(
            started_at=blocked_at,
            finished_at=blocked_at,
            round=10,
            pages=[PageReport(url=URL, outcome="blocked", reason=reason, for_claude=list(ROUND_FACTS))],
        )
    )
    assert cli.main(["collect", "--report", "--lake", str(tmp_path / "lake")]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Last run: 2026-10-31 09:00 UTC, round 10",
        f"{URL}: blocked ({reason})",
        "  for Claude, through read_page: fixtures, probable_lineups, official_lineups, match_odds",
        "Last worked:",
        f"  {URL}: 2026-10-30 18:00 UTC",
    ]
    assert cli.main(["collect", "--report", "--lake", str(tmp_path / "empty" / "lake")]) == 0
    assert capsys.readouterr().out == "No collection has run yet.\n"
