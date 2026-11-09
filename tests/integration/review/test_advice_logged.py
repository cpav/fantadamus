"""mvp-review task 4.2: an override is logged with the whole advice beside it, so a review compares the
user's lineup with what they were told (design C5; R3.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.lineup_data import CAPTAIN_RULE
from tests.lineup_harness import a_round
from tests.xy_harness import classic_with

pytestmark = pytest.mark.anyio


async def test_an_override_logs_the_advice(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        with_captain = classic_with(formula_rules=[CAPTAIN_RULE], lineup=None)
        assert not (await here.client.call_tool("set_league_rules", {"rules": with_captain})).is_error
        advised = (await here.ask())["lineup"]
        benched = next(player["name"] for player in advised["bench"] if player["role"] != "P")
        await here.ask(start=[benched])
        told, chosen = here.log.read()[-2:]
    assert chosen.override_cost is not None
    assert chosen.advised_starters == told.starters
    assert chosen.advised_bench == told.bench
    assert chosen.advised_formation == told.formation
    assert (chosen.advised_captain, chosen.advised_vice) == (told.captain, told.vice)
    assert told.captain is not None
    assert told.advised_bench is None  # the advice itself needs nothing beside it
