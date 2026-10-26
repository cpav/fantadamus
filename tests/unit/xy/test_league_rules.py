"""Task 6: the league-rules store and the setup step (design C9; R12.2 to R12.4)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from fantadamus.contracts.xy.league import LeagueRules
from fantadamus.league.rules import CLASSIC, RulesStore, setup_step

T1 = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)
T2 = dt.datetime(2026, 10, 27, 9, 0, tzinfo=dt.UTC)


def test_change_keeps_previous_version(tmp_path: Path) -> None:
    store = RulesStore(tmp_path)
    assert store.get("user-1") is None
    store.set("user-1", CLASSIC, at=T1)
    richer = LeagueRules.model_validate(CLASSIC.model_dump() | {"goal": 3.5})
    store.set("user-1", richer, at=T2)
    current = store.get("user-1")
    assert current is not None
    assert (current.rules, current.saved_at, current.user) == (richer, T2, "user-1")
    [previous] = sorted(tmp_path.glob("user-1.*.json"))
    assert previous.name == "user-1.20261026T090000000000Z.json"
    assert json.loads(previous.read_text(encoding="utf-8"))["rules"]["goal"] == 3
    assert store.get("user-2") is None
    with pytest.raises(ValueError, match="user"):
        store.get("../user-1")


def test_setup_step_offers_classic_values() -> None:
    step = setup_step()
    assert step.tool == "set_league_rules"
    assert {field.field: field.classic for field in step.fields} == {
        "goal": 3,
        "assist": 1,
        "penalty_scored": 3,
        "penalty_missed": -3,
        "penalty_saved": 3,
        "own_goal": -2,
        "yellow_card": -0.5,
        "red_card": -1,
        "goal_conceded": -1,
        "clean_sheet": 1,
    }
    assert all(field.meaning for field in step.fields)
    assert "Classic" in step.message
