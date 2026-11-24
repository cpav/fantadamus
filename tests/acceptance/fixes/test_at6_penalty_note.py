"""mvp-fixes AT-6: a taker whose listed predecessors are all out gets a note that says so, in the outlook and
the lineup's warnings; one with a doubtful predecessor keeps the share (R4.1, R4.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.collect_pages import FcoMatch
from tests.lineup_harness import MATCHES, Round, a_round
from tests.xy_harness import NOW, send

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("start_values")]  # as AT-18 of mvp-lineup

LISTS = {club: [f"{club} Nove", f"{club} Dieci"] for club in ("Alfa", "Beta", "Gamma", "Delta")}
OUT = "Beta Quattordici, first on Beta's list, is out, so Beta Nove takes the penalties: counted in full."


def _payload(**orders: list[str]) -> dict[str, Any]:
    return {"clubs": [{"club": club, "takers": orders.get(club, LISTS[club])} for club in LISTS]}


async def _notes(here: Round, player: str) -> list[str]:
    result = await here.client.call_tool("player_outlook", {"player": player})
    assert not result.is_error, result
    assert result.structured_content is not None
    notes: list[str] = result.structured_content["answer"]["players"][0]["notes"]
    return notes


async def test_at6_the_note_says_who_is_out(tmp_path: Path) -> None:
    async with a_round(tmp_path / "out") as here:
        await send(
            here.client, "submit_penalty_takers", _payload(Beta=["Beta Quattordici", "Beta Nove"]), NOW
        )
        handed = await _notes(here, "Beta Nove")
        lineup = await here.ask()
    assert OUT in handed
    assert OUT in lineup["lineup"]["warnings"]
    assert not any("misses the start" in note for note in handed)
    doubtful = (FcoMatch("Alfa", "Beta", percents={"Beta Nove": (60, 60, 60, 60)}), MATCHES[1])
    async with a_round(tmp_path / "doubtful", matches=doubtful) as here:
        second = await _notes(here, "Beta Dieci")
    assert "Beta Dieci takes Beta's penalties if Beta Nove misses the start: they count at 40%." in second
