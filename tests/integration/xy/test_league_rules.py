"""Task 6.2: `set_league_rules` through the MCP client (R12.2, R12.3, R12.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import CLASSIC, RulesStore, scoring_for
from tests.xy_harness import NOW, error_text, tools

pytestmark = pytest.mark.anyio


async def test_set_then_change_rules(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        first = await client.call_tool("set_league_rules", {"rules": CLASSIC.model_dump()})
        assert not first.is_error, first
        by_role = CLASSIC.model_dump() | {
            "goal": {"keeper": 5, "defender": 4.5, "midfielder": 3.5, "forward": 3}
        }
        second = await client.call_tool("set_league_rules", {"rules": by_role})
        assert not second.is_error, second
        assert second.structured_content is not None
        assert second.structured_content["user"] == "user-1"
    stored = RulesStore(tmp_path / "league").get("user-1")
    assert stored is not None
    assert stored.saved_at == NOW
    forward, defender = scoring_for(stored.rules, "A"), scoring_for(stored.rules, "D")
    assert (forward.goal, forward.penalty_scored, forward.assist, forward.yellow) == (3, 3, 1, -0.5)
    assert defender.goal == 4.5
    assert scoring_for(CLASSIC, "D").goal == 3


async def test_out_of_range_rejected_with_reason(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        too_high = await client.call_tool("set_league_rules", {"rules": CLASSIC.model_dump() | {"goal": 11}})
        assert "less than or equal to 10" in error_text(too_high)
        wrong_sign = await client.call_tool(
            "set_league_rules", {"rules": CLASSIC.model_dump() | {"yellow_card": 0.5}}
        )
        assert "yellow_card" in error_text(wrong_sign)
        assert "less than or equal to 0" in error_text(wrong_sign)
    assert RulesStore(tmp_path / "league").get("user-1") is None
