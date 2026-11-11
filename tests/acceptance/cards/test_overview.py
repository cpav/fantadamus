"""AT-7 of mvp-cards: the round at a glance, one line per fixture in kickoff order, team-level only, enough
for a question across fixtures (design C6; R5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.lineup_harness import Round, a_round

pytestmark = pytest.mark.anyio


async def _call(here: Round, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    result = await here.client.call_tool(tool, args)
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


async def test_at7_one_line_per_fixture(tmp_path: Path) -> None:
    """Each fixture once, in kickoff order, with the favourite and its chance, the draw, both sides' expected
    goals and clean sheets, and three goals or more; nothing is logged."""
    async with a_round(tmp_path) as here:
        found = await _call(here, "round_overview", {})
        logged = here.log.read()
    assert found["status"] == "overview", found
    overview = found["overview"]
    assert overview["round"] == 10
    assert overview["deadline"].startswith("2026-10-31T15:00:00+01:00")
    lines = overview["lines"]
    assert [(line["home"], line["away"]) for line in lines] == [("Alfa", "Beta"), ("Gamma", "Delta")]
    assert [line["kickoff"][:16] for line in lines] == ["2026-10-31T15:00", "2026-10-31T18:00"]
    for line in lines:
        assert line["favourite"] in (line["home"], line["away"])
        assert 0 < line["p_draw"] < line["p_favourite"] < 1
        assert line["home_goals"] > 0
        assert 0 < line["home_clean_sheet"] < 1
        assert line["p_three_or_more"] is not None
        assert line["from_odds"]
    assert logged == []
    numbers = [value for line in lines for value in line.values() if isinstance(value, float)]
    assert all(round(value, 3) == value for value in numbers)  # three decimals, like a card
    asked = {item["fact"] for item in found["improve"]}
    assert asked <= {"fixtures", "match_odds", "team_season"}  # never the takers or players' figures


async def test_at7_the_safest_keepers(tmp_path: Path) -> None:
    """The overview's clean sheets are the cards': "which keepers are safest this round?" is answered from
    its lines alone, and agrees with each match's card."""
    async with a_round(tmp_path) as here:
        overview = (await _call(here, "round_overview", {}))["overview"]
        cards = {
            line["home"]: (await _call(here, "match_card", {"club": line["home"]}))["card"]
            for line in overview["lines"]
        }
    sheets = sorted(
        (
            (line[f"{side}_clean_sheet"], line[side])
            for line in overview["lines"]
            for side in ("home", "away")
        ),
        reverse=True,
    )
    assert len(sheets) == 4
    for line in overview["lines"]:
        numbers = cards[line["home"]]["numbers"]
        assert line["home_clean_sheet"] == pytest.approx(numbers["home"]["p_clean_sheet"], abs=1e-3)
        assert line["away_clean_sheet"] == pytest.approx(numbers["away"]["p_clean_sheet"], abs=1e-3)
        assert line["home_goals"] == pytest.approx(numbers["home"]["expected_goals"], abs=1e-3)
