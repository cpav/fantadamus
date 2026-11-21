"""mvp-fixes AT-2: retrying stays polite. Over runs that can't read a host's robots.txt, each run asks for it
once and requests none of the host's pages, and an answer doesn't try the page again sooner than `RETRY_AFTER`
after a failed try (R1.2, R1.3). One request a second per host is the fetcher's own rule, unchanged
(`mvp-collect` P1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.cadence import RETRY_AFTER, may_read_page
from tests.collect_harness import FakeWeb, round_collector, ticking
from tests.xy_harness import NOW

BASE = "https://example.org"
ROBOTS = BASE + "/robots.txt"
WIKI = BASE + "/wiki/2026%E2%80%9327_"
CHAMPIONS = WIKI + "UEFA_Champions_League_league_phase?action=raw"
CUP = WIKI + "Coppa_Italia?action=raw"
RUNS = 4


def test_at2_retries_stay_polite(tmp_path: Path) -> None:
    web = FakeWeb({ROBOTS: TimeoutError("timed out")})
    log = CollectLog(tmp_path / "collect")
    collector = round_collector(
        LakeStore(tmp_path / "lake"),
        BASE,
        tmp_path / "robots",
        transport=web,
        hosts=["example.org"],
        clock=ticking(NOW, dt.timedelta(minutes=15)),
        other_competitions=[CHAMPIONS, CUP],
    )
    for _ in range(RUNS):
        report = collector.collect(facts=["other_fixtures"])
        log.append(report)
        assert [page.outcome for page in report.pages] == ["failed", "failed"]
    assert [url for url, _, _ in web.calls] == [ROBOTS] * RUNS
    last = report.started_at
    assert not may_read_page("other_fixtures", log, last + RETRY_AFTER - dt.timedelta(minutes=1))
    assert may_read_page("other_fixtures", log, last + RETRY_AFTER)
