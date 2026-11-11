"""AT-10 of mvp-cards: a card and the round overview within 3 seconds and 15 KB, from no new page, each tool's
description saying how to show it (design C7; R6.2 to R6.4)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from scripts.checks._common import run_command

from tests.lineup_harness import Round, a_round

pytestmark = pytest.mark.anyio


async def _content(here: Round, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    result = await here.client.call_tool(tool, args)
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


async def test_at10_in_budget(tmp_path: Path) -> None:
    """In a process of its own for the time, as the lineup's budget is measured: see
    `tests/lineup_speed.py`."""
    for kind in ("--card", "--overview"):
        timed = run_command([sys.executable, "-m", "tests.lineup_speed", kind])
        assert timed.returncode == 0, timed.stderr
        assert float(timed.stdout) < 3.0, kind
    async with a_round(tmp_path) as here:
        card = await _content(here, "match_card", {"club": "Alfa"})
        overview = await _content(here, "round_overview", {})
    assert card["status"] == "card"
    assert overview["status"] == "overview"
    assert len(json.dumps(card).encode()) < 15_000
    assert len(json.dumps(overview).encode()) < 15_000


async def test_at10_from_no_new_page(tmp_path: Path) -> None:
    """A card and the overview read only the pages the round already reads, and each tool says how to show
    its answer, so the prompt needs only a line about them."""
    async with a_round(tmp_path) as here:
        await _content(here, "match_card", {"club": "Alfa"})
        await _content(here, "round_overview", {})
        pages = [url for url, _, _ in here.web.calls]
        tools = {tool.name: tool.description or "" for tool in (await here.client.list_tools()).tools}
    assert set(pages) <= set(here.routes)
    card = tools["match_card"]
    for rule in ("In this order", "listed as out by", "never move a number", "Sources at the bottom"):
        assert rule in card, rule
    assert "In this order" in tools["round_overview"]
