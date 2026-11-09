"""AT-8: a user with only bonuses and maluses still gets "X or Y?", and is asked for just the missing
settings; an impossible value is rejected. `best_lineup` itself returns this step from task 5 (R2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import CLASSIC, RulesStore, scoring_for, setup_step
from tests.xy_harness import ask, collect, error_text, set_classic, tools

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)


async def _set(client: Any, **lineup: Any) -> Any:
    return await client.call_tool("set_league_rules", {"rules": CLASSIC.model_dump() | {"lineup": lineup}})


async def test_at8_setup_step_only_for_what_is_missing(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    rules = RulesStore(store.root / "league")

    def missing() -> set[str] | None:
        stored = rules.get("user-1")
        assert stored is not None
        step = setup_step(stored.rules, lineup=True)
        return None if step is None else {field.field for field in step.lineup}

    async with tools(store) as client:
        await set_classic(client)
        await collect(client, READ)
        assert (await ask(client))["status"] == "answer"  # bonuses and maluses are enough for this
        assert missing() == {
            "format",
            "thresholds",
            "bench_size",
            "substitutions",
            "substitution_mode",
            "formations",
        }
        assert not (await _set(client, format="head_to_head", bench_size=12)).is_error
        assert missing() == {"thresholds", "substitutions", "substitution_mode", "formations"}
        full = {
            "thresholds": [66, 72],
            "substitutions": 5,
            "substitution_mode": "same_role",
            "formations": ["3-4-3", "4-3-3"],
            "other_rules": ["defence modifier"],
        }
        assert not (await _set(client, **full)).is_error
        assert missing() is None
        stored = rules.get("user-1")
        assert stored is not None
        assert stored.rules.lineup is not None
        assert stored.rules.lineup.bench_size == 12  # kept from the earlier call
        assert stored.rules.lineup.other_rules == ["defence modifier"]
        assert (await ask(client))["status"] == "answer"

        await set_classic(client, goal=3.5)  # a change of bonuses doesn't lose the lineup rules
        stored = rules.get("user-1")
        assert stored is not None
        assert scoring_for(stored.rules, "A").goal == 3.5
        assert stored.rules.lineup is not None
        assert missing() is None


async def test_at8_an_impossible_value_is_rejected_with_the_reason(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        await set_classic(client)
        refused = await _set(client, formations=["4-4-3"])
        assert refused.is_error
        assert "ten outfield players" in error_text(refused)
        refused = await _set(client, thresholds=[72, 66])
        assert refused.is_error
        assert "thresholds must rise" in error_text(refused)
    stored = RulesStore(store.root / "league").get("user-1")
    assert stored is not None
    assert stored.rules.lineup is None  # nothing changed
