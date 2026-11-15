"""mvp-alerts task 2.2: only a run that stored lineups, official or probable, or a line of the injured or
suspended pages calls for a check (design C4; requirements decision 1, R4.1)."""

from __future__ import annotations

from fantadamus.mcp.alerts import ALERT_TABLES, stored_news
from fantadamus.web.collector import CollectReport, PageReport
from tests.alerts_data import AT


def _run(*stored: dict[str, int]) -> CollectReport:
    pages = [PageReport(url="https://example.org/page", outcome="stored", stored=rows) for rows in stored]
    return CollectReport(started_at=AT, finished_at=AT, round=None, pages=pages)


def test_the_tables_that_call_for_a_check() -> None:
    assert {"official_lineups", "outlet_views", "injuries", "suspensions"} == ALERT_TABLES


def test_lineups_injuries_and_bans_are_news() -> None:
    for table in ALERT_TABLES:
        assert stored_news(_run({"odds": 4}, {table: 2}))


def test_odds_fixtures_and_figures_alone_arent() -> None:
    assert not stored_news(_run({"odds": 4, "fixtures": 10, "season_stats": 500}))
    assert not stored_news(_run({"outlet_views": 0}))
    assert not stored_news(_run())
    assert not stored_news(None)
