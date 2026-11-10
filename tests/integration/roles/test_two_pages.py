"""mvp-roles tasks 3.1 and 3.2: the collector reads the round page and the statistics page, each when its
facts are asked for or due, with one report each (design C4, C5; R1.1, R1.4, R1.5, R1.6)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.cadence import collect_due, what_is_due
from fantadamus.web.collector import CollectReport, PageReport
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE, local_site, round_collector, ticking
from tests.collect_pages import FcoMatch, fco_round_page, stats_page
from tests.roles_data import stats_read

ROUND = fco_round_page(FcoMatch("Alfa", "Beta")).encode()
STATS = stats_page(stats_read()["players"]).encode()
START = dt.datetime(2026, 11, 3, 8, 0, tzinfo=dt.UTC)


def _routes(stats: bytes | None = STATS) -> dict[str, tuple[int, dict[str, str], bytes]]:
    routes = {"/robots.txt": (404, {}, b""), ROUND_ROUTE: (200, HTML, ROUND)}
    if stats is not None:
        routes[STATS_ROUTE] = (200, HTML, stats)
    return routes


def test_reads_the_pages_asked_for(tmp_path: Path) -> None:
    with local_site(_routes()) as site:
        collector = round_collector(LakeStore(tmp_path / "lake"), site.base_url, tmp_path, statistics=True)
        both = collector.collect().pages
        [stats] = collector.collect(facts=["player_season"]).pages
        [lineups] = collector.collect(facts=["probable_lineups"]).pages
        [round_eleven] = collector.collect(11).pages
    assert [(page.page, page.outcome) for page in both] == [("round", "stored"), ("statistics", "stored")]
    assert both[1].url == site.base_url + STATS_ROUTE
    assert both[1].stored == {"season_stats": len(stats_read()["players"])}
    assert (stats.page, stats.outcome, stats.confirmed) == ("statistics", "unchanged", ["season_stats"])
    assert (lineups.page, lineups.outcome) == ("round", "unchanged")
    assert (round_eleven.page, round_eleven.url) == (
        "round",
        site.base_url + "/probabili-formazioni/11-giornata",
    )


def test_statistics_failure_for_claude(tmp_path: Path) -> None:
    missing_club = stats_page(stats_read(without=("Gamma",))["players"]).encode()
    routes = _routes(stats=None)
    with local_site(routes) as site:
        store = LakeStore(tmp_path / "lake")
        [failed] = (
            round_collector(store, site.base_url, tmp_path, statistics=True)
            .collect(facts=["player_season"])
            .pages
        )
        routes[STATS_ROUTE] = (200, HTML, missing_club)
        [refused] = (
            round_collector(store, site.base_url, tmp_path, statistics=True)
            .collect(facts=["player_season"])
            .pages
        )
        off = round_collector(store, site.base_url, tmp_path, statistics=True, statistics_enabled=False)
        [switched_off] = off.collect(facts=["player_season"]).pages
        requests = [path for path, _ in site.requests]
    assert (failed.outcome, failed.for_claude) == ("failed", ["player_season"])
    assert (refused.outcome, refused.for_claude) == ("rejected", ["player_season"])
    assert "the read has no players of Gamma" in " ".join(refused.problems)
    assert (switched_off.outcome, switched_off.for_claude) == ("switched off", ["player_season"])
    assert requests.count(STATS_ROUTE) == 2
    assert store.read_bronze("season_stats") == []


def test_last_attempt_per_page(tmp_path: Path) -> None:
    log = CollectLog(tmp_path / "collect")
    round_page = PageReport(url="https://example.org/round", outcome="stored", fetched_at=START)
    statistics = PageReport(url="https://example.org/stats", page="statistics", outcome="failed")
    log.append(CollectReport(started_at=START, finished_at=START, round=None, pages=[round_page]))
    later = START + dt.timedelta(hours=1)
    log.append(CollectReport(started_at=later, finished_at=later, round=None, pages=[statistics]))
    old = '{"started_at": "2026-11-02T08:00:00Z", "finished_at": "2026-11-02T08:00:00Z", "round": null, '
    old += '"pages": [{"url": "https://example.org/round", "outcome": "stored"}]}\n'
    with (log.root / "2026-10.jsonl").open("w", encoding="utf-8") as earlier:
        earlier.write(old)  # a line written before reports named their page: the round page's
    assert log.last_attempt(START + dt.timedelta(hours=2)) == START
    assert log.last_attempt(START + dt.timedelta(hours=2), "statistics") == later
    assert log.last_attempt(START - dt.timedelta(hours=1)) == START - dt.timedelta(days=1)
    assert log.last_attempt(START - dt.timedelta(hours=1), "statistics") is None


def test_due_reads_only_the_pages_due(tmp_path: Path) -> None:
    with local_site(_routes()) as site:
        store = LakeStore(tmp_path / "lake")
        log = CollectLog(tmp_path / "collect")
        clock = ticking(START, dt.timedelta(seconds=1))
        collector = round_collector(store, site.base_url, tmp_path, statistics=True, clock=clock)
        first = collect_due(collector, log)
        site.requests.clear()
        day_later = round_collector(
            store, site.base_url, tmp_path, statistics=True, clock=ticking(START + dt.timedelta(hours=25))
        )
        assert what_is_due(store, log, START + dt.timedelta(hours=25)) == [
            "player_season",
            "penalty_takers",
            "team_season",
        ]
        second = collect_due(day_later, log)
        requests = [path for path, _ in site.requests]
        round_only = round_collector(
            store, site.base_url, tmp_path, clock=ticking(START + dt.timedelta(days=3))
        )
        third = collect_due(round_only, log)  # no statistics page configured: its fact isn't asked for
    assert first is not None
    assert first.due == ["fixtures", "player_season"]
    assert [page.page for page in first.pages] == ["round", "statistics"]
    assert second is not None
    assert [page.page for page in second.pages] == ["statistics"]
    assert ROUND_ROUTE not in requests
    assert third is None
