"""AT-7 of mvp-sources: a card and an outlook stay within their budgets with every new fact, a season of
ratings included, and the new pages need no paid service and no account (design C9; R7.2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from fantadamus.web.collector import load_collector
from tests.acceptance.sources.test_detail import PAGES
from tests.lineup_harness import a_round
from tests.property.sources.test_no_number_moves import CHAMPIONS, IN_EUROPE

pytestmark = pytest.mark.anyio
ROOT = Path(__file__).resolve().parents[3]


async def test_at7_a_card_and_an_outlook_in_budget(tmp_path: Path, timings: dict[str, Any]) -> None:
    """Each under 3 CPU-seconds with a season's ratings stored (timed in a process of its own, see
    `tests/lineup_speed.py`), and each under 15 KB with rest days, injuries and bans; no page asks for a
    key."""
    assert timings["sources_card"] < 3.0
    assert timings["sources_outlook"] < 3.0

    async with a_round(tmp_path, unavailable=PAGES, other={CHAMPIONS: IN_EUROPE}) as here:
        answers: list[dict[str, Any]] = []
        for tool, args in (("match_card", {"club": "Beta"}), ("player_outlook", {"player": "Beta Nove"})):
            result = await here.client.call_tool(tool, args)
            assert not result.is_error, result
            assert result.structured_content is not None
            answers.append(result.structured_content)
    card, outlook = answers
    assert card["card"]["sides"][1]["rest"]["line"]
    assert any("reason" in entry for side in card["card"]["sides"] for entry in side["out"])
    assert outlook["answer"]["players"][0]["rest"]["line"]
    for answer in answers:
        assert len(json.dumps(answer).encode()) < 15_000

    config = load_collector(ROOT / "config" / "reading_list.toml")
    pages = [config.injuries, config.suspensions, config.ratings, *config.other_competitions]
    for page in pages:
        assert page is not None
        keys = {name.lower() for name in parse_qs(urlsplit(page).query)}
        assert not keys & {"key", "apikey", "api_key", "token"}, page
