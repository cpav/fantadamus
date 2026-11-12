"""AT-9: what the approved change moves on a round's lineup and cards: the chances and the expected score
move, the shape of every answer stays the same (mvp-recalibrate R9.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fantadamus.domains.availability import consensus
from fantadamus.engine import constants, outfield
from fantadamus.engine.recalibrate import IDENTITY, mapped
from tests.lineup_harness import a_round

pytestmark = pytest.mark.anyio

STARTER = (0.9 + 0.9 + 0.95 + 0.9) / 4  # the outlets' default for a listed starter


def _shape(answer: Any) -> Any:
    """Every key an answer has, at every depth, without its values."""
    if isinstance(answer, dict):
        return {key: _shape(value) for key, value in answer.items()}
    if isinstance(answer, list):
        return [_shape(item) for item in answer[:1]]
    return type(answer).__name__


async def _answers(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    async with a_round(tmp_path) as here:
        lineup = await here.ask()
        card = await here.client.call_tool("match_card", {"club": "Alfa"})
    assert card.structured_content is not None
    return lineup, card.structured_content


async def test_at9_what_it_moves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calibrated, calibrated_card = await _answers(tmp_path / "calibrated")
    monkeypatch.setattr(consensus, "START_MAP", IDENTITY)
    monkeypatch.setattr(outfield, "YELLOW_PRIOR", 0.15)
    started, started_card = await _answers(tmp_path / "started")

    assert _shape(calibrated) == _shape(started)
    assert _shape(calibrated_card) == _shape(started_card)
    assert calibrated["lineup"]["expected"] != started["lineup"]["expected"]

    def chance(card: dict[str, Any]) -> float:
        p_start: float = card["card"]["players"][0]["p_start"]  # a listed starter
        return p_start

    assert chance(started_card) == pytest.approx(STARTER, abs=0.001)
    assert chance(calibrated_card) == pytest.approx(mapped(STARTER, constants.START_MAP), abs=0.001)
