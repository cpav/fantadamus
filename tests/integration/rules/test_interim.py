"""A league's captain was named as left out until the simulation priced it (mvp-rules task 4): now it's in
the score, and no longer among what the score doesn't include (R1.2, R3.3, R4.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.lineup_harness import a_round
from tests.xy_harness import classic_with

pytestmark = pytest.mark.anyio

CAPTAIN = {
    "name": "captain",
    "who": "captain",
    "combine": "each",
    "bands": [{"from_value": 0.0, "points": -1.0}, {"from_value": 7.0, "points": 1.0}],
}


async def test_a_priced_captain_isnt_named_as_left_out(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        rules = classic_with(formula_rules=[CAPTAIN], lineup=None)
        result = await here.client.call_tool("set_league_rules", {"rules": rules})
        assert not result.is_error, result
        lineup = (await here.ask())["lineup"]
    assert not any("doesn't include" in warning and "captain" in warning for warning in lineup["warnings"])
    assert [rule["name"] for rule in lineup["rules_worth"]] == ["captain"]
    assert lineup["captain"] is not None
