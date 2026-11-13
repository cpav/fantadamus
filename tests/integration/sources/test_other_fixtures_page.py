"""mvp-sources task 2.1: Fantadamus reads each competition's Wikipedia page itself, weekly and daily in a
match week, and keeps the matches of the Serie A clubs; switched off, or when a page can't be read, Claude
submits them (design C2, C9; R1.2, R2.1, R7.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from pydantic import ValidationError

from fantadamus.domains.facts import read_silver
from fantadamus.domains.fixtures.silver import OTHER_FIXTURES
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.cadence import what_is_due
from fantadamus.web.collector import CollectorConfig, page_of
from fantadamus.web.fetch import Response
from tests.collect_harness import FakeWeb, round_collector, ticking
from tests.sources_pages import CUP_PROSE, Box, cup_box, link, plain_date, start_date, uefa_box, wiki_page
from tests.xy_harness import NOW, send, tools

pytestmark = pytest.mark.anyio

BASE = "https://example.org"
WIKI = BASE + "/wiki/2026%E2%80%9327_"
CHAMPIONS = WIKI + "UEFA_Champions_League_league_phase?action=raw"
CUP = WIKI + "Coppa_Italia?action=raw"
TEXT = {"Content-Type": "text/x-wiki; charset=UTF-8"}
CHAMPIONS_PAGE = wiki_page(
    [
        uefa_box(
            Box(
                link("Alfa", "Alfa FC"),
                link("Ostrava Rovers"),
                start_date(dt.date(2026, 9, 16)),
                "21:00",
                "2\u20131",
            )
        ),
        uefa_box(Box(link("Kessel"), link("Beta", "Beta Calcio"), start_date(dt.date(2026, 10, 1)), "18:45")),
        uefa_box(Box(link("Kessel"), link("Ostrava Rovers"), start_date(dt.date(2026, 10, 21)), "21:00")),
    ]
)
CUP_PAGE = wiki_page(
    [
        cup_box(
            Box(
                link("Gamma") + " (1)",
                link("Delta") + " (1)",
                plain_date(dt.date(2027, 1, 14)),
                "21:00 [[Central European Time|CET]]",
            )
        ),
        cup_box(
            Box(
                link("Vico") + " (2)",
                link("Lupa") + " (3)",
                plain_date(dt.date(2026, 8, 8)),
                "20:00 [[Central European Summer Time|CEST]]",
            )
        ),
        cup_box(Box("Winner of Match 37", "Winner of Match 38", "2\u20133 March 2027", "21:00")),
    ],
    CUP_PROSE,
)
ROUTES = {
    f"{BASE}/robots.txt": Response(404, {}, b""),
    CHAMPIONS: Response(200, TEXT, CHAMPIONS_PAGE.encode()),
    CUP: Response(200, TEXT, CUP_PAGE.encode()),
}


def test_read_stored_and_switched_off(tmp_path: Path) -> None:
    """Each page is read once and stored as its own read; only the matches with a Serie A club reach silver,
    that club by its key and the other by its name. Read again unchanged, nothing new is stored. Switched off,
    no page is fetched and the report hands the matches to Claude."""
    store = LakeStore(tmp_path / "lake")
    collector = round_collector(
        store,
        BASE,
        tmp_path / "robots",
        transport=FakeWeb(ROUTES),
        hosts=["example.org"],
        other_competitions=[CHAMPIONS, CUP],
    )
    assert collector.reads("other_fixtures")
    assert page_of("other_fixtures") == "other_fixtures"

    first = collector.collect(facts=["other_fixtures"])
    assert [(page.url, page.page, page.outcome, page.stored, page.problems) for page in first.pages] == [
        (CHAMPIONS, "other_fixtures", "stored", {"other_fixtures": 2}, []),
        (
            CUP,
            "other_fixtures",
            "stored",
            {"other_fixtures": 1},
            ["1 match without a fixed date, a kickoff or both clubs, left out"],
        ),
    ]
    rows = read_silver(store, OTHER_FIXTURES)
    assert sorted((row.kickoff_at, row.competition, row.home, row.away) for row in rows) == [
        (dt.datetime(2026, 9, 16, 19, 0, tzinfo=dt.UTC), "Champions League", "alfa", "Ostrava Rovers"),
        (dt.datetime(2026, 10, 1, 16, 45, tzinfo=dt.UTC), "Champions League", "Kessel", "beta"),
        (dt.datetime(2027, 1, 14, 20, 0, tzinfo=dt.UTC), "Coppa Italia", "gamma", "delta"),
    ]
    assert {row.source_url for row in rows} == {CHAMPIONS, CUP}
    again = collector.collect(facts=["other_fixtures"])
    assert [(page.url, page.outcome) for page in again.pages] == [
        (CHAMPIONS, "unchanged"),
        (CUP, "unchanged"),
    ]

    web = FakeWeb(ROUTES)
    off = round_collector(
        LakeStore(tmp_path / "off"),
        BASE,
        tmp_path / "robots-off",
        transport=web,
        hosts=["example.org"],
        other_competitions=[CHAMPIONS, CUP],
        other_competitions_enabled=False,
    )
    report = off.collect(facts=["other_fixtures"])
    assert [(page.url, page.outcome, page.for_claude) for page in report.pages] == [
        (CHAMPIONS, "switched off", ["other_fixtures"]),
        (CUP, "switched off", ["other_fixtures"]),
    ]
    assert web.calls == []


def test_a_refresh_leaves_them_to_their_cadence(tmp_path: Path) -> None:
    """A run that names no fact, such as "refresh the lineups", doesn't read them: they keep to ADR-0007's
    cadence, read on schedule or when asked for by name."""
    web = FakeWeb(ROUTES)
    collector = round_collector(
        LakeStore(tmp_path / "lake"),
        BASE,
        tmp_path / "robots",
        transport=web,
        hosts=["example.org"],
        other_competitions=[CHAMPIONS, CUP],
    )
    report = collector.collect()
    assert "other_fixtures" not in {page.page for page in report.pages}
    assert not {CHAMPIONS, CUP} & {url for url, *_ in web.calls}


def test_an_unreadable_page_is_claudes(tmp_path: Path) -> None:
    """A page without its match templates stores nothing, and the report hands its matches to Claude; the
    other page is still read."""
    store = LakeStore(tmp_path / "lake")
    routes = ROUTES | {CHAMPIONS: Response(200, TEXT, b"{{Short description|Moved}}\nNothing here.")}
    collector = round_collector(
        store,
        BASE,
        tmp_path / "robots",
        transport=FakeWeb(routes),
        hosts=["example.org"],
        other_competitions=[CHAMPIONS, CUP],
    )
    report = collector.collect(facts=["other_fixtures"])
    assert [(page.outcome, page.for_claude) for page in report.pages] == [
        ("unreadable", ["other_fixtures"]),
        ("stored", []),
    ]
    assert {row.competition for row in read_silver(store, OTHER_FIXTURES)} == {"Coppa Italia"}


@pytest.mark.parametrize(
    ("read_at", "every"),
    [
        (dt.datetime(2026, 9, 28, 10, 0, tzinfo=dt.UTC), dt.timedelta(days=1)),  # 1 October is 3 days off
        (dt.datetime(2026, 10, 26, 10, 0, tzinfo=dt.UTC), dt.timedelta(days=7)),  # next: 14 January
    ],
)
def test_due_weekly_and_daily_in_a_match_week(
    tmp_path: Path, read_at: dt.datetime, every: dt.timedelta
) -> None:
    """ADR-0007's cadence (C9): weekly, and daily when a match the pages list is in the coming week, so that a
    moved kickoff is noticed in time."""
    store = LakeStore(tmp_path / "lake")
    log = CollectLog(tmp_path / "collect")
    collector = round_collector(
        store,
        BASE,
        tmp_path / "robots",
        transport=FakeWeb(ROUTES),
        hosts=["example.org"],
        clock=ticking(read_at),
        other_competitions=[CHAMPIONS, CUP],
    )
    assert "other_fixtures" in what_is_due(store, log, read_at)
    log.append(collector.collect(facts=["other_fixtures"]))
    soon = read_at + every - dt.timedelta(hours=1)
    assert "other_fixtures" not in what_is_due(store, log, soon)
    assert "other_fixtures" in what_is_due(store, log, read_at + every + dt.timedelta(hours=1))


def test_an_address_naming_no_competition_is_refused() -> None:
    """The reading list's addresses name their competition, or the collector doesn't start."""
    with pytest.raises(ValidationError, match="names none of"):
        CollectorConfig(
            current_round=BASE + "/round",
            round=BASE + "/round/{round}",
            other_competitions=[WIKI + "Serie_A?action=raw"],
        )


async def test_claude_submits_them(tmp_path: Path) -> None:
    """Claude's fallback, on the same contract: a match with no Serie A club is left out of silver."""
    store = LakeStore(tmp_path / "lake")
    payload = {
        "competition": "Europa League",
        "matches": [
            {"home": "Gamma", "away": "Ostrava Rovers", "kickoff_at": "2026-11-26T18:45:00+01:00"},
            {"home": "Kessel", "away": "Ostrava Rovers", "kickoff_at": "2026-11-26T21:00:00+01:00"},
        ],
    }
    async with tools(store) as client:
        result = await send(client, "submit_other_fixtures", payload, NOW)
        assert not result.is_error, result
    assert [(row.competition, row.home, row.away) for row in read_silver(store, OTHER_FIXTURES)] == [
        ("Europa League", "gamma", "Ostrava Rovers")
    ]
