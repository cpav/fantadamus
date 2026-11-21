"""mvp-fixes AT-5: every answer names the pages whose facts it shows. A lineup that says why a player is out
names the injured page among its sources, as the card and the outlook already do (R3.1, R3.2).

The test site serves every page from one host, so a Sources line can't tell the pages apart there; the content
hashes an answer logs, one per page read it used, can."""

from __future__ import annotations

from pathlib import Path

import pytest

from fantadamus.domains.availability.silver import INJURIES
from fantadamus.domains.facts import read_silver
from fantadamus.domains.season.silver import SEASON_STATS
from fantadamus.lake.review_log import ReviewLog
from tests.collect_harness import INJURIES_ROUTE
from tests.integration.review.test_tool import review
from tests.lineup_harness import SQUAD, a_round, finished
from tests.sources_pages import injured_page, suspended_page

pytestmark = pytest.mark.anyio

INJURED = injured_page(
    {"Alfa": [("Alfa Quattordici", "Lesione muscolare alla coscia destra, rientro dalla fine di novembre.")]}
)
PAGES = (INJURED, suspended_page({}))


async def test_at5_a_lineup_names_the_injured_page(tmp_path: Path) -> None:
    async with a_round(tmp_path, unavailable=PAGES, squad=False) as here:
        await here.set_squad(*SQUAD, "Alfa Quattordici")
        lineup = (await here.ask())["lineup"]
        concerns = {entry["name"]: entry for entry in lineup["out_and_doubtful"]}
        assert concerns["Alfa Quattordici"]["reason"] == "thigh muscle injury"  # shown, from the injured page
        injured = {row.content_sha256 for row in read_silver(here.store, INJURIES)}
        assert injured
        [logged] = [decision for decision in here.log.read() if decision.kind == "lineup"]
        assert injured <= set(logged.content_hashes)


async def test_at5_every_answer_names_the_pages_it_shows(tmp_path: Path) -> None:
    """The outlook and the card name the injured page by its address; the lineup by its logged read, above."""
    async with a_round(tmp_path, unavailable=PAGES, squad=False) as here:
        await here.set_squad(*SQUAD, "Alfa Quattordici")
        await here.ask()
        injured_url = f"{here.base}{INJURIES_ROUTE}"
        outlook = await here.client.call_tool("player_outlook", {"player": "Alfa Quattordici"})
        assert outlook.structured_content is not None
        [player] = outlook.structured_content["answer"]["players"]
        assert injured_url in {found["source_url"] for found in player["sources"]}
        card = await here.client.call_tool("match_card", {"club": "Alfa"})
        assert not card.is_error
        injured = {row.content_sha256 for row in read_silver(here.store, INJURIES)}
        [logged] = [decision for decision in here.log.read() if decision.kind == "card"]
        assert injured <= set(logged.content_hashes)


async def test_at5_the_overview_and_the_review_name_their_pages(tmp_path: Path) -> None:
    """The round at a glance names the pages of its fixtures and odds; a review names the facts priced at the
    lock and the statistics reads it scores the round from, and logs those reads with it."""
    async with a_round(tmp_path) as here:
        await here.ask()
        overview = await here.client.call_tool("round_overview", {})
        assert overview.structured_content is not None
        assert overview.structured_content["overview"]["sources"]
        finished(here)
        result = await review(here, as_advised=True)
        assert result["status"] == "review", result
        assert result["review"]["sources"]
        newest = max(read_silver(here.store, SEASON_STATS), key=lambda row: row.captured_at)
        [logged] = ReviewLog(tmp_path / "lake" / "reviews").read()
        assert newest.content_sha256 in logged.content_hashes
