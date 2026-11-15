"""mvp-sources task 4.1: Fantadamus reads Fantacalcio.it's injured and suspended pages itself, daily and twice
a day in the 48 hours before a round, and keeps their facts, never the sentences; switched off, or when a page
can't be read, Claude submits them (design C4, C9; R1.2, R3.1, R7.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.availability.silver import INJURIES, SUSPENSIONS
from fantadamus.domains.facts import read_silver
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.cadence import what_is_due
from fantadamus.web.collector import page_of
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, INJURIES_ROUTE, SUSPENSIONS_ROUTE, FakeWeb, round_collector, ticking
from tests.sources_pages import injured_page, suspended_page
from tests.xy_harness import NOW, page, send, tools

pytestmark = pytest.mark.anyio

BASE = "https://example.org"
INJURED = injured_page(
    {
        "Alfa": [("Alfa Due", "Lesione muscolare alla coscia destra, rientro dalla fine di novembre.")],
        "Beta": [("Beta Uno", "Fastidio fisico, da valutare.")],
    }
)
SUSPENDED = suspended_page(
    {
        "Alfa": ([("Alfa Sei", "squalificato nella 11a giornata di campionato")], ["Alfa Tre"]),
        "Gamma": ([], ["Gamma Otto"]),
    }
)
ROUTES = {
    f"{BASE}/robots.txt": Response(404, {}, b""),
    f"{BASE}{INJURIES_ROUTE}": Response(200, HTML, INJURED.encode()),
    f"{BASE}{SUSPENSIONS_ROUTE}": Response(200, HTML, SUSPENDED.encode()),
}


def test_read_stored_and_switched_off(tmp_path: Path) -> None:
    """Each page is read once and stored: each player by his club's key and his name as the page writes it,
    with the facts the rules found, and no sentence. Read again unchanged, nothing new is stored. Switched
    off, neither page is fetched and the report hands their facts to Claude."""
    store = LakeStore(tmp_path / "lake")
    collector = round_collector(
        store, BASE, tmp_path / "robots", transport=FakeWeb(ROUTES), hosts=["example.org"], unavailable=True
    )
    assert collector.reads("injuries")
    assert collector.reads("suspensions")
    assert (page_of("injuries"), page_of("suspensions")) == ("injuries", "suspensions")

    first = collector.collect(facts=["injuries", "suspensions"])
    assert [(page.page, page.outcome, page.stored, page.problems) for page in first.pages] == [
        ("injuries", "stored", {"injuries": 2}, []),
        ("suspensions", "stored", {"suspensions": 3}, []),
    ]
    injuries = sorted(
        (row.club, row.name, row.kind, row.body_part, row.back_from, row.back_until, row.to_be_assessed)
        for row in read_silver(store, INJURIES)
    )
    assert injuries == [
        ("alfa", "Alfa Due", "muscle", "thigh", dt.date(2026, 11, 21), dt.date(2026, 11, 30), False),
        ("beta", "Beta Uno", "other", None, None, None, True),
    ]
    bans = sorted((row.club, row.name, row.status, row.round) for row in read_silver(store, SUSPENSIONS))
    assert bans == [
        ("alfa", "Alfa Sei", "banned", 11),
        ("alfa", "Alfa Tre", "one booking", None),
        ("gamma", "Gamma Otto", "one booking", None),
    ]
    again = collector.collect(facts=["injuries", "suspensions"])
    assert [(page.page, page.outcome) for page in again.pages] == [
        ("injuries", "unchanged"),
        ("suspensions", "unchanged"),
    ]

    web = FakeWeb(ROUTES)
    off = round_collector(
        LakeStore(tmp_path / "off"),
        BASE,
        tmp_path / "robots-off",
        transport=web,
        hosts=["example.org"],
        unavailable=True,
        injuries_enabled=False,
        suspensions_enabled=False,
    )
    report = off.collect(facts=["injuries", "suspensions"])
    assert [(page.page, page.outcome, page.for_claude) for page in report.pages] == [
        ("injuries", "switched off", ["injuries"]),
        ("suspensions", "switched off", ["suspensions"]),
    ]
    assert web.calls == []


def test_a_refresh_leaves_them_to_their_cadence(tmp_path: Path) -> None:
    """A run that names no fact doesn't read them: they keep to ADR-0007's cadence, or are asked for by
    name."""
    web = FakeWeb(ROUTES)
    collector = round_collector(
        LakeStore(tmp_path / "lake"),
        BASE,
        tmp_path / "robots",
        transport=web,
        hosts=["example.org"],
        unavailable=True,
    )
    report = collector.collect()
    assert not {"injuries", "suspensions"} & {page.page for page in report.pages}


@pytest.mark.parametrize(
    ("read_at", "every"),
    [
        (NOW, dt.timedelta(days=1)),  # the round's first kickoff is 5 days off
        (dt.datetime(2026, 10, 29, 15, 0, tzinfo=dt.UTC), dt.timedelta(hours=12)),  # 47 hours off
    ],
)
async def test_due_daily_and_twice_a_day_before_a_round(
    tmp_path: Path, read_at: dt.datetime, every: dt.timedelta
) -> None:
    """ADR-0007's cadence (C9): daily, and twice a day in the 48 hours before the round's first kickoff."""
    store = LakeStore(tmp_path / "lake")
    async with tools(store) as client:
        assert not (
            await send(client, "submit_fixtures", page("fixtures"), NOW - dt.timedelta(hours=1))
        ).is_error
    log = CollectLog(tmp_path / "collect")
    collector = round_collector(
        store,
        BASE,
        tmp_path / "robots",
        transport=FakeWeb(ROUTES),
        hosts=["example.org"],
        clock=ticking(read_at),
        unavailable=True,
    )
    assert {"injuries", "suspensions"} <= set(what_is_due(store, log, read_at))
    log.append(collector.collect(facts=["injuries", "suspensions"]))
    due_soon = what_is_due(store, log, read_at + every - dt.timedelta(hours=1))
    assert not {"injuries", "suspensions"} & set(due_soon)
    assert {"injuries", "suspensions"} <= set(
        what_is_due(store, log, read_at + every + dt.timedelta(hours=1))
    )


async def test_claude_submits_them(tmp_path: Path) -> None:
    """Claude's fallback, on the same contracts: what it reads in each sentence, as facts."""
    store = LakeStore(tmp_path / "lake")
    injuries = {
        "clubs": [
            {"club": "Gamma", "players": [{"name": "Gamma Due", "kind": "fracture", "body_part": "foot"}]}
        ]
    }
    bans = {
        "clubs": [{"club": "Delta", "banned": [{"name": "Delta Sei", "rounds": [12, 13]}], "one_booking": []}]
    }
    async with tools(store) as client:
        assert not (await send(client, "submit_injuries", injuries, NOW)).is_error
        assert not (await send(client, "submit_suspensions", bans, NOW)).is_error
    assert [(row.club, row.kind, row.body_part) for row in read_silver(store, INJURIES)] == [
        ("gamma", "fracture", "foot")
    ]
    assert sorted(row.round for row in read_silver(store, SUSPENSIONS) if row.round is not None) == [12, 13]
