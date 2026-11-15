"""P5 of mvp-sources: the new facts (rest days, injuries and bans) move no chance of starting and no expected
score: the same round, with and without the pages, gives the same numbers everywhere (design C5; R3.3, R5.3,
decision 2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from tests.acceptance.sources.test_detail import PAGES
from tests.lineup_harness import CLUBS, LINES, a_round
from tests.sources_pages import Box, link, start_date, uefa_box, wiki_page

pytestmark = pytest.mark.anyio

CHAMPIONS = "https://example.org/wiki/2026%E2%80%9327_UEFA_Champions_League_league_phase?action=raw"
IN_EUROPE = wiki_page(
    [uefa_box(Box(link(club), link("Kessel"), start_date(dt.date(2026, 10, 28)), "21:00")) for club in CLUBS]
)
SHOWN = ("rest", "out", "one_booking_from_a_ban", "notes", "sources")
"""What the new facts may add; everything else must be the same."""


async def _content(client: Client, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    result = await client.call_tool(tool, args)
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


def _numbers(found: object) -> object:
    """Every number in an answer, wherever it sits, without what the new facts may add."""
    if isinstance(found, dict):
        return {key: _numbers(value) for key, value in found.items() if key not in SHOWN}
    if isinstance(found, list):
        return [_numbers(value) for value in found]
    return found if isinstance(found, int | float) and not isinstance(found, bool) else None


async def _answers(tmp_path: Path, **pages: Any) -> list[object]:
    async with a_round(tmp_path, **pages) as here:
        cards = [
            (await _content(here.client, "match_card", {"club": club}))["card"] for club in ("Alfa", "Gamma")
        ]
        outlooks = [
            (await _content(here.client, "player_outlook", {"player": f"{club} {word}"}))["answer"]["players"]
            for club in CLUBS
            for word in LINES
        ]
        lineup = (await here.ask())["lineup"]
    return (
        [
            _numbers([{key: side[key] for key in ("eleven", "disputed")} for side in card["sides"]])
            for card in cards
        ]
        + [_numbers([card["players"], card["numbers"], card["scorers"]]) for card in cards]
        + [
            _numbers(outlooks),
            _numbers({key: lineup[key] for key in ("starters", "bench", "expected", "formation")}),
        ]
    )


async def test_p5_context_moves_nothing(tmp_path: Path) -> None:
    """Every player of the round, on both cards, in his outlook and in the lineup."""
    plain = await _answers(tmp_path / "plain")
    with_pages = await _answers(tmp_path / "pages", unavailable=PAGES, other={CHAMPIONS: IN_EUROPE})
    assert with_pages == plain
