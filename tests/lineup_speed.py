"""Time a lineup with no coverage tracer in the way: `python -m tests.lineup_speed` prints the CPU seconds
one `best_lineup` takes on a synthetic round, with all its simulated rounds (mvp-lineup R4.6); `--review`, one
`review_round` once the round has been played and its statistics read (mvp-review R5.2). Inside the test
suite the tracer slows the simulation about sixfold and other workers compete for the machine, and neither is
the user's wait."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

from fantadamus.engine.constants import SIMULATIONS
from tests.lineup_data import BUDGET_RULES
from tests.lineup_harness import a_round, finished
from tests.xy_harness import NOW, classic_with


async def _seconds(with_rules: bool) -> float:
    with tempfile.TemporaryDirectory() as folder:
        async with a_round(Path(folder), rounds=SIMULATIONS) as here:
            if with_rules:  # a captain and three common modifiers (mvp-rules AT-12)
                rules = classic_with(formula_rules=BUDGET_RULES, lineup=None)
                await here.client.call_tool("set_league_rules", {"rules": rules})
            await here.ask()
            started = time.process_time()
            await here.ask(as_of=NOW.isoformat())
            return time.process_time() - started


async def _review_seconds() -> float:
    with tempfile.TemporaryDirectory() as folder:
        async with a_round(Path(folder), rounds=SIMULATIONS) as here:
            await here.ask()
            finished(here)
            await here.client.call_tool("review_round", {"round": 10, "as_advised": True})  # reads the page
            started = time.process_time()
            await here.client.call_tool("review_round", {"round": 10})
            return time.process_time() - started


if __name__ == "__main__":
    review = "--review" in sys.argv
    print(asyncio.run(_review_seconds() if review else _seconds("--rules" in sys.argv)))
