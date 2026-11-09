"""Until the simulation prices it (mvp-rules task 4), a league's captain is named as left out, so that no rule
a league holds is quietly ignored (R1.2, R4.3)."""

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


async def test_a_formula_rule_is_named_until_it_is_priced(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        rules = classic_with(formula_rules=[CAPTAIN], lineup=None)
        result = await here.client.call_tool("set_league_rules", {"rules": rules})
        assert not result.is_error, result
        lineup = (await here.ask())["lineup"]
    assert any("doesn't include" in warning and "captain" in warning for warning in lineup["warnings"])
    assert lineup["rules_worth"] == []
