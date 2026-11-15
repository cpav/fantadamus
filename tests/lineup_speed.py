"""Time a lineup with no coverage tracer in the way: `python -m tests.lineup_speed` prints the CPU seconds
one `best_lineup` takes on a synthetic round, with all its simulated rounds (mvp-lineup R4.6); `--review`, one
`review_round` once the round has been played and its statistics read, and `--replayed` when no advice was
asked for (mvp-review R5.2); `--card`, one `match_card`, and `--overview`, one `round_overview` (mvp-cards
R6.2); `--sources`, a card and an outlook with every new fact of mvp-sources, a season of ratings
included (R7.2); `--alert`, the alerts' check after a run that stored an official lineup (mvp-alerts R4.1).
Inside the test suite the tracer slows the simulation about sixfold and other workers compete for the
machine, and neither is the user's wait. Each answer is timed three times and the fastest kept, as `timeit`
does: a busy machine can only slow a run down, so the fastest is the answer's own cost."""

from __future__ import annotations

import asyncio
import datetime as dt
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from fantadamus.contracts.xy.ratings import RatingsPayload
from fantadamus.domains.facts import Submission, submit_many
from fantadamus.domains.ratings.silver import MATCH_RATINGS
from fantadamus.engine.constants import SIMULATIONS
from tests.lineup_data import BUDGET_RULES
from tests.lineup_harness import a_round, finished
from tests.sources_pages import season_ratings
from tests.xy_harness import CLUBS, NOW, classic_with

TIMES = 3


async def _fastest(run: Callable[[], Awaitable[object]]) -> float:
    """The fewest CPU seconds `run` takes in `TIMES` tries."""
    best = float("inf")
    for _ in range(TIMES):
        started = time.process_time()
        await run()
        best = min(best, time.process_time() - started)
    return best


async def _seconds(with_rules: bool) -> float:
    with tempfile.TemporaryDirectory() as folder:
        async with a_round(Path(folder), rounds=SIMULATIONS) as here:
            if with_rules:  # a captain and three common modifiers (mvp-rules AT-12)
                rules = classic_with(formula_rules=BUDGET_RULES, lineup=None)
                await here.client.call_tool("set_league_rules", {"rules": rules})
            await here.ask()
            return await _fastest(lambda: here.ask(as_of=NOW.isoformat()))


async def _review_seconds(replayed: bool) -> float:
    """With the advice asked for, or replayed at the lock because it wasn't (the collector read the round on
    its own)."""
    with tempfile.TemporaryDirectory() as folder:
        async with a_round(Path(folder), rounds=SIMULATIONS) as here:
            if replayed:
                collector = here.calibrator.collector
                assert collector is not None
                here.collect_log.append(collector.collect())
            else:
                await here.ask()
            finished(here)
            await here.client.call_tool("review_round", {"round": 10, "as_advised": True})  # reads the page
            return await _fastest(lambda: here.client.call_tool("review_round", {"round": 10}))


async def _card_seconds(tool: str, args: dict[str, str]) -> float:
    """A match card, or the round overview, once the round's facts are stored (mvp-cards R6.2)."""
    with tempfile.TemporaryDirectory() as folder:
        async with a_round(Path(folder), rounds=SIMULATIONS) as here:
            await here.ask()
            return await _fastest(lambda: here.client.call_tool(tool, {**args, "as_of": NOW.isoformat()}))


async def _sources_seconds() -> str:
    """A card and an outlook, the fastest of three each, with rest days, injuries, bans and a season of
    ratings stored: two reads of each of 38 rounds, about 27,000 rows, as many as a whole season gives."""
    from tests.acceptance.sources.test_detail import PAGES
    from tests.property.sources.test_no_number_moves import CHAMPIONS, IN_EUROPE

    with tempfile.TemporaryDirectory() as folder:
        async with a_round(
            Path(folder), rounds=SIMULATIONS, unavailable=PAGES, other={CHAMPIONS: IN_EUROPE}
        ) as here:
            await here.ask()
            season = [
                Submission(RatingsPayload.model_validate(season_ratings(round, read)))
                for round in range(1, 39)
                for read in range(2)
            ]
            submit_many(  # one rebuild of the table for the whole season, as a test can afford
                here.store,
                MATCH_RATINGS,
                season,
                source_url="https://example.org/voti",
                captured_at=NOW - dt.timedelta(days=1),
                allowed_hosts=("example.org",),
                clock=lambda: NOW,
                submitted_by="test",
                clubs=CLUBS,
            )
            as_of = NOW.isoformat()
            card = await _fastest(
                lambda: here.client.call_tool("match_card", {"club": "Alfa", "as_of": as_of})
            )
            outlook = await _fastest(
                lambda: here.client.call_tool("player_outlook", {"player": "Alfa Nove", "as_of": as_of})
            )
            return f"{card} {outlook}"


async def _alert_seconds() -> float:
    """The check after a scheduled run that stored an official lineup benching a starter: the first sends,
    the next find the call unchanged; each replays the lineup in full."""
    from tests.alerts_harness import (
        IN_WINDOW,
        Shown,
        benchable,
        check,
        collect_officials,
        told_after_officials,
    )

    with tempfile.TemporaryDirectory() as folder:
        async with a_round(Path(folder), rounds=SIMULATIONS) as here:
            benched = benchable(await told_after_officials(here))["name"]
            report = collect_officials(here, IN_WINDOW, [benched])

            async def run() -> None:
                check(here, report, Shown(), rounds=SIMULATIONS)

            return await _fastest(run)


if __name__ == "__main__":
    if "--review" in sys.argv:
        print(asyncio.run(_review_seconds("--replayed" in sys.argv)))
    elif "--card" in sys.argv:
        print(asyncio.run(_card_seconds("match_card", {"club": "Alfa"})))
    elif "--sources" in sys.argv:
        print(asyncio.run(_sources_seconds()))
    elif "--alert" in sys.argv:
        print(asyncio.run(_alert_seconds()))
    elif "--overview" in sys.argv:
        print(asyncio.run(_card_seconds("round_overview", {})))
    else:
        print(asyncio.run(_seconds("--rules" in sys.argv)))
