"""Time a lineup with no coverage tracer in the way: `python -m tests.lineup_speed` prints the CPU seconds
one `best_lineup` takes on a synthetic round, with all its simulated rounds (mvp-lineup R4.6). Inside the test
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
from tests.lineup_harness import a_round
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


if __name__ == "__main__":
    print(asyncio.run(_seconds("--rules" in sys.argv)))
