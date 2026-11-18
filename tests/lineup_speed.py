"""Every budget, timed in one process with no coverage tracer in the way (mvp-store design C7; R5.1, R5.2):
`python -m tests.lineup_speed --all` prints each one's CPU seconds as JSON, `--only <name> ...` some of them.

On the synthetic round, as each slice set them: a `best_lineup` with all its simulated rounds (mvp-lineup
R4.6), the same with a captain and three modifiers (mvp-rules AT-12), a `review_round` once the round has
been played, and replayed when no advice was asked for (mvp-review R5.2), a `match_card` and a
`round_overview` (mvp-cards R6.2), a card and an outlook with every new fact of mvp-sources and a season of
ratings (R7.2), and the alerts' check after a run that stored an official lineup (mvp-alerts R4.1). And at
season size, on the same round with a season grown around it (`tests/season.py`): storing one read of the
round page, the schedule's check, reading the lake for an answer, gathering a squad, every answer and the
alerts' check (mvp-store R1.2, R1.5, R3.1, R3.2); with the row counts a reader saw while a store went on
(R1.4).

The round is built once and copied for each timing. Inside the test suite the tracer slows the simulation
about sixfold and other workers compete for the machine, and neither is the user's wait. Each is timed three
times and the fastest kept, as `timeit` does: a busy machine can only slow a run down, so the fastest is its
own cost."""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import json
import shutil
import sys
import tempfile
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

import duckdb

from fantadamus.contracts.xy.lineups import OutletLineupPayload
from fantadamus.contracts.xy.ratings import RatingsPayload
from fantadamus.core.clock import fixed_clock
from fantadamus.domains.availability.silver import OUTLET_VIEWS
from fantadamus.domains.facts import Domain, Submission, submit_many
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.domains.ratings.silver import MATCH_RATINGS
from fantadamus.domains.season.gold import known_players
from fantadamus.domains.season.silver import SEASON_STATS
from fantadamus.engine.constants import SIMULATIONS
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore, connect
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.advisor import Facts, load_reading_list
from fantadamus.mcp.server import make_advisor
from fantadamus.web.cadence import what_is_due
from tests.lineup_data import BUDGET_RULES
from tests.lineup_harness import Round, a_round, finished
from tests.season import grow
from tests.sources_pages import season_ratings
from tests.xy_harness import CLUBS, NOW, ROOT, classic_with, outlet_lineup

TIMES = 3
SEASON_AT = NOW + dt.timedelta(minutes=30)
"""The season's answers: after the round's own read, with nothing left to collect."""
OUTLETS = 30
"""A read of the round page at season size: thirty outlets' sheets for each of the two matches, 60 bronze
files and 1,680 rows."""

Timings = dict[str, Any]


async def _fastest(run: Callable[[], Awaitable[object]]) -> float:
    """The fewest CPU seconds `run` takes in `TIMES` tries."""
    best = float("inf")
    for _ in range(TIMES):
        started = time.process_time()
        await run()
        best = min(best, time.process_time() - started)
    return best


def _fastest_now(run: Callable[[], object]) -> float:
    best = float("inf")
    for _ in range(TIMES):
        started = time.process_time()
        run()
        best = min(best, time.process_time() - started)
    return best


@contextlib.asynccontextmanager
async def _copy(of: Path, into: Path, **options: Any) -> AsyncIterator[Round]:
    """The round stored in `of`, copied to `into` and opened again: its table, takers, rules and squad are
    there already."""
    shutil.copytree(of, into)
    async with a_round(into, rounds=SIMULATIONS, table=False, league=False, squad=False, **options) as here:
        yield here


async def _call(here: Round, tool: str, **args: Any) -> Any:
    result = await here.client.call_tool(tool, args)
    assert not result.is_error, result
    return result.structured_content


async def _rounds(root: Path) -> tuple[Path, Path]:
    """The synthetic round with its table, takers, rules and squad and nothing read yet; and a copy of it
    whose lineup was asked for, which read the round's pages."""
    plain, asked = root / "plain", root / "asked"
    async with a_round(plain, rounds=SIMULATIONS):
        pass
    async with _copy(plain, asked) as here:
        await here.ask()
    return plain, asked


