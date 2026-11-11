"""mvp-cards task 5.1: `match_card`'s statuses, and a card for a match whose lineups aren't out yet (design
C5; R1.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from fantadamus.web.fetch import Response
from tests.collect_harness import ROUND_ROUTE, TAKERS_ROUTE
from tests.collect_pages import FcoMatch, takers_page
from tests.lineup_harness import MATCHES, a_round

pytestmark = pytest.mark.anyio


async def _card(client: Any, **args: Any) -> dict[str, Any]:
    result = await client.call_tool("match_card", args)
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


async def test_statuses(tmp_path: Path) -> None:
    """Without the round's fixtures there's nothing to say yet: a refresh plan for them. With no league rules
    stored, the card still answers, on Classic's points, and says so."""
    async with a_round(tmp_path, league=False) as here:
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(500, {}, b"")
        empty = await _card(here.client, club="Alfa")
        here.round_page(*MATCHES)
        here.clock.now += dt.timedelta(minutes=16)  # a page tried moments ago isn't asked again at once
        found = await _card(here.client, club="Alfa")
    assert empty["status"] == "refresh"
    assert "fixtures" in [item["fact"] for item in empty["refresh"]]
    assert found["status"] == "card", found
    assert found["card"]["classic_rules"]
    assert "Classic" in found["message"]


async def test_missing_lineups_still_give_a_card(tmp_path: Path) -> None:
    """Before the outlets publish, a card gives the match in numbers and names the lineups as missing."""
    early = (FcoMatch("Alfa", "Beta", lineups=False), MATCHES[1])
    async with a_round(tmp_path, matches=early) as here:
        found = await _card(here.client, club="Alfa")
    assert found["status"] == "card", found
    card = found["card"]
    assert card["numbers"]["home"]["expected_goals"] > 0
    assert all(side["eleven"] == [] for side in card["sides"])
    assert "probable_lineups" in [item["fact"] for item in found["improve"]]


async def test_the_overview_before_the_fixtures(tmp_path: Path) -> None:
    """Without the round's fixtures the overview asks for them, as a card does."""
    async with a_round(tmp_path) as here:
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(500, {}, b"")
        result = await here.client.call_tool("round_overview", {})
    content = result.structured_content
    assert content is not None
    assert content["status"] == "refresh"
    assert "fixtures" in [item["fact"] for item in content["refresh"]]


async def test_the_overview_reads_only_its_pages(tmp_path: Path) -> None:
    """With no penalty takers stored, the overview still doesn't send the collector for them: they're the
    cards', and a glance at the round doesn't need them."""
    page = takers_page({club: [f"{club} Nove"] for club in ("Alfa", "Beta", "Gamma", "Delta")})
    async with a_round(tmp_path, takers=page) as here:
        result = await here.client.call_tool("round_overview", {})
        fetched = [url for url, _, _ in here.web.calls]
    content = result.structured_content
    assert content is not None
    assert content["status"] == "overview", content
    assert not any(url.endswith(TAKERS_ROUTE) for url in fetched)
    assert "penalty_takers" not in [item["fact"] for item in content["improve"]]
