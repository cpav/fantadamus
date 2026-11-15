"""mvp-sources task 6.1: Fantadamus reads the round ratings page itself, the morning after a round, and keeps
each player's base rating from each desk; switched off, or when the page can't be read, Claude submits them
(design C6, C9; R1.2, R4.2, R7.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.facts import read_silver
from fantadamus.domains.ratings.silver import MATCH_RATINGS
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.cadence import what_is_due
from fantadamus.web.collector import page_of
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, RATINGS_ROUTE, FakeWeb, round_collector, ticking
from tests.sources_pages import NOT_PUBLISHED, Rated, ratings_page
from tests.xy_harness import NOW, page, send, tools

pytestmark = pytest.mark.anyio

BASE = "https://example.org"
ROUND_9 = f"{BASE}{RATINGS_ROUTE.format(round=9)}"
LAST_KICKOFF = dt.datetime(2026, 10, 31, 17, 0, tzinfo=dt.UTC)  # Gamma v Delta, 18:00 in Rome
MORNING = LAST_KICKOFF + dt.timedelta(hours=12)
PAGE = ratings_page(
    9,
    [
        (
            "Alfa",
            "Beta",
            [
                Rated("UNO", "A", "P", ("6,00", "6,50", "6,00")),
                Rated("SETTE", "A", "C", ("s.v.", "s.v.", "6,00"), came_on=9),
            ],
            [Rated("NOVE", "B", "A", ("7,50", NOT_PUBLISHED, "7,00"))],
        )
    ],
)
ROUTES = {f"{BASE}/robots.txt": Response(404, {}, b""), ROUND_9: Response(200, HTML, PAGE.encode())}


async def _with_fixtures(store: LakeStore) -> None:
    async with tools(store) as client:
        assert not (
            await send(client, "submit_fixtures", page("fixtures"), NOW - dt.timedelta(hours=1))
        ).is_error


async def test_read_stored_and_switched_off(tmp_path: Path) -> None:
    """The page of the round just played is read once, a row per player and desk that published, s.v. as no
    rating; read again unchanged, nothing new. Switched off, nothing is fetched and the report hands the
    ratings to Claude."""
    store = LakeStore(tmp_path / "lake")
    await _with_fixtures(store)
    collector = round_collector(
        store,
        BASE,
        tmp_path / "robots",
        transport=FakeWeb(ROUTES),
        hosts=["example.org"],
        clock=ticking(MORNING),
        ratings=True,
    )
    assert collector.reads("match_ratings")
    assert page_of("match_ratings") == "ratings"
    first = collector.collect(facts=["match_ratings"])
    assert [(page.url, page.page, page.outcome, page.stored) for page in first.pages] == [
        (ROUND_9, "ratings", "stored", {"match_ratings": 8})
    ]
    rows = read_silver(store, MATCH_RATINGS)
    assert sorted((row.round, row.home, row.away, row.club, row.name, row.desk, row.rating) for row in rows)[
        :4
    ] == [
        (9, "alfa", "beta", "alfa", "SETTE A.", "Fantacalcio.it", None),
        (9, "alfa", "beta", "alfa", "SETTE A.", "Roma", None),
        (9, "alfa", "beta", "alfa", "SETTE A.", "Torino", 6.0),
        (9, "alfa", "beta", "alfa", "UNO A.", "Fantacalcio.it", 6.0),
    ]
    assert {(row.name, row.came_on, row.minutes) for row in rows if row.club == "alfa"} == {
        ("UNO A.", False, None),
        ("SETTE A.", True, 9),
    }
    again = collector.collect(facts=["match_ratings"])
    assert [(page.page, page.outcome) for page in again.pages] == [("ratings", "unchanged")]
    assert [page.outcome for page in collector.collect_ratings(9).pages] == ["unchanged"]

    web = FakeWeb(ROUTES)
    off = round_collector(
        store,
        BASE,
        tmp_path / "robots-off",
        transport=web,
        hosts=["example.org"],
        ratings=True,
        ratings_enabled=False,
        clock=ticking(MORNING),
    )
    report = off.collect(facts=["match_ratings"])
    assert [(page.page, page.outcome, page.for_claude) for page in report.pages] == [
        ("ratings", "switched off", ["match_ratings"])
    ]
    assert web.calls == []


async def test_due_the_morning_after_a_round(tmp_path: Path) -> None:
    """ADR-0007's cadence (C9): once a round has been played, its page is due the morning after its last
    match, once; before any round has been played, nothing is."""
    store = LakeStore(tmp_path / "lake")
    log = CollectLog(tmp_path / "collect")
    assert "match_ratings" not in what_is_due(store, log, NOW)
    await _with_fixtures(store)
    assert "match_ratings" not in what_is_due(store, log, MORNING - dt.timedelta(hours=1))
    assert "match_ratings" in what_is_due(store, log, MORNING)
    collector = round_collector(
        store,
        BASE,
        tmp_path / "robots",
        transport=FakeWeb(ROUTES),
        hosts=["example.org"],
        clock=ticking(MORNING),
        ratings=True,
    )
    log.append(collector.collect(facts=["match_ratings"]))
    assert "match_ratings" not in what_is_due(store, log, MORNING + dt.timedelta(days=3))


async def test_claude_submits_them(tmp_path: Path) -> None:
    """Claude's fallback, on the same contract."""
    store = LakeStore(tmp_path / "lake")
    rated = {
        "round": 9,
        "matches": [
            {
                "home": "Gamma",
                "away": "Delta",
                "players": [
                    {
                        "club": "Delta",
                        "name": "Delta Nove",
                        "role": "A",
                        "ratings": [{"desk": "Fantacalcio.it", "rating": 6.5}],
                    }
                ],
            }
        ],
    }
    async with tools(store) as client:
        assert not (await send(client, "submit_ratings", rated, NOW)).is_error
    assert [(row.club, row.desk, row.rating) for row in read_silver(store, MATCH_RATINGS)] == [
        ("delta", "Fantacalcio.it", 6.5)
    ]
