"""mvp-roles task 3.3: `collect` and `fantadamus collect` read only the page of the fact asked for, and both
pages by default (design C4; R1.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from fantadamus.cli import __main__ as cli
from fantadamus.core.clubs import Clubs
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.mcp.server import AdvisorServer
from fantadamus.mcp.tools import collect
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE, local_site, round_collector
from tests.collect_pages import FcoMatch, fco_round_page, stats_page
from tests.roles_data import stats_read

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[3]
REAL = Clubs.from_toml((ROOT / "config" / "clubs.toml").read_text(encoding="utf-8"))


async def test_tool_and_command_choose_the_fact(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    routes = {
        "/robots.txt": (404, {}, b""),
        ROUND_ROUTE: (200, HTML, fco_round_page(FcoMatch("Alfa", "Beta")).encode()),
        STATS_ROUTE: (200, HTML, stats_page(stats_read()["players"]).encode()),
    }
    with local_site(routes) as site:
        server = AdvisorServer(name="fantadamus-test")
        collector = round_collector(LakeStore(tmp_path / "lake"), site.base_url, tmp_path, statistics=True)
        collect.register(server, collector, CollectLog(tmp_path / "collect"))
        async with Client(server) as client:
            result = await client.call_tool("collect", {"fact": "player_season"})
        assert not result.is_error, result
        assert result.structured_content is not None
        assert [page["page"] for page in result.structured_content["pages"]] == ["statistics"]
        assert ROUND_ROUTE not in [path for path, _ in site.requests]

        # The command, on clubs config/clubs.toml knows.
        routes[ROUND_ROUTE] = (200, HTML, fco_round_page(FcoMatch("Inter", "Milan")).encode())
        routes[STATS_ROUTE] = (200, HTML, stats_page(stats_read(clubs=REAL)["players"]).encode())
        sources = tmp_path / "sources.toml"
        sources.write_text('allowed_hosts = ["127.0.0.1"]\n', encoding="utf-8")
        reading = tmp_path / "reading_list.toml"
        reading.write_text(
            f'[collector]\ncurrent_round = "{site.base_url}{ROUND_ROUTE}"\n'
            f'round = "{site.base_url}/probabili-formazioni/{{round}}-giornata"\n'
            f'statistics = "{site.base_url}{STATS_ROUTE}"\n',
            encoding="utf-8",
        )
        command = ["collect", "--lake", str(tmp_path / "cli" / "lake"), "--sources", str(sources)]
        command += ["--reading-list", str(reading)]
        assert cli.main([*command, "--fact", "player_season"]) == 0
        only = capsys.readouterr().out
        assert cli.main(command) == 0
        both = capsys.readouterr().out
    assert only == f"{site.base_url}{STATS_ROUTE}: stored season_stats {4 * len(REAL.names)}\n"
    assert f"{site.base_url}{ROUND_ROUTE}: stored" in both
    assert f"{site.base_url}{STATS_ROUTE}: unchanged" in both
