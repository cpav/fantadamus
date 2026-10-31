"""mvp-collect task 3.2: `read_page` hands Claude a listed page's text, then Claude submits its facts (design
C3.2; R3.2, R3.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.core.clock import fixed_clock
from fantadamus.domains.facts import read_silver
from fantadamus.domains.season.silver import TEAM_SEASONS
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.mcp.tools.compare import ReadingItem
from fantadamus.web import text
from fantadamus.web.fetch import Fetcher, Response
from tests.collect_harness import FakeTime, FakeWeb, page_tools
from tests.xy_harness import error_text

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)
HTML = {"Content-Type": "text/html; charset=utf-8"}
READING = {
    "team_season": ReadingItem(
        need="N5", submit_tool="submit_team_season", pages=["https://example.org/classifica"]
    ),
    "player_season": ReadingItem(
        need="N5",
        submit_tool="submit_player_season",
        search=["{player} site:example.org"],
        patterns=["https://example.org/squadre/{club}/{player}/{id}"],
    ),
}
TABLE = (
    b"<html><body><nav><a href='/'>Home</a></nav><main><h1>Classifica</h1><table>"
    b"<tr><th>Squadra</th><th>G</th><th>Gf</th><th>Gs</th></tr>"
    b"<tr><td><a href='/squadre/alfa/nove/9'>Alfa</a></td><td>8</td><td>14</td><td>9</td></tr>"
    b"<tr><td><a href='/squadre/alfa'>Beta</a></td><td>8</td><td>10</td><td>11</td></tr>"
    b"</table></main></body></html>"
)


def _fetcher(web: FakeWeb, tmp_path: Path) -> Fetcher:
    time = FakeTime()
    return Fetcher(
        allowed_hosts=["example.org"],
        clock=fixed_clock(READ),
        monotonic=time.monotonic,
        sleep=time.sleep,
        transport=web,
        robots_cache=tmp_path / "robots",
    )


async def test_read_then_submit(tmp_path: Path) -> None:
    web = FakeWeb(
        {
            "https://example.org/robots.txt": Response(404, {}, b""),
            "https://example.org/classifica": Response(200, HTML, TABLE),
        }
    )
    store = LakeStore(tmp_path / "lake")
    async with page_tools(store, READING, _fetcher(web, tmp_path), ["example.org"]) as client:
        result = await client.call_tool("read_page", {"url": "https://example.org/classifica"})
        assert not result.is_error, result
        read = result.structured_content
        assert read is not None
        assert read["url"] == "https://example.org/classifica"
        assert dt.datetime.fromisoformat(read["fetched_at"]) == READ
        assert read["facts"] == [{"fact": "team_season", "submit_tool": "submit_team_season"}]
        assert read["text"].splitlines() == [
            "# Classifica",
            "Squadra | G | Gf | Gs",
            "Alfa (https://example.org/squadre/alfa/nove/9) | 8 | 14 | 9",  # a profile: on the list
            "Beta | 8 | 10 | 11",  # a squad page: not on this list, so no address
        ]
        table = {
            "teams": [
                {"club": "Alfa", "played": 8, "goals_for": 14, "goals_against": 9},
                {"club": "Beta", "played": 8, "goals_for": 10, "goals_against": 11},
            ]
        }
        stored = await client.call_tool(
            "submit_team_season",
            {"payload": table, "source_url": read["url"], "captured_at": read["fetched_at"]},
        )
        assert not stored.is_error, stored
    assert [(row.club, row.source_url, row.captured_at) for row in read_silver(store, TEAM_SEASONS)] == [
        ("alfa", "https://example.org/classifica", READ),
        ("beta", "https://example.org/classifica", READ),
    ]


async def test_unlisted_address_refused(tmp_path: Path) -> None:
    web = FakeWeb(
        {
            "https://example.org/robots.txt": Response(200, {}, b"User-agent: *\nDisallow: /squadre/\n"),
            "https://example.org/squadre/alfa/nove/9": Response(200, HTML, b"<p>Nove</p>"),
        }
    )
    async with page_tools(LakeStore(tmp_path / "lake"), READING, _fetcher(web, tmp_path), []) as client:
        unlisted = await client.call_tool("read_page", {"url": "https://example.org/altro"})
        assert "https://example.org/altro is not on the reading list" in error_text(unlisted)
        assert web.calls == []  # refused before any request, robots.txt included
        disallowed = await client.call_tool("read_page", {"url": "https://example.org/squadre/alfa/nove/9"})
        assert "robots.txt disallows" in error_text(disallowed)
    assert [url for url, _, _ in web.calls] == ["https://example.org/robots.txt"]


async def test_long_page_in_parts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(text, "PART", 300)  # the table below is about 460 characters
    rows = "".join(f"<tr><td>Squadra {n}</td><td>{n}</td></tr>" for n in range(30))
    web = FakeWeb(
        {
            "https://example.org/robots.txt": Response(404, {}, b""),
            "https://example.org/classifica": Response(
                200, HTML, f"<main><table>{rows}</table></main>".encode()
            ),
        }
    )
    async with page_tools(LakeStore(tmp_path / "lake"), READING, _fetcher(web, tmp_path), []) as client:
        first = (
            await client.call_tool("read_page", {"url": "https://example.org/classifica"})
        ).structured_content
        assert first is not None
        assert (first["part"], first["parts"]) == (1, 2)
        assert first["text"].startswith("Squadra 0 | 0\n")
        assert first["text"].endswith("[Part 1 of 2: call read_page with part=2 for the rest.]")
        second = await client.call_tool("read_page", {"url": "https://example.org/classifica", "part": 2})
        assert second.structured_content is not None
        assert second.structured_content["text"].endswith("Squadra 29 | 29")
        beyond = await client.call_tool("read_page", {"url": "https://example.org/classifica", "part": 3})
        assert "has 2 parts" in error_text(beyond)