async def _round(root: Path, plain: Path, asked: Path) -> Timings:
    """The six budgets of the earlier slices, on the synthetic round."""
    found: Timings = {}
    async with _copy(asked, root / "lineup") as here:
        found["lineup"] = await _fastest(lambda: here.ask(as_of=NOW.isoformat()))
        found["card"] = await _fastest(lambda: _call(here, "match_card", club="Alfa", as_of=NOW.isoformat()))
        found["overview"] = await _fastest(lambda: _call(here, "round_overview", as_of=NOW.isoformat()))
    async with _copy(asked, root / "rules") as here:  # a captain and three common modifiers (mvp-rules AT-12)
        await _call(here, "set_league_rules", rules=classic_with(formula_rules=BUDGET_RULES, lineup=None))
        await here.ask()
        found["rules"] = await _fastest(lambda: here.ask(as_of=NOW.isoformat()))
    async with _copy(asked, root / "review") as here:
        found["review"] = await _review(here)
    async with _copy(plain, root / "replayed") as here:  # the collector read the round on its own
        collector = here.calibrator.collector
        assert collector is not None
        here.collect_log.append(collector.collect())
        found["review_replayed"] = await _review(here)
    found["sources_card"], found["sources_outlook"] = await _sources(plain, root / "sources")
    async with _copy(plain, root / "alert") as here:
        found["alert"] = await _alert(here)
    return found


async def _review(here: Round) -> float:
    finished(here)
    await _call(here, "review_round", round=10, as_advised=True)  # reads the page
    return await _fastest(lambda: _call(here, "review_round", round=10))


