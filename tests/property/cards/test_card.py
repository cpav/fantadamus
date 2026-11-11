"""P4 and P5 of mvp-cards: each player's chances on a card are `player_outlook`'s, checked for every player of
both clubs; and a card replayed at an earlier as-of logs nothing (design C5; R1.5, R4.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.lineup_harness import Round, a_round

pytestmark = pytest.mark.anyio


async def _content(here: Round, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    result = await here.client.call_tool(tool, args)
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


async def test_p4_as_player_outlook(tmp_path: Path) -> None:
    """Every player of both clubs the card names, on both matches of the round: his chance of starting, of
    scoring if he starts and in the match, and his worth, are the outlook's."""
    async with a_round(tmp_path) as here:
        await here.ask()
        at = here.clock.now.isoformat()
        for club in ("Alfa", "Gamma"):
            found = (await _content(here, "match_card", {"club": club, "as_of": at}))["card"]
            for player in found["players"]:
                outlook = await _content(here, "player_outlook", {"player": player["name"], "as_of": at})
                value = outlook["answer"]["players"][0]["value"]
                # A card rounds to three decimals, to stay within its size.
                assert player["p_start"] == pytest.approx(value["p_start"], abs=1e-3)
                assert player["key"] == pytest.approx(value["key"], abs=1e-3)
                if player["role"] != "P":
                    expected = (
                        value["p_start"] * value["p_scores"] + value["p_cameo"] * value["p_scores_cameo"]
                    )
                    assert player["p_scores"] == pytest.approx(expected, abs=1e-3)


async def test_p5_a_replay_logs_nothing(tmp_path: Path) -> None:
    """An earlier as-of never logs, however often it's asked; the clock's time logs once a call."""
    async with a_round(tmp_path) as here:
        await here.ask()
        at = here.clock.now.isoformat()
        before = len(here.log.read())
        for _ in range(3):
            assert (await _content(here, "match_card", {"club": "Alfa", "as_of": at}))["status"] == "card"
        assert len(here.log.read()) == before
        await _content(here, "match_card", {"club": "Alfa"})
        assert len(here.log.read()) == before + 1
