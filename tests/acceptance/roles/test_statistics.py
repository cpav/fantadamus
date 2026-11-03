"""mvp-roles AT-6: from a synthetic statistics page served by a local test server, one collection stores every
player's season figures with the page's URL; a second run stores nothing new; a page missing a club stores
nothing, and the season figures are left for Claude to read (R1). The refresh plan's part is proven with
`compare_players` (task 5.1)."""

from __future__ import annotations

from pathlib import Path

from fantadamus.domains.facts import read_silver
from fantadamus.domains.season.silver import SEASON_STATS
from fantadamus.lake.duckdb_store import LakeStore
from tests.collect_harness import HTML, STATS_ROUTE, local_site, round_collector
from tests.collect_pages import stats_page
from tests.roles_data import stats_read


def test_at6_statistics_collected(tmp_path: Path) -> None:
    players = stats_read()["players"]
    routes = {"/robots.txt": (404, {}, b""), STATS_ROUTE: (200, HTML, stats_page(players).encode())}
    with local_site(routes) as site:
        store = LakeStore(tmp_path / "lake")
        collector = round_collector(store, site.base_url, tmp_path, statistics=True)
        [first] = collector.collect(facts=["player_season"]).pages
        [second] = collector.collect(facts=["player_season"]).pages
        routes[STATS_ROUTE] = (200, HTML, stats_page(stats_read(without=("Delta",))["players"]).encode())
        [incomplete] = collector.collect(facts=["player_season"]).pages
    url = site.base_url + STATS_ROUTE
    assert (first.outcome, first.stored) == ("stored", {"season_stats": len(players)})
    rows = read_silver(store, SEASON_STATS)
    assert sorted(row.player_id for row in rows) == sorted(player["player_id"] for player in players)
    assert {(row.source_url, row.captured_at) for row in rows} == {(url, first.fetched_at)}
    assert [record.envelope.submitted_by for record in store.read_bronze("season_stats")] == ["collector"]
    assert (second.outcome, second.stored, second.confirmed) == ("unchanged", {}, ["season_stats"])
    assert (incomplete.outcome, incomplete.for_claude) == ("rejected", ["player_season"])
    assert len(store.read_bronze("season_stats")) == 1