async def _sources(plain: Path, into: Path) -> tuple[float, float]:
    """A card and an outlook with rest days, injuries, bans and a season of ratings stored: two reads of each
    of 38 rounds, about 27,000 rows, as many as a whole season gives."""
    from tests.acceptance.sources.test_detail import PAGES
    from tests.property.sources.test_no_number_moves import CHAMPIONS, IN_EUROPE

    async with _copy(plain, into, unavailable=PAGES, other={CHAMPIONS: IN_EUROPE}) as here:
        await here.ask()
        season = [
            Submission(RatingsPayload.model_validate(season_ratings(round, read)))
            for round in range(1, 39)
            for read in range(2)
        ]
        submit_many(
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
        card = await _fastest(lambda: _call(here, "match_card", club="Alfa", as_of=as_of))
        outlook = await _fastest(lambda: _call(here, "player_outlook", player="Alfa Nove", as_of=as_of))
    return card, outlook


async def _alert(here: Round) -> float:
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

    benched = benchable(await told_after_officials(here))["name"]
    report = collect_officials(here, IN_WINDOW, [benched])

    async def run() -> None:
        check(here, report, Shown(), rounds=SIMULATIONS)

    return await _fastest(run)


async def _season(root: Path, asked: Path) -> Timings:
    """The same round with a season grown around it: its size, and storing, the schedule's check, reading,
    gathering a squad, every answer, with what each answered, and the alerts' check."""
    seasoned = Path(shutil.copytree(asked, root / "season"))
    store = LakeStore(seasoned / "lake")
    grow(store, CollectLog(seasoned / "collect"), DecisionLog(store.root / "decisions"))
    found: Timings = {"size": _size(seasoned), "statuses": {}}
    async with _copy(seasoned, root / "season-answers") as here:
        at = SEASON_AT.isoformat()
        answers: dict[str, Callable[[], Awaitable[Any]]] = {
            "lineup": lambda: here.ask(as_of=at),
            "compare": lambda: _call(
                here, "compare_players", first="Beta Nove", second="Delta Nove", as_of=at
            ),
            "outlook": lambda: _call(here, "player_outlook", player="Alfa Nove", as_of=at),
            "card": lambda: _call(here, "match_card", club="Alfa", as_of=at),
            "overview": lambda: _call(here, "round_overview", as_of=at),
        }
        for name, ask in answers.items():
            found["statuses"][name] = (await ask())["status"]
            found[name] = await _fastest(ask)
        found.update(_reading(here))
        found.update(_storing(here))
    async with _copy(seasoned, root / "season-review") as here:
        found["review"] = await _review(here)
    async with _copy(seasoned, root / "season-alert") as here:
        found["alert"] = await _alert(here)
    return found


def _size(folder: Path) -> Timings:
    """What the season holds, counted by DuckDB: the round page's reads and rows, those in the window, the
    largest month, the statistics' reads, the logs, and the bronze files that came with the round."""
    store = LakeStore(folder / "lake")

    def files(domain: Domain[Any, Any]) -> list[str]:
        written = store.description(domain.table)
        assert written is not None
        return [str(store.root / "silver" / domain.table.name / name) for name in written.files.values()]

    with connect() as connection:
        outlets = connection.read_parquet(files(OUTLET_VIEWS))
        rows, reads = outlets.aggregate("count(*), count(DISTINCT captured_at)").fetchall()[0]
        captured = duckdb.ColumnExpression("captured_at")
        window = outlets.filter(captured >= duckdb.ConstantExpression(NOW - FACTS_WINDOW)).filter(
            captured < duckdb.ConstantExpression(NOW)
        )
        months = [
            connection.read_parquet(path).aggregate("count(*)").fetchall()[0][0]
            for path in files(OUTLET_VIEWS)
        ]
        statistics = connection.read_parquet(files(SEASON_STATS)).aggregate("count(DISTINCT captured_at)")
        return {
            "outlet_rows": int(rows),
            "outlet_reads": int(reads),
            "window_reads": int(window.aggregate("count(DISTINCT captured_at)").fetchall()[0][0]),
            "largest_month": int(max(months)),
            "statistics_reads": int(statistics.fetchall()[0][0]),
            "runs": len(CollectLog(folder / "collect").runs()),
            "answers": len(DecisionLog(store.root / "decisions").read()),
            "bronze": len(store.bronze_files(OUTLET_VIEWS.source)),
        }


def _reading(here: Round) -> Timings:
    """Reading the lake for an answer, and gathering a squad's facts: 25 players."""
    advisor = make_advisor(
        here.store,
        rules=RulesStore(here.store.root / "league"),
        log=DecisionLog(here.store.root / "decisions"),
        clubs=CLUBS,
        reading=load_reading_list(ROOT / "config" / "reading_list.toml"),
        user="user-1",
        clock=fixed_clock(SEASON_AT),
        collect_log=here.collect_log,
    )
    reading = _fastest_now(lambda: Facts.read(here.store, SEASON_AT))
    facts = Facts.read(here.store, SEASON_AT)
    known = known_players(facts.players, SEASON_AT)
    players = [player for player in known if 8000 <= player.player_id < 9000][:25]
    assert len(players) == 25
    gathering = _fastest_now(lambda: advisor.gather(players, SEASON_AT, facts=facts, known=known))
    return {"reading": reading, "gathering": gathering}


def _sheets(index: int) -> list[Submission[OutletLineupPayload]]:
    return [
        Submission(
            OutletLineupPayload.model_validate(outlet_lineup(f"Outlet {index}-{number:02d}", home, away))
        )
        for number in range(OUTLETS)
        for home, away in (("Alfa", "Beta"), ("Gamma", "Delta"))
    ]


def _store(store: LakeStore, index: int) -> None:
    """One read of the round page, its outlets' sheets: their bronze files, and their rows to their month."""
    at = SEASON_AT + dt.timedelta(minutes=index)
    submit_many(
        store,
        OUTLET_VIEWS,
        _sheets(index),
        source_url="https://example.org/probabili-formazioni/ultima-giornata",
        captured_at=at,
        allowed_hosts=("example.org",),
        clock=fixed_clock(at),
        submitted_by="collector",
        clubs=CLUBS,
    )


def _storing(here: Round) -> Timings:
    """A store, the schedule's check, and what a reader saw while a store went on."""
    stores = iter(range(1, 100))
    storing = _fastest_now(lambda: _store(here.store, next(stores)))
    due = _fastest_now(lambda: what_is_due(here.store, here.collect_log, SEASON_AT))
    before = len(here.store.read_rows(OUTLET_VIEWS.table, SEASON_AT - dt.timedelta(days=1)))
    seen: set[int] = set()
    done = threading.Event()

    def read() -> None:
        while not done.is_set():
            seen.add(len(here.store.read_rows(OUTLET_VIEWS.table, SEASON_AT - dt.timedelta(days=1))))

    reader = threading.Thread(target=read)
    reader.start()
    try:
        _store(here.store, next(stores))
    finally:
        done.set()
        reader.join()
    after = len(here.store.read_rows(OUTLET_VIEWS.table, SEASON_AT - dt.timedelta(days=1)))
    return {
        "store": storing,
        "nothing_due": due,
        "reader": {"before": before, "after": after, "seen": sorted(seen)},
    }


async def measure(only: Sequence[str] = ()) -> Timings:
    """Every budget, or those in `only`: `round` for the earlier slices' six, `season` for this slice's."""
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        plain, asked = await _rounds(root)
        found: Timings = {}
        if not only or "round" in only:
            found.update(await _round(root, plain, asked))
        if not only or "season" in only:
            found["season"] = await _season(root, asked)
        return found


def main(argv: Sequence[str]) -> int:
    only = argv[argv.index("--only") + 1 :] if "--only" in argv else []
    if "--all" not in argv and not only:
        print("Usage: python -m tests.lineup_speed --all | --only round season", file=sys.stderr)
        return 2
    print(json.dumps(asyncio.run(measure(only)), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
