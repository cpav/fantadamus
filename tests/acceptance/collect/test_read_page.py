"""AT-11: a page added to the reading list in configuration alone is read through `read_page` from a real
local server, and the facts Claude submits from it are stored with its address (R3.2, R3.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.core.clock import fixed_clock
from fantadamus.domains.facts import read_silver
from fantadamus.domains.season.silver import PENALTY_TAKERS
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.mcp.tools.compare import load_reading_list
from fantadamus.web.fetch import Fetcher
from tests.collect_harness import local_site, page_tools
from tests.xy_harness import error_text

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)
TAKERS = (
    "<html><body><main><h1>Rigoristi</h1>"
    + "".join(
        f"<div><span>{club}</span><ol><li>{club} Nove</li><li>{club} Dieci</li></ol></div>"
        for club in ("Alfa", "Beta")
    )
    + "</main></body></html>"
).encode()


async def test_at11_page_added_in_config_only(tmp_path: Path) -> None:
    routes = {
        "/robots.txt": (404, {}, b""),
        "/rigoristi": (200, {"Content-Type": "text/html; charset=utf-8"}, TAKERS),
    }
    with local_site(routes) as site:
        config = tmp_path / "reading_list.toml"
        config.write_text(
            '[facts.penalty_takers]\nneed = "N9"\nsubmit_tool = "submit_penalty_takers"\n'
            f'pages = ["{site.base_url}/rigoristi"]\n',
            encoding="utf-8",
        )
        fetcher = Fetcher(
            allowed_hosts=["127.0.0.1"], clock=fixed_clock(READ), robots_cache=tmp_path / "robots"
        )
        store = LakeStore(tmp_path / "lake")
        async with page_tools(store, load_reading_list(config), fetcher, ["127.0.0.1"]) as client:
            refused = await client.call_tool("read_page", {"url": f"{site.base_url}/altro"})
            assert "is not on the reading list" in error_text(refused)
            result = await client.call_tool("read_page", {"url": f"{site.base_url}/rigoristi"})
            assert not result.is_error, result
            read = result.structured_content
            assert read is not None
            assert read["facts"] == [{"fact": "penalty_takers", "submit_tool": "submit_penalty_takers"}]
            assert read["text"].splitlines() == [
                "# Rigoristi",
                "Alfa",
                "- Alfa Nove",
                "- Alfa Dieci",
                "Beta",
                "- Beta Nove",
                "- Beta Dieci",
            ]
            takers = {
                "clubs": [
                    {"club": club, "takers": [f"{club} Nove", f"{club} Dieci"]} for club in ("Alfa", "Beta")
                ]
            }
            stored = await client.call_tool(
                "submit_penalty_takers",
                {"payload": takers, "source_url": read["url"], "captured_at": read["fetched_at"]},
            )
            assert not stored.is_error, stored
    assert [path for path, _ in site.requests] == ["/robots.txt", "/rigoristi"]  # never /altro
    rows = read_silver(store, PENALTY_TAKERS)
    assert {(row.club, row.rank, row.name) for row in rows} >= {
        ("alfa", 1, "Alfa Nove"),
        ("beta", 2, "Beta Dieci"),
    }
    assert {(row.source_url, row.captured_at) for row in rows} == {(f"{site.base_url}/rigoristi", READ)}
