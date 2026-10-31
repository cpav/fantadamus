"""AT-9: at each time, `collect --due` fetches the round page only when some fact is past its cadence, and
names exactly those facts (R7.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.cadence import collect_due
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, FakeWeb, round_collector
from tests.collect_pages import FcoMatch, fco_round_page
from tests.xy_harness import SetClock

BASE = "https://example.org"
KICKOFF = dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC)  # Alfa v Beta, the round's first match
HOUR, MINUTE = dt.timedelta(hours=1), dt.timedelta(minutes=1)


def _page(confirmed: bool) -> Response:
    alfa = FcoMatch("Alfa", "Beta", confirmed=confirmed)
    return Response(
        200, HTML, fco_round_page(alfa, FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00")).encode()
    )


def test_at9_due_collects_exactly_whats_due(tmp_path: Path) -> None:
    web = FakeWeb(
        {f"{BASE}/robots.txt": Response(404, {}, b""), f"{BASE}{ROUND_ROUTE}": _page(confirmed=False)}
    )
    clock = SetClock(KICKOFF - 50 * HOUR)
    store, log = LakeStore(tmp_path / "lake"), CollectLog(tmp_path / "collect")
    collector = round_collector(
        store, BASE, tmp_path / "robots", transport=web, hosts=["example.org"], clock=clock
    )

    def run_at(when: dt.datetime) -> list[str] | None:
        clock.now = when
        report = collect_due(collector, log)
        return None if report is None else report.due

    assert run_at(KICKOFF - 50 * HOUR) == ["fixtures"]  # no fixtures yet: that read brings everything
    assert run_at(KICKOFF - 44 * HOUR) is None  # 6 hours on: nothing is due, nothing is fetched
    assert run_at(KICKOFF - 38 * HOUR) == ["probable_lineups"]  # 12 hours: lineups twice a day, odds daily
    assert run_at(KICKOFF - 23 * HOUR) == ["probable_lineups", "match_odds"]  # the last day: every 3 hours
    web.routes = {**web.routes, f"{BASE}{ROUND_ROUTE}": _page(confirmed=True)}
    assert run_at(KICKOFF - 74 * MINUTE) == ["probable_lineups", "official_lineups", "match_odds"]
    assert run_at(KICKOFF - 60 * MINUTE) is None  # the official lineup is in, and 14 minutes isn't 3 hours
    page_reads = [url for url, _, _ in web.calls if url.endswith(ROUND_ROUTE)]
    assert len(page_reads) == 4  # one read per run that had something due
