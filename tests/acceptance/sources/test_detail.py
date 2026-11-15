"""AT-3 of mvp-sources: injury and ban detail from invented pages, shown on a card, an outlook and a lineup;
one booking from a ban marked; a disagreement shown; no chance moves (design C5; R3.2, R3.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from tests.collect_harness import INJURIES_ROUTE
from tests.lineup_harness import SQUAD, a_round
from tests.sources_pages import injured_page, suspended_page

pytestmark = pytest.mark.anyio

INJURED = injured_page(
    {
        "Alfa": [
            ("Alfa Quattordici", "Lesione muscolare alla coscia destra, rientro dalla fine di novembre.")
        ],
        "Beta": [("Beta Nove", "Affaticamento al polpaccio, da valutare.")],
    }
)
SUSPENDED = suspended_page(
    {
        "Alfa": ([], ["Alfa Sette"]),
        "Gamma": ([("Gamma Sei", "squalificato nella 10a giornata di campionato")], []),
    }
)
PAGES = (INJURED, SUSPENDED)
QUATTORDICI = {"reason": "thigh muscle injury", "back": "back from late November"}
DISAGREEMENT = (
    "Fantacalcio.it, Gazzetta, SOS Fanta and Sky have him starting; Fantacalcio.it's injury page has him out."
)


async def _content(client: Client, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    result = await client.call_tool(tool, args)
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


def _out(card: dict[str, Any], side: int) -> dict[str, dict[str, Any]]:
    return {entry["name"]: entry for entry in card["sides"][side]["out"]}


async def test_at3_detail_on_the_answers(tmp_path: Path) -> None:
    """The card's out list gives each player's reason and return from the pages, the outlook his own, and the
    lineup the reason beside each player out or doubtful; a ban for this round is a reason too. The lineup,
    asked first, has the pages read, since nothing of theirs is stored; they're named in the sources."""
    async with a_round(tmp_path, unavailable=PAGES, squad=False) as here:
        await here.set_squad(*SQUAD, "Alfa Quattordici")
        lineup = (await here.ask())["lineup"]  # first: it reads the pages itself
        concerns = {entry["name"]: entry for entry in lineup["out_and_doubtful"]}
        assert concerns["Alfa Quattordici"]["status"] == "out"
        assert (concerns["Alfa Quattordici"]["reason"], concerns["Alfa Quattordici"]["back"]) == (
            QUATTORDICI["reason"],
            QUATTORDICI["back"],
        )

        card = (await _content(here.client, "match_card", {"club": "Alfa"}))["card"]
        assert _out(card, 0)["Alfa Quattordici"] | QUATTORDICI == _out(card, 0)["Alfa Quattordici"]
        assert _out(card, 0)["Alfa Quattordici"]["outlets"] == 4
        gamma = (await _content(here.client, "match_card", {"club": "Gamma"}))["card"]
        assert _out(gamma, 0)["Gamma Sei"]["reason"] == "banned for round 10"

        outlook = await _content(here.client, "player_outlook", {"player": "Alfa Quattordici"})
        [player] = outlook["answer"]["players"]
        assert player["out"] == QUATTORDICI
        assert f"https://example.org{INJURIES_ROUTE}" in {
            source["source_url"] for source in player["sources"]
        }
        reads = [url for url, *_ in here.web.calls if url.endswith(INJURIES_ROUTE)]
        assert len(reads) == 1  # read for the lineup; fresh after that


async def test_at3_one_booking_from_a_ban(tmp_path: Path) -> None:
    """A player one booking from a ban is marked on the card and in his outlook; the others aren't."""
    async with a_round(tmp_path, unavailable=PAGES) as here:
        card = (await _content(here.client, "match_card", {"club": "Alfa"}))["card"]
        marked = {player["name"] for player in card["players"] if player.get("one_booking_from_a_ban")}
        assert marked == {"Alfa Sette"}
        outlook = await _content(here.client, "player_outlook", {"player": "Alfa Sette"})
        assert outlook["answer"]["players"][0]["one_booking_from_a_ban"] is True
        other = await _content(here.client, "player_outlook", {"player": "Alfa Sei"})
        assert other["answer"]["players"][0]["one_booking_from_a_ban"] is False


async def test_at3_a_disagreement(tmp_path: Path) -> None:
    """Every outlet has Beta Nove starting while the injury page has him out: the card lists him as out with
    the disagreement, his outlook says it, and the lineup has him as doubtful with it, his chance of starting
    the outlets' alone."""
    async with a_round(tmp_path) as here:
        before = (await _content(here.client, "player_outlook", {"player": "Beta Nove"}))["answer"][
            "players"
        ][0]
    async with a_round(tmp_path / "pages", unavailable=PAGES) as here:
        card = (await _content(here.client, "match_card", {"club": "Beta"}))["card"]
        nove = _out(card, 1)["Beta Nove"]
        assert (nove["reason"], nove["back"], nove["disagreement"]) == (
            "calf muscle injury",
            "return to be assessed",
            DISAGREEMENT,
        )
        assert nove["outlets"] == 0
        [player] = (await _content(here.client, "player_outlook", {"player": "Beta Nove"}))["answer"][
            "players"
        ]
        assert DISAGREEMENT in player["notes"]
        assert player["value"]["p_start"] == before["value"]["p_start"]
        lineup = (await here.ask())["lineup"]
        assert "Beta Nove" in {part["name"] for part in lineup["starters"]}
        concerns = {entry["name"]: entry for entry in lineup["out_and_doubtful"]}
        assert concerns["Beta Nove"]["status"] == "doubtful"
        assert concerns["Beta Nove"]["disagreement"] == DISAGREEMENT
